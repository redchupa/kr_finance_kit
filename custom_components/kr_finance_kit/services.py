"""Service handlers: refresh_now, add_position, remove_position.

Positions are stored on the ConfigEntry's options blob so they're
recoverable across restarts. They never appear in source or fixtures —
the user adds them explicitly at runtime.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DISCLOSURE_CORP_CODES,
    CONF_INCLUDE_FX,
    CONF_INCLUDE_INDICES,
    CONF_KR_TICKERS,
    CONF_OPENDART_API_KEY,
    CONF_POSITIONS,
    CONF_US_TICKERS,
    DOMAIN,
    LOGGER,
    MARKET_KR,
    MARKET_US,
)

SERVICE_REFRESH_NOW = "refresh_now"
SERVICE_ADD_POSITION = "add_position"
SERVICE_REMOVE_POSITION = "remove_position"

_POSITION_SCHEMA = vol.Schema(
    {
        vol.Required("ticker"): cv.string,
        vol.Required("quantity"): vol.Coerce(float),
        vol.Required("avg_price"): vol.Coerce(float),
        vol.Required("market"): vol.In([MARKET_KR, MARKET_US]),
    }
)
_REMOVE_SCHEMA = vol.Schema(
    {
        vol.Required("ticker"): cv.string,
        vol.Required("market"): vol.In([MARKET_KR, MARKET_US]),
    }
)


def _first_entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _save_positions(hass: HomeAssistant, entry: ConfigEntry, positions: list[dict[str, Any]]) -> None:
    new_options = {
        CONF_KR_TICKERS: entry.options.get(CONF_KR_TICKERS, entry.data.get(CONF_KR_TICKERS, [])),
        CONF_US_TICKERS: entry.options.get(CONF_US_TICKERS, entry.data.get(CONF_US_TICKERS, [])),
        CONF_DISCLOSURE_CORP_CODES: entry.options.get(
            CONF_DISCLOSURE_CORP_CODES, entry.data.get(CONF_DISCLOSURE_CORP_CODES, [])
        ),
        CONF_OPENDART_API_KEY: entry.options.get(
            CONF_OPENDART_API_KEY, entry.data.get(CONF_OPENDART_API_KEY, "")
        ),
        CONF_INCLUDE_INDICES: entry.options.get(
            CONF_INCLUDE_INDICES, entry.data.get(CONF_INCLUDE_INDICES, True)
        ),
        CONF_INCLUDE_FX: entry.options.get(CONF_INCLUDE_FX, entry.data.get(CONF_INCLUDE_FX, True)),
        CONF_POSITIONS: positions,
    }
    hass.config_entries.async_update_entry(entry, options=new_options)


def async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_NOW):
        return

    async def _refresh_now(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
            market = store.get("market")
            disclosure = store.get("disclosure")
            if market is not None:
                await market.async_request_refresh()
            if disclosure is not None:
                await disclosure.async_request_refresh()

    async def _add_position(call: ServiceCall) -> None:
        entry = _first_entry(hass)
        if entry is None:
            LOGGER.error("add_position: no kr_finance_kit entry found")
            return
        cur = list(
            entry.options.get(CONF_POSITIONS, entry.data.get(CONF_POSITIONS, []))
        )
        ticker = call.data["ticker"].strip().upper()
        market = call.data["market"]
        # Upsert by (market, ticker).
        cur = [p for p in cur if not (p.get("ticker") == ticker and p.get("market") == market)]
        cur.append(
            {
                "ticker": ticker,
                "quantity": float(call.data["quantity"]),
                "avg_price": float(call.data["avg_price"]),
                "market": market,
            }
        )
        _save_positions(hass, entry, cur)

    async def _remove_position(call: ServiceCall) -> None:
        entry = _first_entry(hass)
        if entry is None:
            return
        cur = list(
            entry.options.get(CONF_POSITIONS, entry.data.get(CONF_POSITIONS, []))
        )
        ticker = call.data["ticker"].strip().upper()
        market = call.data["market"]
        cur = [p for p in cur if not (p.get("ticker") == ticker and p.get("market") == market)]
        _save_positions(hass, entry, cur)

    hass.services.async_register(DOMAIN, SERVICE_REFRESH_NOW, _refresh_now)
    hass.services.async_register(
        DOMAIN, SERVICE_ADD_POSITION, _add_position, schema=_POSITION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE_POSITION, _remove_position, schema=_REMOVE_SCHEMA
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    # Only unregister when the last entry unloads — leave to caller.
    for name in (SERVICE_REFRESH_NOW, SERVICE_ADD_POSITION, SERVICE_REMOVE_POSITION):
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)
