"""Config flow + options flow for KR Finance Kit.

Single-step layout: one form captures everything (tickers, OpenDart key,
toggles). The same KR ticker list feeds both price sensors (via yfinance)
and disclosure binary_sensors (via the OpenDart resolver) — we removed
the separate "stock_codes for disclosure" field because typing the same
codes twice was a recurring source of confusion.

Holdings (quantity + average price) stay out of the flow on purpose —
those land via the ``add_position`` service so they're never serialized
into ``entry.data`` until the user explicitly chooses to add them.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api.opendart import resolve_corp_codes_by_stock, validate_api_key
from .const import (
    CONF_DISCLOSURE_CORP_CODES,
    CONF_INCLUDE_FX,
    CONF_INCLUDE_INDICES,
    CONF_KR_TICKERS,
    CONF_OPENDART_API_KEY,
    CONF_POSITIONS,
    CONF_US_TICKERS,
    DOMAIN,
)


def _csv_to_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def _list_to_csv(items: list[str] | None) -> str:
    return ", ".join(items or [])


async def _resolve_corp_codes_for_kr_tickers(
    hass, api_key: str, kr_tickers: list[str]
) -> list[str]:
    """Map the user's KR tickers to OpenDart corp_codes.

    Only the 6-digit ones go through the resolver (``.KQ``-suffixed codes
    still resolve — we strip the suffix). Returns the deduped list of
    corp_codes; empty when no key or no tickers.
    """
    if not api_key or not kr_tickers:
        return []
    stock_codes = []
    for t in kr_tickers:
        bare = t.split(".")[0]  # 005930 / 035720.KQ → 005930 / 035720
        if bare.isdigit() and len(bare) == 6:
            stock_codes.append(bare)
    if not stock_codes:
        return []
    resolved = await resolve_corp_codes_by_stock(hass, api_key, stock_codes)
    return list(dict.fromkeys(resolved.values()))  # preserve insertion order


class KRFinanceKitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = (user_input.get(CONF_OPENDART_API_KEY) or "").strip()
            kr = _csv_to_list(user_input.get(CONF_KR_TICKERS))
            us = _csv_to_list(user_input.get(CONF_US_TICKERS))

            if api_key and not await validate_api_key(self.hass, api_key):
                errors[CONF_OPENDART_API_KEY] = "invalid_api_key"
            else:
                corp_codes = await _resolve_corp_codes_for_kr_tickers(
                    self.hass, api_key, kr
                )
                return self.async_create_entry(
                    title="KR Finance Kit",
                    data={
                        CONF_KR_TICKERS: kr,
                        CONF_US_TICKERS: us,
                        CONF_OPENDART_API_KEY: api_key,
                        CONF_DISCLOSURE_CORP_CODES: corp_codes,
                        CONF_INCLUDE_INDICES: user_input.get(CONF_INCLUDE_INDICES, True),
                        CONF_INCLUDE_FX: user_input.get(CONF_INCLUDE_FX, True),
                        CONF_POSITIONS: [],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_OPENDART_API_KEY, default=""): str,
                    vol.Optional(CONF_KR_TICKERS, default=""): str,
                    vol.Optional(CONF_US_TICKERS, default=""): str,
                    vol.Optional(CONF_INCLUDE_INDICES, default=True): bool,
                    vol.Optional(CONF_INCLUDE_FX, default=True): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "KRFinanceKitOptionsFlow":
        return KRFinanceKitOptionsFlow(config_entry)


class KRFinanceKitOptionsFlow(config_entries.OptionsFlow):
    """Lets the user edit tickers/keys without removing the entry."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    def _current(self, key: str, default: Any = None) -> Any:
        return (self._entry.options or self._entry.data).get(key, default)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = (user_input.get(CONF_OPENDART_API_KEY) or "").strip()
            kr = _csv_to_list(user_input.get(CONF_KR_TICKERS))
            us = _csv_to_list(user_input.get(CONF_US_TICKERS))

            if api_key and not await validate_api_key(self.hass, api_key):
                errors[CONF_OPENDART_API_KEY] = "invalid_api_key"
            else:
                corp_codes = await _resolve_corp_codes_for_kr_tickers(
                    self.hass, api_key, kr
                )
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_KR_TICKERS: kr,
                        CONF_US_TICKERS: us,
                        CONF_OPENDART_API_KEY: api_key,
                        CONF_DISCLOSURE_CORP_CODES: corp_codes,
                        CONF_INCLUDE_INDICES: user_input.get(CONF_INCLUDE_INDICES, True),
                        CONF_INCLUDE_FX: user_input.get(CONF_INCLUDE_FX, True),
                        # Holdings are service-managed; keep whatever we already have.
                        CONF_POSITIONS: self._current(CONF_POSITIONS, []),
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_OPENDART_API_KEY,
                        default=self._current(CONF_OPENDART_API_KEY, ""),
                    ): str,
                    vol.Optional(
                        CONF_KR_TICKERS,
                        default=_list_to_csv(self._current(CONF_KR_TICKERS, [])),
                    ): str,
                    vol.Optional(
                        CONF_US_TICKERS,
                        default=_list_to_csv(self._current(CONF_US_TICKERS, [])),
                    ): str,
                    vol.Optional(
                        CONF_INCLUDE_INDICES,
                        default=self._current(CONF_INCLUDE_INDICES, True),
                    ): bool,
                    vol.Optional(
                        CONF_INCLUDE_FX,
                        default=self._current(CONF_INCLUDE_FX, True),
                    ): bool,
                }
            ),
            errors=errors,
        )
