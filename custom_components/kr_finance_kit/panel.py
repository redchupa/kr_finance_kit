"""Sidebar panel — static JS, panel registration, websocket API.

Lifecycle:

- Static path + websocket commands are registered once per HA process
  (neither can be unregistered, so we guard with flags).
- The sidebar panel is registered on setup and survives entry reloads
  (adding a ticker from the panel reloads the entry — removing the
  panel there would make the open page flicker). It is removed only in
  ``async_remove_entry`` when the user deletes the integration.

All business logic lives in ``panel_data`` (HA-free, unit-tested).
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from . import panel_data as pd
from .access import can_read_holdings
from .credentials import unseal
from .api.pacing import Backoff, ProviderBusy, gate
from .api import yfinance_wrap
from .api.yfinance_wrap import FX_TICKERS, INDEX_TICKERS, normalize_kr_ticker
from .const import (
    CONF_DISCLOSURE_CORP_CODES,
    CONF_DISCLOSURE_CORP_NAMES,
    CONF_INCLUDE_DETAILED_ATTRS,
    CONF_KR_TICKER_NAMES,
    CONF_KR_TICKERS,
    CONF_OPENDART_API_KEY,
    CONF_OTHER_TICKER_LABELS,
    CONF_POSITIONS,
    CONF_US_TICKER_LABELS,
    DOMAIN,
    LOGGER,
    MARKET_KR,
    MARKET_OTHER,
    MARKET_US,
)

PANEL_URL_PATH = "finance-kit"
PANEL_COMPONENT = "kr-finance-panel"
PANEL_TITLE = "Finance Kit"
PANEL_ICON = "mdi:finance"
STATIC_URL = "/kr_finance_kit_static"
FRONTEND_DIR = Path(__file__).parent / "frontend"

_DATA_KEY = f"{DOMAIN}_panel"
_PREFS_STORE_KEY = f"{DOMAIN}.panel_prefs"
_PREFS_VERSION = 1

# Chart cache TTL (seconds) per period — intraday ranges refresh faster.
_HISTORY_TTL = {"1d": 300, "5d": 900, "1mo": 3600, "6mo": 3600 * 6, "1y": 3600 * 12}
_HISTORY_MAX_SYMBOLS = 12
_HISTORY_CACHE_MAX = 500
_SEARCH_TTL = 600
# Corp-code map download failures (bad/expired OpenDart key) are remembered
# for this long so every search keystroke doesn't re-download the ~MB zip.
_CORP_MAP_RETRY = 600
# yfinance interpolates the symbol into the request path without encoding,
# so anything reaching it from the websocket is limited to Yahoo's symbol
# alphabet (same grammar as panel_data's watchlist validation).
_SYMBOL_RE = r"^[A-Za-z0-9^][A-Za-z0-9.\-=^]{0,23}$"


def _state(hass: HomeAssistant) -> dict[str, Any]:
    return hass.data.setdefault(
        _DATA_KEY,
        {
            "static": False,
            "ws": False,
            "panel": False,
            "history": {},
            "search": {},
            "prefs": None,
            "store": None,
        },
    )


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------

async def async_setup_panel(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register static assets, websocket API and the sidebar panel."""
    st = _state(hass)

    if not st["static"]:
        try:
            from homeassistant.components.http import StaticPathConfig

            await hass.http.async_register_static_paths(
                [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), False)]
            )
        except ImportError:  # HA < 2024.7
            hass.http.register_static_path(STATIC_URL, str(FRONTEND_DIR), False)
        st["static"] = True

    if not st["ws"]:
        for handler in (
            ws_snapshot, ws_history, ws_search, ws_catalog, ws_watchlist_add,
            ws_watchlist_remove, ws_prefs_get, ws_prefs_set,
        ):
            websocket_api.async_register_command(hass, handler)
        st["ws"] = True

    if not st["panel"]:
        from homeassistant.components import panel_custom
        from homeassistant.loader import async_get_integration

        integration = await async_get_integration(hass, DOMAIN)
        version = str(integration.version or "0")
        st["version"] = version
        try:
            await panel_custom.async_register_panel(
                hass,
                frontend_url_path=PANEL_URL_PATH,
                webcomponent_name=PANEL_COMPONENT,
                sidebar_title=PANEL_TITLE,
                sidebar_icon=PANEL_ICON,
                module_url=f"{STATIC_URL}/kr-finance-panel.js?v={version}",
                require_admin=False,
                config={"version": version},
            )
        except ValueError as err:  # already registered (e.g. dev reload)
            LOGGER.debug("Panel already registered: %s", err)
        st["panel"] = True


@callback
def async_remove_panel(hass: HomeAssistant) -> None:
    """Drop the sidebar entry (integration deleted)."""
    st = _state(hass)
    if not st["panel"]:
        return
    from homeassistant.components import frontend

    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    st["panel"] = False


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _active(hass: HomeAssistant) -> tuple[ConfigEntry | None, dict[str, Any]]:
    for entry in hass.config_entries.async_entries(DOMAIN):
        store = (hass.data.get(DOMAIN) or {}).get(entry.entry_id)
        if isinstance(store, dict) and store.get("market") is not None:
            return entry, store
    return None, {}


def _entity_ids(hass: HomeAssistant, cfg: dict[str, Any]) -> dict[str, str]:
    reg = er.async_get(hass)
    out: dict[str, str] = {}

    def lookup(key: str, unique_id: str) -> None:
        eid = reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        if eid:
            out[key] = eid

    for idx in INDEX_TICKERS:
        lookup(f"INDEX:{idx}", f"{DOMAIN}_index_{idx.lower()}")
    for pair in FX_TICKERS:
        lookup(f"FX:{pair}", f"{DOMAIN}_fx_{pair.lower()}")
    for market, key in ((MARKET_KR, "kr_tickers"), (MARKET_US, "us_tickers"), (MARKET_OTHER, "other_tickers")):
        for t in cfg.get(key, []) or []:
            lookup(f"{market}:{t}", f"{DOMAIN}_{market.lower()}_{t}")
    return out


def _yahoo_symbol(market: str, ticker: str) -> str | None:
    if market == MARKET_KR:
        return normalize_kr_ticker(ticker)
    if market == "INDEX":
        return INDEX_TICKERS.get(ticker)
    if market == "FX":
        return FX_TICKERS.get(ticker)
    if market in (MARKET_US, MARKET_OTHER):
        return ticker
    return None


async def _prefs_doc(hass: HomeAssistant) -> dict[str, Any]:
    st = _state(hass)
    if st["prefs"] is None:
        st["store"] = Store(hass, _PREFS_VERSION, _PREFS_STORE_KEY)
        loaded = await st["store"].async_load()
        st["prefs"] = loaded if isinstance(loaded, dict) else {"users": {}}
        st["prefs"].setdefault("users", {})
    return st["prefs"]


# --------------------------------------------------------------------------
# Websocket commands
# --------------------------------------------------------------------------

@websocket_api.websocket_command({vol.Required("type"): "kr_finance_kit/snapshot"})
@websocket_api.async_response
async def ws_snapshot(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    entry, store = _active(hass)
    if entry is None:
        # entry_exists → HA is still starting / reloading the integration.
        connection.send_result(msg["id"], {
            "configured": False,
            "entry_exists": bool(hass.config_entries.async_entries(DOMAIN)),
        })
        return
    cfg = pd.merged_config(entry.data, entry.options)
    market = store["market"]
    disclosure = store.get("disclosure")
    data = market.data or getattr(market, "startup_quotes", {})
    if data and data.get("positions") and not can_read_holdings(hass, connection.user):
        data = {**data, "positions": []}
    snap = pd.build_snapshot(
        data,
        cfg,
        disclosures=(disclosure.data or []) if disclosure is not None else None,
        entity_ids=_entity_ids(hass, cfg),
    )
    snap.update({
        "configured": True,
        "is_admin": bool(connection.user and connection.user.is_admin),
        "opendart": bool((cfg.get(CONF_OPENDART_API_KEY) or "").strip()),
        "detailed_attrs": bool(cfg.get(CONF_INCLUDE_DETAILED_ATTRS, False)),
        "entry_id": entry.entry_id,
        "provider_wait_minutes": {
            name: int((remaining + 59.999) // 60)
            for name in ("yahoo", "dart")
            if (remaining := gate(name).resume - time.monotonic()) > 0
        },
        "initial_sync": not bool(market.data),
        "last_update_success": bool(market.last_update_success),
        "version": _state(hass).get("version"),
    })
    connection.send_result(msg["id"], snap)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "kr_finance_kit/history",
        vol.Required("symbols"): vol.All(
            [
                {
                    vol.Required("market"): vol.In([MARKET_KR, MARKET_US, MARKET_OTHER, "INDEX", "FX"]),
                    vol.Required("ticker"): vol.All(str, vol.Match(_SYMBOL_RE)),
                }
            ],
            vol.Length(max=_HISTORY_MAX_SYMBOLS),
        ),
        vol.Optional("period", default="1mo"): vol.In(list(pd.CHART_PERIODS)),
    }
)
@websocket_api.async_response
async def ws_history(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    st = _state(hass)
    period = msg["period"]
    ttl = _HISTORY_TTL.get(period, 3600)
    cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = st["history"]
    out: dict[str, Any] = {}
    limited = False
    for item in msg["symbols"]:
        key = f"{item['market']}:{item['ticker']}"
        sym = _yahoo_symbol(item["market"], item["ticker"])
        if not sym:
            continue
        ck = (sym, period)
        hit = cache.get(ck)
        if hit and hit[0] > time.monotonic():
            out[key] = hit[1]
            continue
        try:
            series = await yfinance_wrap.fetch_history(sym, period)
        except (Backoff, ProviderBusy):
            limited = True
            break
        if len(cache) >= _HISTORY_CACHE_MAX:
            cache.clear()
        cache[ck] = (time.monotonic() + ttl, series)
        out[key] = series
    connection.send_result(msg["id"], {"period": period, "series": out, "limited": limited})


async def _get_corp_map_cached(
    hass: HomeAssistant, api_key: str
) -> dict[str, tuple[str, str]]:
    """Load OpenDart corp_code map with negative-cache guard."""
    if not api_key:
        return {}
    st = _state(hass)
    if st.get("corp_map_failed_until", 0) >= time.monotonic():
        return {}
    try:
        from .api.opendart import _load_corp_code_map

        mapping = await _load_corp_code_map(hass, api_key)
        if not mapping:
            st["corp_map_failed_until"] = time.monotonic() + _CORP_MAP_RETRY
            return {}
        return mapping
    except Exception as err:  # noqa: BLE001
        st["corp_map_failed_until"] = time.monotonic() + _CORP_MAP_RETRY
        LOGGER.debug("KR company map load failed: %s", err)
        return {}


@websocket_api.websocket_command(
    {
        vol.Required("type"): "kr_finance_kit/catalog",
        vol.Optional("market", default=MARKET_KR): vol.In(list(pd.PANEL_MARKETS)),
        vol.Optional("category", default="all"): vol.All(str, vol.Length(max=24)),
        vol.Optional("lang", default="ko"): vol.In(list(pd.SUPPORTED_LANGS)),
        vol.Optional("query", default=""): vol.All(str, vol.Length(max=40)),
        vol.Optional("limit", default=80): vol.All(int, vol.Range(min=1, max=150)),
    }
)
@websocket_api.async_response
async def ws_catalog(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    """Return browsable symbol catalog, categories, and code-lookup URLs."""
    market = msg["market"]
    extra_kr_map: dict[str, tuple[str, str]] | None = None
    if market == MARKET_KR:
        entry, _store = _active(hass)
        cfg = pd.merged_config(entry.data, entry.options) if entry else {}
        api_key = await unseal(hass, cfg.get(CONF_OPENDART_API_KEY))
        if api_key:
            extra_kr_map = await _get_corp_map_cached(hass, api_key)
    payload = pd.catalog_for_market(
        market,
        category=msg["category"],
        lang=msg["lang"],
        query=msg["query"],
        extra_kr_map=extra_kr_map,
        limit=msg["limit"],
    )
    connection.send_result(msg["id"], payload)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "kr_finance_kit/search",
        vol.Required("query"): vol.All(str, vol.Length(min=1, max=40)),
        vol.Optional("lang", default="ko"): vol.In(list(pd.SUPPORTED_LANGS)),
    }
)
@websocket_api.async_response
async def ws_search(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    query = msg["query"].strip()
    lang = msg.get("lang", "ko")
    st = _state(hass)
    cache_key = f"{lang}:{query.lower()}"
    hit = st["search"].get(cache_key)
    if hit and hit[0] > time.monotonic():
        connection.send_result(msg["id"], {"results": hit[1]})
        return

    results: list[dict[str, Any]] = []
    entry, _store = _active(hass)
    cfg = pd.merged_config(entry.data, entry.options) if entry else {}
    api_key = await unseal(hass, cfg.get(CONF_OPENDART_API_KEY))
    if api_key:
        mapping = await _get_corp_map_cached(hass, api_key)
        if mapping:
            results.extend(pd.match_kr_companies(mapping, query, limit=6))
    limited = False
    try:
        yahoo_hits = await yfinance_wrap.search_symbols(query, limit=8)
    except (Backoff, ProviderBusy):
        limited = True
        yahoo_hits = []

    seen = {(r["market"], r["symbol"]) for r in results}
    # Curated catalog matches provide instant Korean/English lookup even
    # without an OpenDart API key (Yahoo Search does not index Korean names).
    for cat_row in pd.match_catalog(query, lang=lang, limit=8):
        key = (cat_row["market"], cat_row["symbol"])
        if key in seen:
            continue
        seen.add(key)
        results.append(cat_row)

    for hit_row in yahoo_hits:
        market, ticker = pd.classify_search_hit(hit_row["symbol"], hit_row["quote_type"])
        if market == MARKET_KR:
            ticker = ticker[:-3] if ticker.endswith(".KS") else ticker
        key = (market, ticker)
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "symbol": ticker,
            "name": hit_row["name"],
            "exchange": hit_row["exchange"],
            "market": market,
        })
    if len(st["search"]) > 200:
        st["search"].clear()
    if not limited:
        st["search"][cache_key] = (time.monotonic() + _SEARCH_TTL, results)
    payload = {"results": results}
    if limited:
        payload["limited"] = True
    connection.send_result(msg["id"], payload)


def _commit_watchlist(hass, entry, original, original_options, proposed, *, removing):
    current = pd.merged_config(entry.data, entry.options)
    changes = {k: v for k, v in proposed.items() if original_options.get(k) != v}
    guarded = set(changes) | {CONF_OPENDART_API_KEY}
    if removing:
        guarded.add(CONF_POSITIONS)
    if any(current.get(k) != original.get(k) for k in guarded):
        return False
    hass.config_entries.async_update_entry(entry, options={**entry.options, **changes})
    return True


@websocket_api.websocket_command(
    {
        vol.Required("type"): "kr_finance_kit/watchlist/add",
        vol.Required("market"): vol.In(list(pd.PANEL_MARKETS)),
        vol.Required("ticker"): vol.All(str, vol.Length(min=1, max=24)),
        vol.Optional("quote"): vol.All(str, vol.Length(max=5)),
        vol.Optional("label"): vol.All(str, vol.Length(max=60)),
        vol.Optional("force", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_watchlist_add(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    async with _state(hass).setdefault("watchlist_lock", asyncio.Lock()):
        await _watchlist_add(hass, connection, msg)


async def _watchlist_add(hass, connection, msg) -> None:
    entry, _store = _active(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_configured", "Integration is not loaded")
        return
    try:
        market, ticker = pd.normalize_watch_input(msg["market"], msg["ticker"], msg.get("quote"))
        original_options = dict(entry.options)
        cfg = pd.merged_config(entry.data, entry.options)
        if market == MARKET_KR:
            wanted = normalize_kr_ticker(ticker)
            if any(normalize_kr_ticker(t) == wanted for t in cfg.get(CONF_KR_TICKERS, []) or []):
                raise pd.WatchlistError("duplicate")
        new_options = pd.watchlist_add(entry.data, entry.options, market, ticker, msg.get("label"))
    except pd.WatchlistError as err:
        connection.send_error(msg["id"], err.code, err.code)
        return

    # Probe Yahoo once so a typo doesn't leave a permanently
    # "unavailable" sensor behind. The panel can retry with force=True
    # (e.g. a KR stock before the first trading day after listing).
    if not msg["force"]:
        try:
            probe = await yfinance_wrap.fetch_quotes([ticker], market)
        except (Backoff, ProviderBusy):
            connection.send_error(msg["id"], "provider_busy", "Market data temporarily unavailable")
            return
        if not (probe.get(ticker) or {}).get("price"):
            connection.send_error(msg["id"], "no_quote", "No price data for this symbol")
            return

    # Enrichment mirrors the options flow: Korean company names + OpenDart
    # corp codes for KR, Yahoo longName for everything else.
    from .config_flow import _enrich_kr_metadata, _enrich_other_labels

    try:
        if market == MARKET_KR:
            api_key = await unseal(hass, cfg.get(CONF_OPENDART_API_KEY))
            if api_key:
                kr_all = list(new_options.get(CONF_KR_TICKERS, []))
                corp_codes, names, corp_names = await _enrich_kr_metadata(hass, api_key, kr_all)
                merged_names = {**(cfg.get(CONF_KR_TICKER_NAMES, {}) or {}), **names}
                if msg.get("label"):
                    merged_names[ticker] = msg["label"].strip()[:40]
                new_options[CONF_KR_TICKER_NAMES] = merged_names
                new_options[CONF_DISCLOSURE_CORP_CODES] = corp_codes
                new_options[CONF_DISCLOSURE_CORP_NAMES] = corp_names
        elif not (msg.get("label") or "").strip():
            label_key = CONF_US_TICKER_LABELS if market == MARKET_US else CONF_OTHER_TICKER_LABELS
            fetched = await _enrich_other_labels(hass, [ticker], {})
            if fetched.get(ticker):
                labels = dict(new_options.get(label_key, cfg.get(label_key, {})) or {})
                labels[ticker] = fetched[ticker]
                new_options[label_key] = labels
    except (ProviderBusy, Backoff):
        connection.send_error(msg["id"], "provider_busy", "Data provider temporarily unavailable")
        return
    except Exception as err:  # noqa: BLE001 — labels are cosmetic
        LOGGER.debug("Watchlist label enrichment failed for %s: %s", ticker, err)

    if not _commit_watchlist(hass, entry, cfg, original_options, new_options, removing=False):
        connection.send_error(msg["id"], "config_changed", "Configuration changed. Please retry.")
        return
    connection.send_result(msg["id"], {"market": market, "ticker": ticker})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "kr_finance_kit/watchlist/remove",
        vol.Required("market"): vol.In([MARKET_KR, MARKET_US, MARKET_OTHER]),
        vol.Required("ticker"): vol.All(str, vol.Length(min=1, max=24)),
        vol.Optional("force", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_watchlist_remove(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    async with _state(hass).setdefault("watchlist_lock", asyncio.Lock()):
        await _watchlist_remove(hass, connection, msg)


async def _watchlist_remove(hass, connection, msg) -> None:
    entry, _store = _active(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_configured", "Integration is not loaded")
        return
    original_options = dict(entry.options)
    cfg = pd.merged_config(entry.data, entry.options)
    market, ticker = msg["market"], msg["ticker"]
    # Positions price off the watchlist quote — removing the ticker would
    # silently drop the holding from every portfolio total.
    held = any(
        p.get("ticker") == ticker and p.get("market") == market
        for p in cfg.get(CONF_POSITIONS, []) or []
    )
    if held and not msg["force"]:
        connection.send_error(msg["id"], "has_position", "Ticker has a recorded position")
        return
    try:
        new_options = pd.watchlist_remove(entry.data, entry.options, market, ticker)
    except pd.WatchlistError as err:
        connection.send_error(msg["id"], err.code, err.code)
        return
    if held:
        new_options[CONF_POSITIONS] = [
            p for p in cfg.get(CONF_POSITIONS, []) or []
            if not (p.get("ticker") == ticker and p.get("market") == market)
        ]
    if market == MARKET_KR:
        api_key = await unseal(hass, cfg.get(CONF_OPENDART_API_KEY))
        if api_key:
            from .config_flow import _enrich_kr_metadata

            try:
                corp_codes, _names, corp_names = await _enrich_kr_metadata(
                    hass, api_key, list(new_options.get(CONF_KR_TICKERS, []))
                )
                new_options[CONF_DISCLOSURE_CORP_CODES] = corp_codes
                new_options[CONF_DISCLOSURE_CORP_NAMES] = corp_names
            except (ProviderBusy, Backoff):
                connection.send_error(msg["id"], "provider_busy", "Data provider temporarily unavailable")
                return
            except Exception as err:  # noqa: BLE001 — keep the removal itself
                LOGGER.debug("Disclosure code refresh after removing %s failed: %s", ticker, err)
    if not _commit_watchlist(hass, entry, cfg, original_options, new_options, removing=True):
        connection.send_error(msg["id"], "config_changed", "Configuration changed. Please retry.")
        return
    connection.send_result(msg["id"], {"market": market, "ticker": ticker})


@websocket_api.websocket_command({vol.Required("type"): "kr_finance_kit/prefs/get"})
@websocket_api.async_response
async def ws_prefs_get(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    doc = await _prefs_doc(hass)
    uid = connection.user.id if connection.user else "_anon"
    stored = doc["users"].get(uid)
    connection.send_result(
        msg["id"],
        {"prefs": pd.sanitize_prefs(stored), "stored": stored is not None},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "kr_finance_kit/prefs/set",
        vol.Required("prefs"): dict,
    }
)
@websocket_api.async_response
async def ws_prefs_set(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
    doc = await _prefs_doc(hass)
    uid = connection.user.id if connection.user else "_anon"
    current = pd.sanitize_prefs(doc["users"].get(uid))
    merged = pd.sanitize_prefs({**current, **msg["prefs"]})
    doc["users"][uid] = merged
    _state(hass)["store"].async_delay_save(lambda: doc, 2)
    connection.send_result(msg["id"], {"prefs": merged})
