"""Finance Kit — Home Assistant integration for Korean & global market data.

HA-specific imports are lazy (inside ``async_setup_entry`` /
``async_unload_entry``) so the package is importable without Home
Assistant installed. That keeps pure-helper unit tests (``portfolio``,
``api.opendart`` parsers) runnable in plain pytest without dragging in
the full HA dependency tree.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _config(entry) -> dict:
    return {**entry.data, **(entry.options or {})}


def _expected_object_id(domain: str, entity_id_prefix: str, unique_id: str) -> str | None:
    """Compute the v0.1.31+ entity_id slug from a unique_id.

    Mirrors the ``_attr_suggested_object_id`` rules in sensor.py /
    binary_sensor.py so the migration converges old entities (created
    when device names were Korean and produced Korean slugs) onto the
    same English ``fi_*`` slug a fresh v0.1.31+ install would assign.

    Returns ``None`` when the unique_id doesn't belong to this
    integration (defensive — we already filter by platform upstream).
    """
    prefix = f"{domain}_"
    if not unique_id.startswith(prefix):
        return None
    suffix = unique_id[len(prefix):]
    # The entity_id slug drops the "index_"/"fx_" sub-prefix that
    # the unique_id carries (sensor.py picks the index/pair name
    # directly for suggested_object_id).
    if suffix.startswith("index_"):
        suffix = suffix[len("index_"):]
    elif suffix.startswith("fx_"):
        suffix = suffix[len("fx_"):]
    slug = re.sub(r"[^a-z0-9_]+", "_", suffix.lower()).strip("_")
    if not slug:
        return None
    return f"{entity_id_prefix}_{slug}"


def _plan_entity_id_migrations(
    entities: list[tuple[str, str, str]],
    handled: set[str],
    first_run: bool,
    domain: str,
    prefix: str,
) -> tuple[list[tuple[str, str]], set[str]]:
    """Decide which entities to rename — pure, unit-tested.

    ``entities`` is ``[(entity_domain, entity_id, unique_id), ...]`` for
    this integration. An entity is considered exactly once (tracked by
    unique_id in ``handled``): the first time it's seen it gets its
    ``fi_*`` slug, after that it's left alone, so an entity_id the user
    renamed in the UI sticks. On the very first run after upgrading
    (``first_run``) existing entities are only recorded, never renamed —
    earlier versions already normalised them on every setup.

    Returns ``(renames, new_handled)``; ``new_handled`` is pruned to
    unique_ids still in the registry.
    """
    renames: list[tuple[str, str]] = []
    present: set[str] = set()
    new_handled = set(handled)
    for ent_domain, entity_id, unique_id in entities:
        expected = _expected_object_id(domain, prefix, unique_id)
        if expected is None:
            continue
        present.add(unique_id)
        if unique_id in handled:
            continue
        new_handled.add(unique_id)
        if first_run:
            continue
        target = f"{ent_domain}.{expected}"
        if entity_id != target:
            renames.append((entity_id, target))
    return renames, new_handled & present


async def _migrate_legacy_entity_ids(hass: "HomeAssistant") -> None:
    """Give each entity its short ``fi_*`` entity_id — once.

    Why: pre-0.1.31 installs got Korean-slug entity_ids, and Home
    Assistant 2026.x ignores ``_attr_suggested_object_id`` so brand-new
    entities are registered under a name-based slug
    ("sensor.ethereum_krw"). This sweep renames such entities to
    ``fi_*`` the first time it sees them and records them in a small
    Store, so a later rename by the user is never reverted (v0.2.1 and
    earlier re-ran the rename on every setup).

    Called twice per setup: before the platforms (existing entities) and
    right after them (entities created in this setup).
    """
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.storage import Store

    from .const import DOMAIN, ENTITY_ID_PREFIX, LOGGER

    store = Store(hass, 1, f"{DOMAIN}.entity_migration")
    stored = await store.async_load()
    first_run = not isinstance(stored, dict)
    handled = set((stored or {}).get("handled", []) if not first_run else [])

    registry = er.async_get(hass)
    entities = [
        (e.domain, e.entity_id, e.unique_id)
        for e in list(registry.entities.values())
        if e.platform == DOMAIN
    ]
    renames, new_handled = _plan_entity_id_migrations(
        entities, handled, first_run, DOMAIN, ENTITY_ID_PREFIX
    )
    for old_id, new_id in renames:
        # Collision guard — leave the entity alone rather than fail setup.
        if registry.async_get(new_id) is not None:
            LOGGER.warning(
                "Skipping entity_id migration: %s -> %s (target already exists)",
                old_id, new_id,
            )
            continue
        LOGGER.info("Migrating entity_id %s -> %s", old_id, new_id)
        registry.async_update_entity(old_id, new_entity_id=new_id)

    if first_run or new_handled != handled:
        await store.async_save({"handled": sorted(new_handled)})


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    from homeassistant.const import Platform

    from .const import (
        CONF_DISCLOSURE_CATEGORIES,
        CONF_DISCLOSURE_CORP_CODES,
        CONF_OPENDART_API_KEY,
        DOMAIN,
    )
    from .coordinator import DisclosureCoordinator, MarketCoordinator
    from .llm_tool import async_setup_llm_api
    from .services import async_register_services

    hass.data.setdefault(DOMAIN, {})

    # v0.2.0 rebrand: "KR Finance Kit" → "Finance Kit". Only the untouched
    # default title is migrated — a title the user renamed is left alone.
    # Runs before the update listener is attached, so no reload is triggered.
    if entry.title == "KR Finance Kit":
        hass.config_entries.async_update_entry(entry, title="Finance Kit")

    # Run before coordinator setup so renamed entity_ids show the new
    # slug from the very first state push (no flicker through the old
    # Korean entity_id on restart).
    await _migrate_legacy_entity_ids(hass)

    # The coordinator's first data fetch is scheduled as a background task
    # at the end of setup (see below), NOT awaited here. A blocking
    # async_config_entry_first_refresh() used to hold up Home Assistant
    # startup by ~1 minute: the market fetch walks dozens of symbols
    # serially through yfinance (one HTTP round-trip each, doubled when
    # detailed attrs are on). Deferring it keeps HA start fast.
    market = MarketCoordinator(hass, entry)

    cfg = _config(entry)
    opendart_key = (cfg.get(CONF_OPENDART_API_KEY) or "").strip()
    corp_codes = list(cfg.get(CONF_DISCLOSURE_CORP_CODES, []) or [])
    categories = list(cfg.get(CONF_DISCLOSURE_CATEGORIES, []) or [])
    disclosure: DisclosureCoordinator | None = None
    if opendart_key and corp_codes:
        disclosure = DisclosureCoordinator(hass, opendart_key, corp_codes, categories)
        await disclosure.async_config_entry_first_refresh()

    store = {"market": market, "disclosure": disclosure}
    store["unregister_llm"] = await async_setup_llm_api(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = store

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
    )
    # HA 2026.x ignores ``_attr_suggested_object_id`` and registers brand-new
    # entities under a name-based slug ("sensor.ethereum_krw"); the sweep
    # above only fixes those on the *next* setup, so a ticker added from the
    # options screen or the sidebar panel would change entity_id once more
    # later and break automations written in between. Running the same
    # idempotent sweep again right after the platforms registered their
    # entities pins new ones to their fi_* slug immediately.
    await _migrate_legacy_entity_ids(hass)
    async_register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Sidebar panel (v0.2.0). A failure here must never take the sensors
    # down with it — the panel is a convenience layer on top.
    try:
        from .panel import async_setup_panel

        await async_setup_panel(hass, entry)
    except Exception as err:  # noqa: BLE001
        from .const import LOGGER

        LOGGER.warning("Finance Kit sidebar panel could not be registered: %s", err)

    # Non-blocking first market fetch. Entities are already added above and
    # tolerate coordinator.data being None — they render "unknown" until
    # this refresh lands, then update in place. Running it as a background
    # task (auto-cancelled on unload) means a slow or unreachable yfinance
    # endpoint no longer delays Home Assistant startup.
    entry.async_create_background_task(
        hass, market.async_refresh(), f"{DOMAIN}_market_first_refresh"
    )
    return True


async def _async_update_listener(hass: "HomeAssistant", entry: "ConfigEntry") -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    from homeassistant.const import Platform

    from .const import DOMAIN
    from .llm_tool import async_cleanup_llm_api
    from .services import async_unregister_services

    store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}) or {}
    async_cleanup_llm_api(store.get("unregister_llm"))
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR, Platform.BINARY_SENSOR]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.config_entries.async_entries(DOMAIN):
            async_unregister_services(hass)
    return unload_ok


async def async_remove_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> None:
    """Integration deleted — drop the sidebar panel too.

    Not done in ``async_unload_entry`` because every options change
    (including adding a ticker from the panel itself) reloads the entry,
    and removing the panel there would yank the page out from under the
    user mid-edit.
    """
    from .const import DOMAIN

    # HA still lists the entry being removed while this hook runs.
    others = [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id]
    if others:
        return
    from .panel import async_remove_panel

    async_remove_panel(hass)
