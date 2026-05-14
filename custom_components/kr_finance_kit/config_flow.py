"""Config flow + options flow for KR Finance Kit.

Single-step layout: one form captures everything (tickers, OpenDart key,
toggles). The same KR ticker list feeds both price sensors (via yfinance)
and disclosure binary_sensors (via the OpenDart resolver) — we removed
the separate "stock_codes for disclosure" field because typing the same
codes twice was a recurring source of confusion.

Holdings (quantity + average price) stay out of the flow on purpose —
those land via the ``add_position`` service so they're never serialized
into ``entry.data`` until the user explicitly chooses to add them.

Form pre-fill uses ``add_suggested_values_to_schema`` so the input boxes
arrive populated with the user's current values (Options flow) or the
last-attempted values (Config flow after a validation error). The plain
``vol.Optional(..., default=...)`` only kicks in when the user submits a
field blank; HA does not surface schema defaults as input placeholders.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api.opendart import (
    resolve_corp_codes_by_stock,
    resolve_kr_ticker_names,
    validate_api_key,
)
from .const import (
    CONF_DISCLOSURE_CORP_CODES,
    CONF_INCLUDE_DETAILED_ATTRS,
    CONF_INCLUDE_FX,
    CONF_INCLUDE_INDICES,
    CONF_INCLUDE_US_INDICES,
    CONF_KR_TICKER_NAMES,
    CONF_KR_TICKERS,
    CONF_OPENDART_API_KEY,
    CONF_OTHER_TICKERS,
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


def _kr_tickers_to_stock_codes(kr_tickers: list[str]) -> list[str]:
    """Strip ``.KS``/``.KQ`` suffixes and keep only 6-digit listed-equity codes."""
    out: list[str] = []
    for t in kr_tickers:
        bare = t.split(".")[0]
        if bare.isdigit() and len(bare) == 6:
            out.append(bare)
    return out


async def _enrich_kr_metadata(
    hass, api_key: str, kr_tickers: list[str]
) -> tuple[list[str], dict[str, str]]:
    """Resolve OpenDart corp_codes and Korean names for the user's KR tickers.

    Both projections share the same cached corpCode.xml download, so this
    is a single network round-trip (or zero, if cached). Returns
    ``(corp_codes, names)`` where ``names`` maps the user's input string
    (post-uppercase, including any ``.KS``/``.KQ`` suffix) to a Korean
    company name.
    """
    if not api_key or not kr_tickers:
        return [], {}
    stock_codes = _kr_tickers_to_stock_codes(kr_tickers)
    if not stock_codes:
        return [], {}
    corp_map = await resolve_corp_codes_by_stock(hass, api_key, stock_codes)
    name_map = await resolve_kr_ticker_names(hass, api_key, stock_codes)
    corp_codes = list(dict.fromkeys(corp_map.values()))  # preserve order, dedupe

    # Re-key names by the original user input so sensors can look up by
    # exactly what the user typed (e.g. "035720.KQ" → "카카오").
    keyed: dict[str, str] = {}
    for ticker in kr_tickers:
        bare = ticker.split(".")[0]
        if bare in name_map:
            keyed[ticker] = name_map[bare]
    return corp_codes, keyed


# Shared schema for both Config Flow's user step and Options Flow's init
# step — they accept the same fields. We keep it free of ``default=``
# values because pre-filling is handled separately via
# ``add_suggested_values_to_schema`` (defaults only apply on submit-with-
# blank, which would silently wipe values across reloads).
_FORM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_OPENDART_API_KEY): str,
        vol.Optional(CONF_KR_TICKERS): str,
        vol.Optional(CONF_US_TICKERS): str,
        vol.Optional(CONF_OTHER_TICKERS): str,
        vol.Optional(CONF_INCLUDE_INDICES, default=True): bool,
        vol.Optional(CONF_INCLUDE_US_INDICES, default=True): bool,
        vol.Optional(CONF_INCLUDE_FX, default=True): bool,
        vol.Optional(CONF_INCLUDE_DETAILED_ATTRS, default=False): bool,
    }
)

# URLs are injected via description_placeholders rather than embedded
# directly in the translation strings — hassfest rejects raw URLs inside
# translations, but the {placeholder} substitution path is allowed and
# renders as a clickable markdown link in the HA UI.
_LINK_PLACEHOLDERS = {
    "opendart_signup_url": "https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do",
    "opendart_key_url": "https://opendart.fss.or.kr/mng/apiUseStusUser.do",
    "krx_search_url": "https://kind.krx.co.kr/corpgeneral/corpList.do?method=loadInitPage",
    "naver_finance_url": "https://finance.naver.com/sise/sise_market_sum.naver",
    "yahoo_finance_url": "https://finance.yahoo.com/lookup",
}


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
            other = _csv_to_list(user_input.get(CONF_OTHER_TICKERS))

            if api_key and not await validate_api_key(self.hass, api_key):
                errors[CONF_OPENDART_API_KEY] = "invalid_api_key"
            else:
                corp_codes, ticker_names = await _enrich_kr_metadata(
                    self.hass, api_key, kr
                )
                return self.async_create_entry(
                    title="KR Finance Kit",
                    data={
                        CONF_KR_TICKERS: kr,
                        CONF_US_TICKERS: us,
                        CONF_OTHER_TICKERS: other,
                        CONF_OPENDART_API_KEY: api_key,
                        CONF_DISCLOSURE_CORP_CODES: corp_codes,
                        CONF_KR_TICKER_NAMES: ticker_names,
                        CONF_INCLUDE_INDICES: user_input.get(CONF_INCLUDE_INDICES, True),
                        CONF_INCLUDE_US_INDICES: user_input.get(CONF_INCLUDE_US_INDICES, True),
                        CONF_INCLUDE_FX: user_input.get(CONF_INCLUDE_FX, True),
                        CONF_INCLUDE_DETAILED_ATTRS: user_input.get(CONF_INCLUDE_DETAILED_ATTRS, False),
                        CONF_POSITIONS: [],
                    },
                )

        # On a validation error we re-render the form pre-filled with what
        # the user just typed (rather than blanks) so they only have to
        # tweak the offending field. First-time visit has no user_input,
        # so the form arrives empty as expected.
        suggested = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_FORM_SCHEMA, suggested),
            description_placeholders=_LINK_PLACEHOLDERS,
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
            other = _csv_to_list(user_input.get(CONF_OTHER_TICKERS))

            if api_key and not await validate_api_key(self.hass, api_key):
                errors[CONF_OPENDART_API_KEY] = "invalid_api_key"
            else:
                corp_codes, ticker_names = await _enrich_kr_metadata(
                    self.hass, api_key, kr
                )
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_KR_TICKERS: kr,
                        CONF_US_TICKERS: us,
                        CONF_OTHER_TICKERS: other,
                        CONF_OPENDART_API_KEY: api_key,
                        CONF_DISCLOSURE_CORP_CODES: corp_codes,
                        CONF_KR_TICKER_NAMES: ticker_names,
                        CONF_INCLUDE_INDICES: user_input.get(CONF_INCLUDE_INDICES, True),
                        CONF_INCLUDE_US_INDICES: user_input.get(CONF_INCLUDE_US_INDICES, True),
                        CONF_INCLUDE_FX: user_input.get(CONF_INCLUDE_FX, True),
                        CONF_INCLUDE_DETAILED_ATTRS: user_input.get(CONF_INCLUDE_DETAILED_ATTRS, False),
                        # Holdings are service-managed; keep whatever we already have.
                        CONF_POSITIONS: self._current(CONF_POSITIONS, []),
                    },
                )

        # Pre-fill with whatever the user just typed (if they're returning
        # after a validation error) or the currently-saved values
        # (first visit). add_suggested_values_to_schema is the HA-blessed
        # way to populate input boxes — schema defaults don't show up in
        # the UI by themselves.
        suggested = user_input if user_input is not None else {
            CONF_OPENDART_API_KEY: self._current(CONF_OPENDART_API_KEY, ""),
            CONF_KR_TICKERS: _list_to_csv(self._current(CONF_KR_TICKERS, [])),
            CONF_US_TICKERS: _list_to_csv(self._current(CONF_US_TICKERS, [])),
            CONF_OTHER_TICKERS: _list_to_csv(self._current(CONF_OTHER_TICKERS, [])),
            CONF_INCLUDE_INDICES: self._current(CONF_INCLUDE_INDICES, True),
            CONF_INCLUDE_US_INDICES: self._current(CONF_INCLUDE_US_INDICES, True),
            CONF_INCLUDE_FX: self._current(CONF_INCLUDE_FX, True),
            CONF_INCLUDE_DETAILED_ATTRS: self._current(CONF_INCLUDE_DETAILED_ATTRS, False),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(_FORM_SCHEMA, suggested),
            description_placeholders=_LINK_PLACEHOLDERS,
            errors=errors,
        )
