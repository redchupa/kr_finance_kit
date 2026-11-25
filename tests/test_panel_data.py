"""Unit tests for the sidebar panel's pure helpers (panel_data.py)."""
from __future__ import annotations

from datetime import datetime

import pytest

from custom_components.kr_finance_kit import panel_data as pd
from custom_components.kr_finance_kit.const import (
    CONF_INCLUDE_GLOBAL_INDICES,
    CONF_KR_TICKER_NAMES,
    CONF_KR_TICKERS,
    CONF_OTHER_TICKER_LABELS,
    CONF_OTHER_TICKERS,
    CONF_POSITIONS,
    CONF_US_TICKERS,
    TZ_KST,
)
from custom_components.kr_finance_kit.panel_data import TZ_NYC


# ---------------------------------------------------------------- prefs

def test_sanitize_prefs_defaults_from_garbage():
    for raw in (None, "x", 3, [], {"theme": 5}):
        out = pd.sanitize_prefs(raw)
        assert out["theme"] == "ha"
        assert out["layout"] == "cards"
        assert [s["id"] for s in out["sections"]] == list(pd.SECTIONS)


def test_sanitize_prefs_keeps_valid_and_drops_unknown():
    out = pd.sanitize_prefs({
        "theme": "neon", "layout": "heatmap", "lang": "en", "up_color": "green",
        "sparkline": False, "spark_period": "1y", "refresh_sec": 60,
        "evil": "<script>",
    })
    assert out["theme"] == "neon"
    assert out["layout"] == "heatmap"
    assert out["lang"] == "en"
    assert out["up_color"] == "green"
    assert out["sparkline"] is False
    assert out["spark_period"] == "1y"
    assert out["refresh_sec"] == 60
    assert "evil" not in out


def test_sanitize_prefs_rejects_bad_values():
    out = pd.sanitize_prefs({"theme": "hacker", "layout": None, "sparkline": "yes",
                             "refresh_sec": True, "spark_period": "10y"})
    assert out["theme"] == "ha"
    assert out["layout"] == "cards"
    assert out["sparkline"] is True
    assert out["refresh_sec"] == 30
    assert out["spark_period"] == "1mo"


@pytest.mark.parametrize("raw,expected", [(1, 10), (5000, 600), (45.7, 45), (float("nan"), 30)])
def test_sanitize_prefs_refresh_clamped(raw, expected):
    assert pd.sanitize_prefs({"refresh_sec": raw})["refresh_sec"] == expected


def test_sanitize_prefs_sections_order_dedupe_and_backfill():
    out = pd.sanitize_prefs({"sections": [
        {"id": "portfolio", "visible": False},
        {"id": "portfolio", "visible": True},  # duplicate dropped
        {"id": "nope"},                       # unknown dropped
        "junk",
        {"id": "indices"},
    ]})
    ids = [s["id"] for s in out["sections"]]
    assert ids[:2] == ["portfolio", "indices"]
    assert sorted(ids) == sorted(pd.SECTIONS)
    assert out["sections"][0]["visible"] is False


def test_sanitize_prefs_order_validated():
    out = pd.sanitize_prefs({"order": ["KR:005930", "KR:005930", "US:AAPL", "BAD", 5, "OTHER:BTC-USD", "X:<b>"]})
    assert out["order"] == ["KR:005930", "US:AAPL", "OTHER:BTC-USD"]


# ---------------------------------------------------------------- watchlist input

@pytest.mark.parametrize("market,raw,quote,expected", [
    ("KR", "005930", None, ("KR", "005930")),
    ("KR", " 035720.kq ", None, ("KR", "035720.KQ")),
    ("US", "aapl", None, ("US", "AAPL")),
    ("US", "BRK-B", None, ("US", "BRK-B")),
    ("CRYPTO", "btc", "KRW", ("OTHER", "BTC-KRW")),
    ("CRYPTO", "eth", None, ("OTHER", "ETH-USD")),
    ("CRYPTO", "SOL-USDT", "KRW", ("OTHER", "SOL-USDT")),
    ("OTHER", "eur=x", None, ("OTHER", "EUR=X")),
    ("OTHER", "GC=F", None, ("OTHER", "GC=F")),
])
def test_normalize_watch_input_ok(market, raw, quote, expected):
    assert pd.normalize_watch_input(market, raw, quote) == expected


@pytest.mark.parametrize("market,raw,quote,code", [
    ("KR", "5930", None, "invalid_kr_ticker"),
    ("KR", "005930.KX", None, "invalid_kr_ticker"),
    ("KR", "AAPL", None, "invalid_kr_ticker"),
    ("US", "123456", None, "invalid_us_ticker"),
    ("US", "AA PL$", None, "invalid_ticker"),
    ("US", "", None, "invalid_ticker"),
    ("CRYPTO", "BTC", "DOGE", "invalid_quote"),
    ("OTHER", "<script>", None, "invalid_ticker"),
    ("MOON", "BTC", None, "invalid_market"),
    ("US", None, None, "invalid_ticker"),
])
def test_normalize_watch_input_rejects(market, raw, quote, code):
    with pytest.raises(pd.WatchlistError) as exc:
        pd.normalize_watch_input(market, raw, quote)
    assert exc.value.code == code


# ---------------------------------------------------------------- watchlist edit

def test_watchlist_add_preserves_every_other_option():
    """Regression guard for the v0.1.55 class of bug (allow-list rebuild)."""
    data = {CONF_KR_TICKERS: ["005930"], "opendart_api_key": ""}
    options = {CONF_US_TICKERS: ["AAPL"], CONF_INCLUDE_GLOBAL_INDICES: True,
               CONF_POSITIONS: [{"ticker": "AAPL", "market": "US", "quantity": 1, "avg_price": 1}],
               "some_future_key": 42}
    new = pd.watchlist_add(data, options, "OTHER", "BTC-USD", "Bitcoin")
    assert new[CONF_OTHER_TICKERS] == ["BTC-USD"]
    assert new[CONF_OTHER_TICKER_LABELS] == {"BTC-USD": "Bitcoin"}
    for k, v in options.items():
        assert new[k] == v
    # input dicts untouched
    assert CONF_OTHER_TICKERS not in options


def test_watchlist_add_reads_data_when_options_partial():
    """Regression guard for v0.1.56 (`options or data` shadowing)."""
    data = {CONF_KR_TICKERS: ["005930", "000660"]}
    options = {CONF_INCLUDE_GLOBAL_INDICES: True}
    new = pd.watchlist_add(data, options, "KR", "035420")
    assert new[CONF_KR_TICKERS] == ["005930", "000660", "035420"]


def test_watchlist_add_duplicate():
    with pytest.raises(pd.WatchlistError) as exc:
        pd.watchlist_add({CONF_US_TICKERS: ["AAPL"]}, {}, "US", "AAPL")
    assert exc.value.code == "duplicate"


def test_watchlist_add_label_truncated_and_blank_ignored():
    new = pd.watchlist_add({}, {}, "KR", "005930", "  ")
    assert CONF_KR_TICKER_NAMES not in new
    new = pd.watchlist_add({}, {}, "KR", "005930", "x" * 100)
    assert len(new[CONF_KR_TICKER_NAMES]["005930"]) == 40


def test_watchlist_remove():
    data = {CONF_OTHER_TICKERS: ["BTC-USD", "ETH-USD"], CONF_OTHER_TICKER_LABELS: {"BTC-USD": "Bitcoin"}}
    new = pd.watchlist_remove(data, {"keep": 1}, "OTHER", "BTC-USD")
    assert new[CONF_OTHER_TICKERS] == ["ETH-USD"]
    assert new[CONF_OTHER_TICKER_LABELS] == {}
    assert new["keep"] == 1
    with pytest.raises(pd.WatchlistError):
        pd.watchlist_remove(data, {}, "OTHER", "DOGE-USD")
    with pytest.raises(pd.WatchlistError):
        pd.watchlist_remove(data, {}, "CRYPTO", "BTC-USD")


# ---------------------------------------------------------------- classification

@pytest.mark.parametrize("market,ticker,info,kind", [
    ("KR", "005930", None, "stock"),
    ("US", "AAPL", None, "stock"),
    ("OTHER", "BTC-USD", None, "crypto"),
    ("OTHER", "ETH-KRW", None, "crypto"),
    ("OTHER", "EUR=X", None, "fx"),
    ("OTHER", "GC=F", None, "future"),
    ("OTHER", "^VIX", None, "index"),
    ("OTHER", "XYZ", {"quoteType": "CRYPTOCURRENCY"}, "crypto"),
    ("OTHER", "SPY", None, "other"),
])
def test_asset_kind(market, ticker, info, kind):
    assert pd.asset_kind(market, ticker, info) == kind


@pytest.mark.parametrize("market,ticker,info,ccy", [
    ("KR", "005930", None, "KRW"),
    ("US", "AAPL", None, "USD"),
    ("OTHER", "BTC-KRW", None, "KRW"),
    ("OTHER", "BTC-USDT", None, "USD"),
    ("OTHER", "EUR=X", None, None),
    ("OTHER", "GC=F", None, "USD"),
    ("OTHER", "7203.T", {"currency": "jpy"}, "JPY"),
])
def test_asset_currency(market, ticker, info, ccy):
    assert pd.asset_currency(market, ticker, info) == ccy


# ---------------------------------------------------------------- kimchi premium

def test_kimchi_premium():
    quotes = {
        "BTC-KRW": {"price": 141_000_000},
        "BTC-USD": {"price": 100_000},
        "ETH-KRW": {"price": 5_000_000},  # no USD pair → skipped
        "SOL-KRW": {"price": 280_000},
        "SOL-USDT": {"price": 200},
    }
    out = pd.kimchi_premium(quotes, 1400.0)
    assert [x["asset"] for x in out] == ["BTC", "SOL"]
    btc = out[0]
    assert btc["global_krw_price"] == 140_000_000
    assert btc["premium_pct"] == pytest.approx(0.71, abs=0.01)
    assert out[1]["premium_pct"] == 0.0


def test_kimchi_premium_needs_fx():
    assert pd.kimchi_premium({"BTC-KRW": {"price": 1}, "BTC-USD": {"price": 1}}, None) == []
    assert pd.kimchi_premium({"BTC-KRW": {"price": None}, "BTC-USD": {"price": 1}}, 1300) == []


# ---------------------------------------------------------------- sessions

@pytest.mark.parametrize("now,open_,next_local", [
    (datetime(2026, 11, 24, 10, 0, tzinfo=TZ_KST), True, "2026-11-24T15:30"),   # Tue intraday
    (datetime(2026, 11, 24, 8, 0, tzinfo=TZ_KST), False, "2026-11-24T09:00"),   # Tue pre-open
    (datetime(2026, 11, 24, 16, 0, tzinfo=TZ_KST), False, "2026-11-25T09:00"),  # Tue after close
    (datetime(2026, 11, 27, 16, 0, tzinfo=TZ_KST), False, "2026-11-30T09:00"),  # Fri after close → Mon
    (datetime(2026, 11, 28, 12, 0, tzinfo=TZ_KST), False, "2026-11-30T09:00"),  # Sat
])
def test_next_session_change_kr(now, open_, next_local):
    out = pd.next_session_change("KR", now)
    assert out["open"] is open_
    assert out["next"].startswith(next_local)


def test_next_session_change_us_timezone():
    now = datetime(2026, 11, 24, 10, 0, tzinfo=TZ_NYC)
    out = pd.next_session_change("US", now)
    assert out["open"] is True
    assert out["next"].startswith("2026-11-24T16:00")


# ---------------------------------------------------------------- snapshot

def _data():
    return {
        "indices": {"KOSPI": {"price": 2600.5, "change": 10, "change_pct": 0.39},
                    "NASDAQ": {"price": float("nan")}},
        "fx": {"USDKRW": {"price": 1400.0, "change_pct": 0.1}},
        "kr_quotes": {"005930": {"price": 70000, "change": 500, "change_pct": 0.72, "prev_close": 69500}},
        "us_quotes": {"AAPL": {"price": 200.0, "change_pct": -1.0}},
        "other_quotes": {"BTC-KRW": {"price": 141_000_000}, "BTC-USD": {"price": 100_000}},
        "info": {"AAPL": {"fiftyTwoWeekHigh": 250, "longName": "Apple Inc.", "shortName": "Apple"}},
        "positions": [
            {"ticker": "005930", "market": "KR", "quantity": 10, "avg_price": 60000},
            {"ticker": "AAPL", "market": "US", "quantity": 5, "avg_price": 100},
            {"ticker": "000660", "market": "KR", "quantity": 1, "avg_price": 1},  # no quote
        ],
        "fetched_at": "2026-11-25T00:00:00+00:00",
    }


def _cfg():
    return {
        CONF_KR_TICKERS: ["005930"],
        CONF_US_TICKERS: ["AAPL"],
        CONF_OTHER_TICKERS: ["BTC-KRW", "BTC-USD"],
        CONF_KR_TICKER_NAMES: {"005930": "삼성전자"},
        CONF_OTHER_TICKER_LABELS: {"BTC-USD": "Bitcoin"},
    }


def test_build_snapshot_shape():
    snap = pd.build_snapshot(_data(), _cfg(), disclosures=[{"corp_name": "삼성전자", "report_nm": "보고서", "rcept_dt": "20261125", "url": "u"}],
                             entity_ids={"KR:005930": "sensor.fi_kr_005930", "INDEX:KOSPI": "sensor.fi_kospi"})
    assert snap["ready"] is True
    assert snap["usdkrw"] == 1400.0
    kospi = next(i for i in snap["indices"] if i["key"] == "KOSPI")
    assert kospi["group"] == "KR" and kospi["entity_id"] == "sensor.fi_kospi"
    nasdaq = next(i for i in snap["indices"] if i["key"] == "NASDAQ")
    assert nasdaq["price"] is None  # NaN filtered

    by_key = {q["key"]: q for q in snap["quotes"]}
    assert list(by_key) == ["KR:005930", "US:AAPL", "OTHER:BTC-KRW", "OTHER:BTC-USD"]
    sam = by_key["KR:005930"]
    assert sam["name"] == "삼성전자" and sam["currency"] == "KRW" and sam["kind"] == "stock"
    assert sam["entity_id"] == "sensor.fi_kr_005930"
    assert "price_krw" not in sam
    aapl = by_key["US:AAPL"]
    assert aapl["name"] == "Apple"  # falls back to info shortName
    assert aapl["price_krw"] == 280000.0
    assert aapl["info"]["fiftyTwoWeekHigh"] == 250
    assert by_key["OTHER:BTC-KRW"]["kind"] == "crypto"
    assert by_key["OTHER:BTC-KRW"]["currency"] == "KRW"
    assert "price_krw" not in by_key["OTHER:BTC-KRW"]
    assert by_key["OTHER:BTC-USD"]["name"] == "Bitcoin"

    assert snap["kimchi"][0]["asset"] == "BTC"
    assert snap["disclosure_enabled"] is True
    assert snap["disclosures"][0]["corp_name"] == "삼성전자"


def test_build_snapshot_portfolio():
    snap = pd.build_snapshot(_data(), _cfg())
    pf = snap["portfolio"]
    # KR: 10*70000=700000 (cost 600000); US: 5*200=1000 USD → 1.4M KRW (cost 700k)
    assert pf["krw_total"] == 700000 + 1_400_000
    assert pf["krw_pl"] == 100000 + 700_000
    assert pf["krw_pl_pct"] == pytest.approx(800000 / 1_300_000 * 100, abs=0.01)
    rows = {r["ticker"]: r for r in pf["positions"]}
    assert rows["005930"]["pl_pct"] == pytest.approx(16.67, abs=0.01)
    assert rows["AAPL"]["weight_pct"] == pytest.approx(66.67, abs=0.01)
    assert rows["000660"]["value"] is None and rows["000660"]["weight_pct"] is None
    assert snap["disclosure_enabled"] is False


def test_build_snapshot_empty():
    snap = pd.build_snapshot(None, {})
    assert snap["ready"] is False
    assert snap["quotes"] == [] and snap["indices"] == []
    assert snap["portfolio"]["krw_total"] is None
    assert snap["portfolio"]["positions"] == []


def test_build_snapshot_ticker_without_quote_yet():
    cfg = _cfg()
    cfg[CONF_US_TICKERS] = ["AAPL", "MSFT"]  # MSFT just added, no data yet
    snap = pd.build_snapshot(_data(), cfg)
    msft = next(q for q in snap["quotes"] if q["ticker"] == "MSFT")
    assert msft["price"] is None and msft["name"] == "MSFT"


# ---------------------------------------------------------------- search

def test_match_kr_companies_ranking():
    mapping = {
        "005930": ("00126380", "삼성전자"),
        "005935": ("00126380", "삼성전자우"),
        "028260": ("00149655", "삼성물산"),
        "000660": ("00164779", "SK하이닉스"),
        "207940": ("00877059", "삼성바이오로직스"),
    }
    names = [r["name"] for r in pd.match_kr_companies(mapping, "삼성전자")]
    assert names[:2] == ["삼성전자", "삼성전자우"]
    assert {r["name"] for r in pd.match_kr_companies(mapping, "삼성")} == {"삼성전자", "삼성전자우", "삼성물산", "삼성바이오로직스"}
    assert pd.match_kr_companies(mapping, "하이닉스")[0]["symbol"] == "000660"
    assert pd.match_kr_companies(mapping, "sk")[0]["symbol"] == "000660"
    assert [r["symbol"] for r in pd.match_kr_companies(mapping, "0059")] == ["005930", "005935"]
    assert pd.match_kr_companies(mapping, "") == []
    assert pd.match_kr_companies({}, "삼성") == []
    assert len(pd.match_kr_companies(mapping, "삼성", limit=2)) == 2


@pytest.mark.parametrize("symbol,qt,expected", [
    ("005930.KS", "EQUITY", ("KR", "005930.KS")),
    ("035720.KQ", "EQUITY", ("KR", "035720.KQ")),
    ("AAPL", "EQUITY", ("US", "AAPL")),
    ("SPY", "ETF", ("US", "SPY")),
    ("BTC-USD", "CRYPTOCURRENCY", ("CRYPTO", "BTC-USD")),
    ("7203.T", "EQUITY", ("OTHER", "7203.T")),
    ("EURUSD=X", "CURRENCY", ("OTHER", "EURUSD=X")),
    ("^GSPC", "INDEX", ("OTHER", "^GSPC")),
])
def test_classify_search_hit(symbol, qt, expected):
    assert pd.classify_search_hit(symbol, qt) == expected


# ---------------------------------------------------------------- first-install defaults

def test_default_symbols_english():
    d = pd.default_symbols("en")
    assert d["kr"] == ["005930", "000660"]
    assert d["us"] == ["AAPL", "NVDA", "MSFT"]
    assert d["other"] == ["BTC-USD", "ETH-USD"]
    assert d["kr_names"]["005930"] == "Samsung Electronics"
    assert set(d["us_labels"]) == set(d["us"])
    assert set(d["other_labels"]) == set(d["other"])


def test_default_symbols_korean_adds_krw_pair_for_kimchi():
    d = pd.default_symbols("ko")
    assert d["other"][0] == "BTC-KRW" and "BTC-USD" in d["other"]
    assert d["kr_names"]["005930"] == "삼성전자"
    # kimchi premium works out of the box with the seeded pair
    quotes = {"BTC-KRW": {"price": 1400}, "BTC-USD": {"price": 1}}
    assert pd.kimchi_premium(quotes, 1400)[0]["premium_pct"] == 0.0


def test_default_symbols_unknown_language_falls_back_to_english():
    assert pd.default_symbols(None)["kr_names"]["000660"] == "SK hynix"
    assert pd.default_symbols("de-DE")["other"] == ["BTC-USD", "ETH-USD"]


def test_default_symbols_returns_fresh_copies():
    a = pd.default_symbols("en")
    a["us"].append("X")
    assert "X" not in pd.default_symbols("en")["us"]


# ---------------------------------------------------------------- catalog

@pytest.mark.parametrize("market", ["KR", "US", "CRYPTO", "OTHER"])
def test_catalog_for_market_populates_items_categories_and_urls(market):
    res = pd.catalog_for_market(market, lang="ko")
    assert res["market"] == market
    assert len(res["items"]) >= 15
    assert len(res["categories"]) >= 3
    assert res["categories"][0]["id"] == "all"
    assert len(res["links"]) >= 1
    assert all(link["url"].startswith("https://") for link in res["links"])


def test_catalog_for_market_category_filter_and_language():
    etfs_ko = pd.catalog_for_market("US", category="etf", lang="ko")
    etfs_en = pd.catalog_for_market("US", category="etf", lang="en")
    assert all(r["category"] == "etf" for r in etfs_ko["items"])
    assert any(r["symbol"] == "SPY" for r in etfs_ko["items"])
    assert etfs_ko["items"][0]["name"] != etfs_en["items"][0]["name"]


def test_catalog_for_market_krx_all_with_opendart_map():
    extra = {
        "005930": ("00126380", "삼성전자"),
        "000660": ("00164779", "SK하이닉스"),
        "999999": ("00999999", "가나다테스트"),
    }
    res = pd.catalog_for_market("KR", category="krx_all", lang="ko", extra_kr_map=extra)
    assert res["krx_total"] == 3
    assert any(c["id"] == "krx_all" for c in res["categories"])
    assert [r["symbol"] for r in res["items"]] == ["000660", "999999", "005930"]
    filtered = pd.catalog_for_market("KR", category="krx_all", query="가나다", extra_kr_map=extra)
    assert [r["symbol"] for r in filtered["items"]] == ["999999"]


def test_match_catalog_korean_and_english_without_opendart():
    assert pd.match_catalog("삼성전자", lang="ko")[0]["symbol"] == "005930"
    assert pd.match_catalog("엔비디아", lang="ko")[0]["symbol"] == "NVDA"
    assert pd.match_catalog("비트코인", lang="ko")[0]["symbol"] == "BTC"
    assert pd.match_catalog("금 선물", lang="ko")[0]["symbol"] == "GC=F"
    assert pd.match_catalog("Apple", lang="en")[0]["symbol"] == "AAPL"
    assert pd.match_catalog("", lang="ko") == []


# ---------------------------------------------------------------- position price alerts

def test_positions_breakdown_price_alert_states():
    data = {
        "kr_quotes": {
            "005930": {"price": 82000},
            "000660": {"price": 140000},
        },
        "us_quotes": {
            "AAPL": {"price": 175.0},
        },
        "positions": [
            {"ticker": "005930", "market": "KR", "quantity": 10, "avg_price": 70000, "alert_high": 80000, "alert_low": 60000},
            {"ticker": "000660", "market": "KR", "quantity": 5, "avg_price": 150000, "alert_high": 200000, "alert_low": 145000},
            {"ticker": "AAPL", "market": "US", "quantity": 2, "avg_price": 170.0, "alert_high": 200.0, "alert_low": 150.0},
        ],
    }
    rows = {r["ticker"]: r for r in pd.positions_breakdown(data)}
    assert rows["005930"]["alert_state"] == "high"
    assert rows["000660"]["alert_state"] == "low"
    assert rows["AAPL"]["alert_state"] is None


def test_coordinator_price_alert_edge_triggered():
    from types import SimpleNamespace
    from custom_components.kr_finance_kit.binary_sensor import evaluate_price_alert
    from custom_components.kr_finance_kit.const import EVENT_PRICE_ALERT
    from custom_components.kr_finance_kit.coordinator import MarketCoordinator

    assert evaluate_price_alert(80000, 80000, 60000) == "high"
    assert evaluate_price_alert(59000, 80000, 60000) == "low"
    assert evaluate_price_alert(70000, 80000, 60000) is None
    assert evaluate_price_alert(None, 80000, 60000) is None

    fired = []
    coord = object.__new__(MarketCoordinator)
    coord._alert_states = {}
    coord.hass = SimpleNamespace(
        bus=SimpleNamespace(async_fire=lambda ev, data: fired.append((ev, data)))
    )
    cfg = {"kr_ticker_names": {"005930": "삼성전자"}}
    pos = [{"ticker": "005930", "market": "KR", "quantity": 10, "avg_price": 70000, "alert_high": 80000}]

    # First crossing fires once
    coord._check_position_price_alerts({"kr_quotes": {"005930": {"price": 81000}}, "positions": pos}, cfg)
    assert len(fired) == 1
    assert fired[0][0] == EVENT_PRICE_ALERT
    assert fired[0][1]["direction"] == "high"
    assert fired[0][1]["name"] == "삼성전자"

    # Staying above threshold does NOT re-fire
    coord._check_position_price_alerts({"kr_quotes": {"005930": {"price": 82000}}, "positions": pos}, cfg)
    assert len(fired) == 1

    # Dropping back below resets, then crossing again fires again
    coord._check_position_price_alerts({"kr_quotes": {"005930": {"price": 79000}}, "positions": pos}, cfg)
    coord._check_position_price_alerts({"kr_quotes": {"005930": {"price": 80500}}, "positions": pos}, cfg)
    assert len(fired) == 2
