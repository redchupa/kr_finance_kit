"""KR Finance Kit — Home Assistant integration for Korean finance data.

HA-specific imports are lazy (inside ``async_setup_entry`` /
``async_unload_entry``) so the package is importable without Home
Assistant installed. That keeps pure-helper unit tests (``portfolio``,
``api.opendart`` parsers) runnable in plain pytest without dragging in
the full HA dependency tree.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _config(entry) -> dict:
    return {**entry.data, **(entry.options or {})}


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    from homeassistant.const import Platform

    from .const import CONF_DISCLOSURE_CORP_CODES, CONF_OPENDART_API_KEY, DOMAIN
    from .coordinator import DisclosureCoordinator, MarketCoordinator
    from .llm_tool import async_setup_llm_api
    from .services import async_register_services

    hass.data.setdefault(DOMAIN, {})

    market = MarketCoordinator(hass, entry)
    await market.async_config_entry_first_refresh()

    cfg = _config(entry)
    opendart_key = (cfg.get(CONF_OPENDART_API_KEY) or "").strip()
    corp_codes = list(cfg.get(CONF_DISCLOSURE_CORP_CODES, []) or [])
    disclosure: DisclosureCoordinator | None = None
    if opendart_key and corp_codes:
        disclosure = DisclosureCoordinator(hass, opendart_key, corp_codes)
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
