"""Config flow + options flow for KR Finance Kit.

A short menu lets the user configure each piece independently and revisit
it later via the Options flow. We keep all financial-private inputs
(holdings quantity/avg price) **out** of the Config Flow on purpose —
those land via the ``add_position`` service so they're never serialized
into ``entry.data`` until the user is ready.
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


class KRFinanceKitConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {
            CONF_KR_TICKERS: [],
            CONF_US_TICKERS: [],
            CONF_DISCLOSURE_CORP_CODES: [],
            CONF_OPENDART_API_KEY: "",
            CONF_INCLUDE_INDICES: True,
            CONF_INCLUDE_FX: True,
            CONF_POSITIONS: [],
        }

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await self.async_step_tickers()

    async def async_step_tickers(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data[CONF_KR_TICKERS] = _csv_to_list(user_input.get(CONF_KR_TICKERS))
            self._data[CONF_US_TICKERS] = _csv_to_list(user_input.get(CONF_US_TICKERS))
            self._data[CONF_INCLUDE_INDICES] = user_input.get(CONF_INCLUDE_INDICES, True)
            self._data[CONF_INCLUDE_FX] = user_input.get(CONF_INCLUDE_FX, True)
            return await self.async_step_disclosures()
        return self.async_show_form(
            step_id="tickers",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_KR_TICKERS, default=""): str,
                    vol.Optional(CONF_US_TICKERS, default=""): str,
                    vol.Optional(CONF_INCLUDE_INDICES, default=True): bool,
                    vol.Optional(CONF_INCLUDE_FX, default=True): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_disclosures(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = (user_input.get(CONF_OPENDART_API_KEY) or "").strip()
            explicit_corp_codes = _csv_to_list(user_input.get(CONF_DISCLOSURE_CORP_CODES))
            stock_codes = _csv_to_list(user_input.get("disclosure_stock_codes"))

            if api_key and not await validate_api_key(self.hass, api_key):
                errors[CONF_OPENDART_API_KEY] = "invalid_api_key"
            else:
                resolved: dict[str, str] = {}
                if api_key and stock_codes:
                    resolved = await resolve_corp_codes_by_stock(
                        self.hass, api_key, stock_codes
                    )
                # Merge explicit corp_codes with resolved-from-stock_codes, dedupe.
                merged = list({*explicit_corp_codes, *resolved.values()})

                self._data[CONF_OPENDART_API_KEY] = api_key
                self._data[CONF_DISCLOSURE_CORP_CODES] = merged
                return self.async_create_entry(title="KR Finance Kit", data=self._data)
        return self.async_show_form(
            step_id="disclosures",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_OPENDART_API_KEY, default=""): str,
                    vol.Optional("disclosure_stock_codes", default=""): str,
                    vol.Optional(CONF_DISCLOSURE_CORP_CODES, default=""): str,
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
            if api_key and not await validate_api_key(self.hass, api_key):
                errors[CONF_OPENDART_API_KEY] = "invalid_api_key"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_KR_TICKERS: _csv_to_list(user_input.get(CONF_KR_TICKERS)),
                        CONF_US_TICKERS: _csv_to_list(user_input.get(CONF_US_TICKERS)),
                        CONF_DISCLOSURE_CORP_CODES: _csv_to_list(
                            user_input.get(CONF_DISCLOSURE_CORP_CODES)
                        ),
                        CONF_OPENDART_API_KEY: api_key,
                        CONF_INCLUDE_INDICES: user_input.get(CONF_INCLUDE_INDICES, True),
                        CONF_INCLUDE_FX: user_input.get(CONF_INCLUDE_FX, True),
                        # Holdings are managed via service, not options UI.
                        CONF_POSITIONS: self._current(CONF_POSITIONS, []),
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_KR_TICKERS,
                        default=_list_to_csv(self._current(CONF_KR_TICKERS, [])),
                    ): str,
                    vol.Optional(
                        CONF_US_TICKERS,
                        default=_list_to_csv(self._current(CONF_US_TICKERS, [])),
                    ): str,
                    vol.Optional(
                        CONF_DISCLOSURE_CORP_CODES,
                        default=_list_to_csv(self._current(CONF_DISCLOSURE_CORP_CODES, [])),
                    ): str,
                    vol.Optional(
                        CONF_OPENDART_API_KEY,
                        default=self._current(CONF_OPENDART_API_KEY, ""),
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
