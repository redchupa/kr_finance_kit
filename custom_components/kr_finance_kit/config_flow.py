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
from homeassistant.helpers import config_validation as cv

from .api.opendart import (
    resolve_corp_codes_by_stock,
    resolve_kr_ticker_names,
    validate_api_key,
)
from .const import (
    CONF_DISCLOSURE_CATEGORIES,
    CONF_DISCLOSURE_CORP_CODES,
    CONF_DISCLOSURE_CORP_NAMES,
    CONF_INCLUDE_DETAILED_ATTRS,
    CONF_INCLUDE_FX,
    CONF_INCLUDE_GLOBAL_INDICES,
    CONF_INCLUDE_INDICES,
    CONF_INCLUDE_US_INDICES,
    CONF_KR_TICKER_NAMES,
    CONF_KR_TICKERS,
    CONF_OPENDART_API_KEY,
    CONF_OTHER_TICKER_LABELS,
    CONF_OTHER_TICKERS,
    CONF_PORTFOLIO_PL_ALERT_PCT,
    CONF_POSITIONS,
    CONF_TARGET_CURRENCY_KRW,
    CONF_US_TICKER_LABELS,
    CONF_US_TICKERS,
    DISCLOSURE_CATEGORY_CODES,
    DOMAIN,
)


def _csv_to_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def _list_to_csv(items: list[str] | None) -> str:
    return ", ".join(items or [])


def _csv_to_tickers_and_labels(raw: str | None) -> tuple[list[str], dict[str, str]]:
    """Parse a "TICKER:label, TICKER, TICKER:라벨" input.

    Splits on the first colon per segment so multi-symbol tickers that
    happen to contain "=" (FX: EUR=X) and "-" (crypto: BTC-USD) pass
    through untouched. Returns ``(tickers, labels)`` where ``labels``
    maps the upper-cased ticker code to its user-supplied friendly
    label. Tickers without an explicit ":label" are still in the
    ``tickers`` list but absent from ``labels`` — the integration will
    fill those in from yfinance .info on save.
    """
    if not raw:
        return [], {}
    tickers: list[str] = []
    labels: dict[str, str] = {}
    for raw_seg in raw.split(","):
        seg = raw_seg.strip()
        if not seg:
            continue
        if ":" in seg:
            code, _, lbl = seg.partition(":")
            code = code.strip().upper()
            lbl = lbl.strip()
            if not code:
                continue
            tickers.append(code)
            if lbl:
                labels[code] = lbl
        else:
            tickers.append(seg.upper())
    return tickers, labels


def _serialize_tickers_with_labels(tickers: list[str] | None, labels: dict[str, str] | None) -> str:
    """Render Options-flow pre-fill so the user sees what they typed.

    Only labels the user explicitly supplied are surfaced — auto-fetched
    longNames stay invisible so the screen looks the same as the last
    submission. Edits to the visible label override; deleting the
    ":label" segment frees the slot for the next yfinance fetch.
    """
    if not tickers:
        return ""
    out: list[str] = []
    labels = labels or {}
    for t in tickers:
        lbl = labels.get(t)
        out.append(f"{t}:{lbl}" if lbl else t)
    return ", ".join(out)


async def _enrich_other_labels(
    hass,
    tickers: list[str],
    explicit_labels: dict[str, str],
) -> dict[str, str]:
    """Auto-fill missing labels from yfinance .info longName / shortName.

    Mirrors the KR path's _enrich_kr_metadata: one network round-trip on
    save, no per-poll overhead. We only fetch for tickers the user
    didn't already label, so toggling an existing entry costs zero
    requests.
    """
    missing = [t for t in tickers if t not in explicit_labels]
    if not missing:
        return dict(explicit_labels)
    from .api import yfinance_wrap
    raw = await yfinance_wrap.fetch_info(missing)
    out = dict(explicit_labels)
    for t in missing:
        info = raw.get(t, {}) or {}
        ln = info.get("longName") or info.get("shortName")
        if ln:
            out[t] = ln
    return out


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
) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """Resolve OpenDart corp_codes and Korean names for the user's KR tickers.

    All three projections share the same cached corpCode.xml download —
    one network round-trip (or zero, if cached). Returns
    ``(corp_codes, ticker_names, corp_names)``:

    - ``corp_codes``: list[str] of unique 8-digit OpenDart corp codes
      driving the disclosure binary_sensors.
    - ``ticker_names``: dict[user_input_ticker → corp_name] feeding the
      price-sensor friendly name (e.g. "035720.KQ" → "카카오").
    - ``corp_names``: dict[corp_code → corp_name] feeding the disclosure
      binary_sensor's device label so users see "삼성전자 신규 공시"
      instead of "공시 00126380".
    """
    if not api_key or not kr_tickers:
        return [], {}, {}
    stock_codes = _kr_tickers_to_stock_codes(kr_tickers)
    if not stock_codes:
        return [], {}, {}
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

    # Build corp_code → corp_name so disclosure binary_sensors can label
    # themselves with the human-readable company name. Both maps are keyed
    # by the same stock_code, so a single zip-style merge gives us what
    # the binary_sensor platform needs.
    corp_names_by_code: dict[str, str] = {}
    for stock, corp in corp_map.items():
        nm = name_map.get(stock)
        if nm:
            corp_names_by_code[corp] = nm
    return corp_codes, keyed, corp_names_by_code


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
        vol.Optional(CONF_INCLUDE_GLOBAL_INDICES, default=False): bool,
        vol.Optional(CONF_INCLUDE_FX, default=True): bool,
        vol.Optional(CONF_INCLUDE_DETAILED_ATTRS, default=False): bool,
        vol.Optional(CONF_TARGET_CURRENCY_KRW, default=False): bool,
        vol.Optional(CONF_PORTFOLIO_PL_ALERT_PCT, default=0): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
        vol.Optional(CONF_DISCLOSURE_CATEGORIES, default=[]): vol.All(
            cv.ensure_list,
            [vol.In(list(DISCLOSURE_CATEGORY_CODES))],
        ),
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
            us, us_labels_explicit = _csv_to_tickers_and_labels(user_input.get(CONF_US_TICKERS))
            other, other_labels_explicit = _csv_to_tickers_and_labels(
                user_input.get(CONF_OTHER_TICKERS)
            )

            if api_key and not await validate_api_key(self.hass, api_key):
                errors[CONF_OPENDART_API_KEY] = "invalid_api_key"
            else:
                corp_codes, ticker_names, corp_names = await _enrich_kr_metadata(
                    self.hass, api_key, kr
                )
                us_labels = await _enrich_other_labels(self.hass, us, us_labels_explicit)
                other_labels = await _enrich_other_labels(self.hass, other, other_labels_explicit)
                return self.async_create_entry(
                    title="KR Finance Kit",
                    data={
                        CONF_KR_TICKERS: kr,
                        CONF_US_TICKERS: us,
                        CONF_OTHER_TICKERS: other,
                        CONF_US_TICKER_LABELS: us_labels,
                        CONF_OTHER_TICKER_LABELS: other_labels,
                        CONF_OPENDART_API_KEY: api_key,
                        CONF_DISCLOSURE_CORP_CODES: corp_codes,
                        CONF_DISCLOSURE_CORP_NAMES: corp_names,
                        CONF_KR_TICKER_NAMES: ticker_names,
                        CONF_INCLUDE_INDICES: user_input.get(CONF_INCLUDE_INDICES, True),
                        CONF_INCLUDE_US_INDICES: user_input.get(CONF_INCLUDE_US_INDICES, True),
                        CONF_INCLUDE_GLOBAL_INDICES: user_input.get(CONF_INCLUDE_GLOBAL_INDICES, False),
                        CONF_INCLUDE_FX: user_input.get(CONF_INCLUDE_FX, True),
                        CONF_INCLUDE_DETAILED_ATTRS: user_input.get(CONF_INCLUDE_DETAILED_ATTRS, False),
                        CONF_TARGET_CURRENCY_KRW: user_input.get(CONF_TARGET_CURRENCY_KRW, False),
                        CONF_PORTFOLIO_PL_ALERT_PCT: user_input.get(CONF_PORTFOLIO_PL_ALERT_PCT, 0),
                        CONF_DISCLOSURE_CATEGORIES: user_input.get(CONF_DISCLOSURE_CATEGORIES, []),
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
            us, us_labels_explicit = _csv_to_tickers_and_labels(user_input.get(CONF_US_TICKERS))
            other, other_labels_explicit = _csv_to_tickers_and_labels(
                user_input.get(CONF_OTHER_TICKERS)
            )

            if api_key and not await validate_api_key(self.hass, api_key):
                errors[CONF_OPENDART_API_KEY] = "invalid_api_key"
            else:
                corp_codes, ticker_names, corp_names = await _enrich_kr_metadata(
                    self.hass, api_key, kr
                )
                us_labels = await _enrich_other_labels(self.hass, us, us_labels_explicit)
                other_labels = await _enrich_other_labels(self.hass, other, other_labels_explicit)
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_KR_TICKERS: kr,
                        CONF_US_TICKERS: us,
                        CONF_OTHER_TICKERS: other,
                        CONF_US_TICKER_LABELS: us_labels,
                        CONF_OTHER_TICKER_LABELS: other_labels,
                        CONF_OPENDART_API_KEY: api_key,
                        CONF_DISCLOSURE_CORP_CODES: corp_codes,
                        CONF_DISCLOSURE_CORP_NAMES: corp_names,
                        CONF_KR_TICKER_NAMES: ticker_names,
                        CONF_INCLUDE_INDICES: user_input.get(CONF_INCLUDE_INDICES, True),
                        CONF_INCLUDE_US_INDICES: user_input.get(CONF_INCLUDE_US_INDICES, True),
                        CONF_INCLUDE_GLOBAL_INDICES: user_input.get(CONF_INCLUDE_GLOBAL_INDICES, False),
                        CONF_INCLUDE_FX: user_input.get(CONF_INCLUDE_FX, True),
                        CONF_INCLUDE_DETAILED_ATTRS: user_input.get(CONF_INCLUDE_DETAILED_ATTRS, False),
                        CONF_TARGET_CURRENCY_KRW: user_input.get(CONF_TARGET_CURRENCY_KRW, False),
                        CONF_PORTFOLIO_PL_ALERT_PCT: user_input.get(CONF_PORTFOLIO_PL_ALERT_PCT, 0),
                        CONF_DISCLOSURE_CATEGORIES: user_input.get(CONF_DISCLOSURE_CATEGORIES, []),
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
            CONF_US_TICKERS: _serialize_tickers_with_labels(
                self._current(CONF_US_TICKERS, []),
                self._current(CONF_US_TICKER_LABELS, {}),
            ),
            CONF_OTHER_TICKERS: _serialize_tickers_with_labels(
                self._current(CONF_OTHER_TICKERS, []),
                self._current(CONF_OTHER_TICKER_LABELS, {}),
            ),
            CONF_INCLUDE_INDICES: self._current(CONF_INCLUDE_INDICES, True),
            CONF_INCLUDE_US_INDICES: self._current(CONF_INCLUDE_US_INDICES, True),
            CONF_INCLUDE_GLOBAL_INDICES: self._current(CONF_INCLUDE_GLOBAL_INDICES, False),
            CONF_INCLUDE_FX: self._current(CONF_INCLUDE_FX, True),
            CONF_INCLUDE_DETAILED_ATTRS: self._current(CONF_INCLUDE_DETAILED_ATTRS, False),
            CONF_TARGET_CURRENCY_KRW: self._current(CONF_TARGET_CURRENCY_KRW, False),
            CONF_PORTFOLIO_PL_ALERT_PCT: self._current(CONF_PORTFOLIO_PL_ALERT_PCT, 0),
            CONF_DISCLOSURE_CATEGORIES: self._current(CONF_DISCLOSURE_CATEGORIES, []),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(_FORM_SCHEMA, suggested),
            description_placeholders=_LINK_PLACEHOLDERS,
            errors=errors,
        )
