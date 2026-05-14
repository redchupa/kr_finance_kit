"""Service handlers: refresh_now, add_position, remove_position.

Positions are stored on the ConfigEntry's options blob so they're
recoverable across restarts. They never appear in source or fixtures —
the user adds them explicitly at runtime.
"""
from __future__ import annotations

import math
import re
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    CONF_POSITIONS,
    DOMAIN,
    LOGGER,
    MARKET_KR,
    MARKET_US,
)

SERVICE_REFRESH_NOW = "refresh_now"
SERVICE_ADD_POSITION = "add_position"
SERVICE_REMOVE_POSITION = "remove_position"

# Ticker grammar: alnum start, then alnum or dot/hyphen. Covers the
# real shapes — `005930`, `005930.KS`, `005930.KQ`, `AAPL`, `BRK-B`,
# `RY.TO`. Hard-rejects whitespace, slashes, equals signs, currency
# symbols, emoji, and SQL/HTML-style punctuation that a user might
# accidentally paste from a broker site or screenshot OCR.
_TICKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,19}$")

# Reasonable upper bound. yfinance prices have ranged from 0.0001 (sub-penny
# OTC equities, micro-priced crypto) to ~$700,000 (Berkshire Hathaway A) —
# 1e9 is comfortably above anything plausible, so anything hitting it is
# almost certainly a unit-of-measurement mistake (e.g. someone pasted
# total cost instead of unit cost).
_MAX_NUMERIC = 1_000_000_000.0


def _validate_ticker(value: Any) -> str:
    """Sanitize + validate the ticker field.

    Hard fails on:
      • non-string input
      • empty / whitespace-only strings
      • anything outside ``[A-Za-z0-9.\\-]`` (special chars, spaces, emoji)
      • > 20 chars

    Yahoo's real-world ticker symbols all fit in this grammar; rejecting
    the wider set protects the positions store from junk that would
    silently never match a coordinator quote and leave a permanently
    unavailable sensor.
    """
    if not isinstance(value, str):
        raise vol.Invalid(
            f"Ticker must be a string, got {type(value).__name__}."
        )
    v = value.strip().upper()
    if not v:
        raise vol.Invalid("Ticker is empty — enter a stock code like 005930 or AAPL.")
    if not _TICKER_RE.match(v):
        raise vol.Invalid(
            f"Invalid ticker {value!r}. Only letters, digits, '.' and '-' are allowed "
            "(e.g. 005930, 005930.KQ, AAPL, BRK-B). Spaces, currency symbols, "
            "and other special characters are rejected."
        )
    return v


def _finite_positive(value: Any) -> float:
    """Coerce to a strictly positive, finite float.

    ``vol.Coerce(float)`` alone passes ``float('nan')`` and
    ``float('inf')`` — both would silently corrupt totals downstream
    (sum * NaN = NaN forever). We reject them at the schema layer so
    the user gets a clean error instead of a broken portfolio sensor.
    """
    try:
        f = float(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid(f"Must be a number, got {value!r}.") from err
    if not math.isfinite(f):
        raise vol.Invalid(f"Must be a finite number, got {value!r}.")
    if f <= 0:
        raise vol.Invalid(
            f"Must be positive (> 0), got {f}. Quantity and average price "
            "are both strictly positive."
        )
    if f > _MAX_NUMERIC:
        raise vol.Invalid(
            f"{f} is too large (max {_MAX_NUMERIC:.0f}). If you meant the total "
            "cost basis, divide by quantity first — avg_price is per-share."
        )
    return f


_POSITION_SCHEMA = vol.Schema(
    {
        vol.Required("ticker"): _validate_ticker,
        vol.Required("quantity"): _finite_positive,
        vol.Required("avg_price"): _finite_positive,
        vol.Required("market"): vol.In([MARKET_KR, MARKET_US]),
    }
)
_REMOVE_SCHEMA = vol.Schema(
    {
        vol.Required("ticker"): _validate_ticker,
        vol.Required("market"): vol.In([MARKET_KR, MARKET_US]),
    }
)


def _first_entry(hass: HomeAssistant) -> ConfigEntry | None:
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _save_positions(hass: HomeAssistant, entry: ConfigEntry, positions: list[dict[str, Any]]) -> None:
    """Persist positions onto entry.options without dropping any other key.

    Earlier this function rebuilt entry.options from scratch using an
    explicit list of six keys. That silently nuked every other option
    the user had set — other_tickers, ticker_labels, US/global index
    toggles, P/L alert threshold, disclosure category filter,
    detailed_attrs, target_currency_krw, etc. — turning those sensors
    into "restored / unavailable" on the next reload because the
    coordinator no longer saw the tickers and the platform skipped
    them in add_entities. We now spread the existing options dict and
    only overwrite the positions slot, so every other field survives.
    """
    new_options = {**(entry.options or {}), CONF_POSITIONS: positions}
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
        # ticker is already validated + uppercased by _validate_ticker.
        ticker = call.data["ticker"]
        market = call.data["market"]
        # Soft sanity check by market — log a hint when the ticker
        # shape is implausible for that market, but still proceed so
        # users with edge-case tickers aren't blocked.
        if market == MARKET_KR and not ticker[:6].isdigit():
            LOGGER.warning(
                "add_position: KR ticker %r doesn't start with 6 digits — "
                "this won't match a Korean stock quote. Use codes like "
                "005930 or 035720.KQ.",
                ticker,
            )
        elif market == MARKET_US and ticker.isdigit():
            LOGGER.warning(
                "add_position: US ticker %r is all digits — US symbols "
                "are typically alphabetic (AAPL, MSFT). Did you mean to "
                "set market=KR?",
                ticker,
            )
        # Upsert by (market, ticker).
        cur = [p for p in cur if not (p.get("ticker") == ticker and p.get("market") == market)]
        cur.append(
            {
                "ticker": ticker,
                "quantity": call.data["quantity"],
                "avg_price": call.data["avg_price"],
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
        ticker = call.data["ticker"]
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
