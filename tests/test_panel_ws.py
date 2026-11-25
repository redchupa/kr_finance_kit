"""Websocket handler tests for the sidebar panel, using lightweight fakes.

The handlers are unwrapped (``inspect.unwrap``) so we exercise the real
coroutine without HA's websocket server; admin gating is checked on the
decorated callable separately.
"""
from __future__ import annotations

import asyncio
import functools
import inspect
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from homeassistant.exceptions import Unauthorized  # noqa: E402

from custom_components.kr_finance_kit import panel  # noqa: E402
from custom_components.kr_finance_kit.const import (  # noqa: E402
    CONF_KR_TICKERS,
    CONF_OTHER_TICKERS,
    CONF_POSITIONS,
    CONF_US_TICKERS,
    DOMAIN,
)


class FakeEntries:
    def __init__(self, entry):
        self._entry = entry
        self.updated: list[dict] = []

    def async_entries(self, domain):
        return [self._entry] if (domain == DOMAIN and self._entry) else []

    def async_update_entry(self, entry, options):
        self.updated.append(options)
        entry.options = options


class FakeConn:
    def __init__(self, admin=True):
        self.user = SimpleNamespace(id="u1", is_admin=admin)
        self.results: list = []
        self.errors: list = []

    def send_result(self, msg_id, result=None):
        self.results.append(result)

    def send_error(self, msg_id, code, message):
        self.errors.append(code)


def _hass(entry=None, market_data=None, loaded=True):
    hass = SimpleNamespace(data={}, config_entries=FakeEntries(entry))
    if entry is not None and loaded:
        market = SimpleNamespace(data=market_data, last_update_success=True)
        hass.data[DOMAIN] = {entry.entry_id: {"market": market, "disclosure": None}}
    return hass


def _entry(data=None, options=None):
    return SimpleNamespace(entry_id="e1", data=data or {}, options=options or {})


def raw(handler):
    return inspect.unwrap(handler)


def sync(fn):
    """Run an async test body with asyncio.run — CI installs plain pytest
    (no pytest-asyncio), so tests must be sync functions."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        asyncio.run(fn(*args, **kwargs))

    return wrapper


@pytest.fixture(autouse=True)
def _no_registry(monkeypatch):
    monkeypatch.setattr(panel, "_entity_ids", lambda hass, cfg: {})


@sync
async def test_snapshot_not_configured_and_loading():
    conn = FakeConn()
    await raw(panel.ws_snapshot)(_hass(None), conn, {"id": 1})
    assert conn.results[-1] == {"configured": False, "entry_exists": False}
    await raw(panel.ws_snapshot)(_hass(_entry(), loaded=False), conn, {"id": 2})
    assert conn.results[-1] == {"configured": False, "entry_exists": True}


@sync
async def test_snapshot_ok():
    entry = _entry({CONF_KR_TICKERS: ["005930"]})
    hass = _hass(entry, {"kr_quotes": {"005930": {"price": 70000}}})
    conn = FakeConn(admin=False)
    await raw(panel.ws_snapshot)(hass, conn, {"id": 1})
    snap = conn.results[-1]
    assert snap["configured"] is True and snap["is_admin"] is False
    assert snap["quotes"][0]["price"] == 70000


def test_watchlist_add_requires_admin():
    with pytest.raises(Unauthorized):
        panel.ws_watchlist_add(_hass(_entry()), FakeConn(admin=False), {"id": 1})
    with pytest.raises(Unauthorized):
        panel.ws_watchlist_remove(_hass(_entry()), FakeConn(admin=False), {"id": 1})


@sync
async def test_watchlist_add_crypto_success(monkeypatch):
    async def fake_quotes(tickers, market):
        return {tickers[0]: {"price": 1.0}}

    async def fake_info(symbols):
        return {s: {"longName": "Bitcoin KRW"} for s in symbols}

    monkeypatch.setattr(panel.yfinance_wrap, "fetch_quotes", fake_quotes)
    monkeypatch.setattr(panel.yfinance_wrap, "fetch_info", fake_info)
    entry = _entry({CONF_US_TICKERS: ["AAPL"]}, {"include_global_indices": True})
    hass = _hass(entry, {})
    conn = FakeConn()
    await raw(panel.ws_watchlist_add)(hass, conn, {"id": 1, "market": "CRYPTO", "ticker": "btc", "quote": "KRW", "force": False})
    assert conn.errors == []
    assert conn.results[-1] == {"market": "OTHER", "ticker": "BTC-KRW"}
    saved = hass.config_entries.updated[-1]
    assert saved[CONF_OTHER_TICKERS] == ["BTC-KRW"]
    assert saved["include_global_indices"] is True  # other options preserved
    assert saved["other_ticker_labels"] == {"BTC-KRW": "Bitcoin KRW"}


@sync
async def test_watchlist_add_no_quote_then_force(monkeypatch):
    async def empty(tickers, market):
        return {tickers[0]: {}}

    monkeypatch.setattr(panel.yfinance_wrap, "fetch_quotes", empty)

    async def no_info(symbols):
        return {}

    monkeypatch.setattr(panel.yfinance_wrap, "fetch_info", no_info)
    hass = _hass(_entry(), {})
    conn = FakeConn()
    msg = {"id": 1, "market": "US", "ticker": "ZZZZ", "force": False}
    await raw(panel.ws_watchlist_add)(hass, conn, msg)
    assert conn.errors == ["no_quote"] and hass.config_entries.updated == []
    await raw(panel.ws_watchlist_add)(hass, conn, {**msg, "force": True})
    assert hass.config_entries.updated[-1][CONF_US_TICKERS] == ["ZZZZ"]


@sync
async def test_watchlist_add_kr_duplicate_across_suffix():
    hass = _hass(_entry({CONF_KR_TICKERS: ["005930"]}), {})
    conn = FakeConn()
    await raw(panel.ws_watchlist_add)(hass, conn, {"id": 1, "market": "KR", "ticker": "005930.KS", "force": True})
    assert conn.errors == ["duplicate"]


@sync
async def test_watchlist_add_invalid():
    hass = _hass(_entry(), {})
    conn = FakeConn()
    await raw(panel.ws_watchlist_add)(hass, conn, {"id": 1, "market": "KR", "ticker": "AAPL", "force": True})
    assert conn.errors == ["invalid_kr_ticker"]


@sync
async def test_watchlist_remove_guards_positions():
    pos = [{"ticker": "AAPL", "market": "US", "quantity": 1, "avg_price": 1}]
    entry = _entry({CONF_US_TICKERS: ["AAPL", "MSFT"], CONF_POSITIONS: pos})
    hass = _hass(entry, {})
    conn = FakeConn()
    msg = {"id": 1, "market": "US", "ticker": "AAPL", "force": False}
    await raw(panel.ws_watchlist_remove)(hass, conn, msg)
    assert conn.errors == ["has_position"]
    await raw(panel.ws_watchlist_remove)(hass, conn, {**msg, "force": True})
    saved = hass.config_entries.updated[-1]
    assert saved[CONF_US_TICKERS] == ["MSFT"]
    assert saved[CONF_POSITIONS] == []


@sync
async def test_prefs_roundtrip(monkeypatch):
    saved = {}

    class FakeStore:
        def __init__(self, hass, version, key):
            pass

        async def async_load(self):
            return None

        def async_delay_save(self, fn, delay):
            saved["doc"] = fn()

    monkeypatch.setattr(panel, "Store", FakeStore)
    hass = _hass(None)
    conn = FakeConn()
    await raw(panel.ws_prefs_get)(hass, conn, {"id": 1})
    assert conn.results[-1]["stored"] is False
    assert conn.results[-1]["prefs"]["theme"] == "ha"
    await raw(panel.ws_prefs_set)(hass, conn, {"id": 2, "prefs": {"theme": "neon", "bogus": 1}})
    assert conn.results[-1]["prefs"]["theme"] == "neon"
    assert "bogus" not in saved["doc"]["users"]["u1"]
    await raw(panel.ws_prefs_set)(hass, conn, {"id": 3, "prefs": {"layout": "list"}})
    prefs = conn.results[-1]["prefs"]
    assert prefs["theme"] == "neon" and prefs["layout"] == "list"  # partial merge
    await raw(panel.ws_prefs_get)(hass, conn, {"id": 4})
    assert conn.results[-1]["stored"] is True


@sync
async def test_history_cache(monkeypatch):
    calls = []

    async def fake_history(sym, period):
        calls.append((sym, period))
        return {"t": [1, 2], "c": [1.0, 2.0]}

    monkeypatch.setattr(panel.yfinance_wrap, "fetch_history", fake_history)
    hass = _hass(None)
    conn = FakeConn()
    msg = {"id": 1, "period": "1mo", "symbols": [
        {"market": "KR", "ticker": "005930"}, {"market": "INDEX", "ticker": "KOSPI"},
        {"market": "FX", "ticker": "USDKRW"}, {"market": "INDEX", "ticker": "NOPE"}]}
    await raw(panel.ws_history)(hass, conn, msg)
    await raw(panel.ws_history)(hass, conn, msg)
    assert calls == [("005930.KS", "1mo"), ("^KS11", "1mo"), ("KRW=X", "1mo")]
    series = conn.results[-1]["series"]
    assert set(series) == {"KR:005930", "INDEX:KOSPI", "FX:USDKRW"}


# ---------------------------------------------------------------- config flow seeding

def _flow(language="en"):
    from custom_components.kr_finance_kit import config_flow as cf

    flow = cf.KRFinanceKitConfigFlow()
    flow.hass = SimpleNamespace(config=SimpleNamespace(language=language))
    flow._async_current_entries = lambda *a, **k: []
    flow.async_create_entry = lambda **kw: kw
    return flow


_BLANK = {"include_indices": True, "include_us_indices": True, "include_fx": True}


@sync
async def test_config_flow_seeds_defaults_when_blank():
    res = await _flow("ko").async_step_user({**_BLANK})
    data = res["data"]
    assert res["title"] == "Finance Kit"
    assert data[CONF_KR_TICKERS] == ["005930", "000660"]
    assert data[CONF_US_TICKERS] == ["AAPL", "NVDA", "MSFT"]
    assert data[CONF_OTHER_TICKERS] == ["BTC-KRW", "BTC-USD", "ETH-USD"]
    assert data["kr_ticker_names"]["005930"] == "삼성전자"
    assert data["us_ticker_labels"]["AAPL"] == "애플"
    assert "seed_defaults" not in data  # flow-only field, never stored


@sync
async def test_config_flow_no_seed_when_user_typed_tickers(monkeypatch):
    from custom_components.kr_finance_kit import config_flow as cf

    async def no_labels(hass, tickers, explicit):
        return dict(explicit)

    monkeypatch.setattr(cf, "_enrich_other_labels", no_labels)
    res = await _flow().async_step_user({**_BLANK, "us_tickers": "TSLA"})
    data = res["data"]
    assert data[CONF_US_TICKERS] == ["TSLA"]
    assert data[CONF_KR_TICKERS] == [] and data[CONF_OTHER_TICKERS] == []


@sync
async def test_config_flow_seed_opt_out():
    res = await _flow().async_step_user({**_BLANK, "seed_defaults": False})
    data = res["data"]
    assert data[CONF_KR_TICKERS] == [] and data[CONF_US_TICKERS] == [] and data[CONF_OTHER_TICKERS] == []


def test_options_form_has_no_seed_field():
    from custom_components.kr_finance_kit import config_flow as cf

    keys = [str(k) for k in cf._FORM_FIELDS]
    assert "seed_defaults" not in keys
    user_keys = [str(k) for k in cf._USER_FIELDS]
    assert user_keys.index("seed_defaults") == user_keys.index("other_tickers") + 1


def test_disclosure_categories_form_values_are_lowercase_but_stored_upper():
    """hassfest: translated selector option values must be lowercase."""
    from custom_components.kr_finance_kit import config_flow as cf

    assert cf._categories_in(["a", "J", "x", "a", None]) == ["A", "J"]
    assert cf._categories_out(["A", "C", "Z"]) == ["a", "c"]


@sync
async def test_config_flow_stores_upper_case_categories():
    res = await _flow().async_step_user({**_BLANK, "seed_defaults": False, "disclosure_categories": ["a", "d"]})
    assert res["data"]["disclosure_categories"] == ["A", "D"]


# ---------------------------------------------------------------- final review hardening

@pytest.mark.parametrize("ticker", ["../v7/x", "a/b", "x?y=1", "x#y", "", "<b>", "a b"])
def test_history_rejects_unsafe_tickers(ticker):
    """yfinance puts the symbol in the URL path unencoded."""
    import voluptuous as vol

    with pytest.raises(vol.Invalid):
        panel.ws_history._ws_schema({"type": "kr_finance_kit/history", "id": 1,
                                     "symbols": [{"market": "US", "ticker": ticker}]})


@pytest.mark.parametrize("ticker", ["005930", "035720.KQ", "BTC-KRW", "^GSPC", "EUR=X", "GC=F", "BRK-B"])
def test_history_accepts_real_symbols(ticker):
    panel.ws_history._ws_schema({"type": "kr_finance_kit/history", "id": 1,
                                 "symbols": [{"market": "OTHER", "ticker": ticker}]})


@sync
async def test_search_negative_caches_corp_map_failure(monkeypatch):
    from custom_components.kr_finance_kit.api import opendart

    calls = []

    async def failing_map(hass, key):
        calls.append(key)
        return {}

    async def no_yahoo(query, limit=8):
        return []

    monkeypatch.setattr(opendart, "_load_corp_code_map", failing_map)
    monkeypatch.setattr(panel.yfinance_wrap, "search_symbols", no_yahoo)
    hass = _hass(_entry({"opendart_api_key": "k"}), {})
    conn = FakeConn(admin=False)
    await raw(panel.ws_search)(hass, conn, {"id": 1, "query": "삼성"})
    await raw(panel.ws_search)(hass, conn, {"id": 2, "query": "하이닉스"})
    assert calls == ["k"]  # second search skipped the re-download
    assert conn.results[-1] == {"results": []}


@sync
async def test_remove_kr_refreshes_disclosure_codes(monkeypatch):
    from custom_components.kr_finance_kit import config_flow as cf

    seen = {}

    async def fake_enrich(hass, key, kr):
        seen["kr"] = kr
        return ["00164779"], {"000660": "SK하이닉스"}, {"00164779": "SK하이닉스"}

    monkeypatch.setattr(cf, "_enrich_kr_metadata", fake_enrich)
    entry = _entry({CONF_KR_TICKERS: ["005930", "000660"], "opendart_api_key": "k",
                    "disclosure_corp_codes": ["00126380", "00164779"]})
    hass = _hass(entry, {})
    conn = FakeConn()
    await raw(panel.ws_watchlist_remove)(hass, conn, {"id": 1, "market": "KR", "ticker": "005930", "force": False})
    saved = hass.config_entries.updated[-1]
    assert seen["kr"] == ["000660"]
    assert saved["disclosure_corp_codes"] == ["00164779"]


@pytest.mark.parametrize("market,ticker,unit", [
    ("KR", "005930", "KRW"), ("US", "AAPL", "USD"), ("OTHER", "BTC-KRW", "KRW"),
    ("OTHER", "BTC-USD", "USD"), ("OTHER", "BTC-USDT", "USD"), ("OTHER", "ETH-EUR", "EUR"),
    ("OTHER", "EUR=X", "USD"), ("OTHER", "GC=F", "USD"),
])
def test_quote_sensor_unit(market, ticker, unit):
    from custom_components.kr_finance_kit import sensor

    assert sensor._quote_unit(market, ticker) == unit


def test_krw_attr_skips_non_usd_assets():
    from custom_components.kr_finance_kit import sensor

    coord = SimpleNamespace(
        _config={"target_currency_krw": True},
        data={"fx": {"USDKRW": {"price": 1400.0}}},
    )
    assert sensor._krw_attr(coord, "OTHER", 100.0, "BTC-USD") == {"price_krw": 140000.0}
    assert sensor._krw_attr(coord, "OTHER", 79_000_000.0, "BTC-KRW") == {}
    assert sensor._krw_attr(coord, "US", 200.0, "AAPL") == {"price_krw": 280000.0}
