"""KR Finance Kit — Home Assistant integration for Korean finance data.

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


async def _migrate_legacy_entity_ids(hass: "HomeAssistant") -> None:
    """Rename pre-v0.1.31 Korean-slug entity_ids onto the fi_* form.

    Why this exists: pre-0.1.31 the integration set Korean device
    names without a ``suggested_object_id``, so HA slugified those
    Korean names into the entity_id ("sensor.hangug_sijang_jipyo_kospi"
    instead of "sensor.fi_kospi"). New installs are already correct,
    but users who upgraded carry the Korean slug forever because HA's
    entity registry pins entity_id by unique_id on first registration.
    This sweep runs once on setup and renames each stuck entity to its
    new ``fi_*`` slug. History/statistics stay attached because HA
    updates them via the registry update.

    No-op on already-correct entities — safe to run every setup.
    """
    from homeassistant.helpers import entity_registry as er
    from .const import DOMAIN, ENTITY_ID_PREFIX, LOGGER

    registry = er.async_get(hass)
    # list(...) — we're mutating during iteration.
    for entry in list(registry.entities.values()):
        if entry.platform != DOMAIN:
            continue
        expected = _expected_object_id(DOMAIN, ENTITY_ID_PREFIX, entry.unique_id)
        if expected is None:
            continue
        new_entity_id = f"{entry.domain}.{expected}"
        if entry.entity_id == new_entity_id:
            continue
        # Collision guard — if a fresh entity already claimed the
        # target slug we leave the stuck one alone rather than blow
        # up the setup. Practically rare (same unique_id can't be
        # registered twice) but defensive.
        if registry.async_get(new_entity_id) is not None:
            LOGGER.warning(
                "Skipping entity_id migration: %s -> %s (target already exists)",
                entry.entity_id, new_entity_id,
            )
            continue
        LOGGER.info("Migrating entity_id %s -> %s", entry.entity_id, new_entity_id)
        registry.async_update_entity(entry.entity_id, new_entity_id=new_entity_id)


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

    # Run before coordinator setup so renamed entity_ids show the new
    # slug from the very first state push (no flicker through the old
    # Korean entity_id on restart).
    await _migrate_legacy_entity_ids(hass)

    market = MarketCoordinator(hass, entry)
    await market.async_config_entry_first_refresh()

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
    async_register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
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
