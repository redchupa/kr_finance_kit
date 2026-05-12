"""Pure-function tests for the LLM tool's dispatch logic."""
from __future__ import annotations

from custom_components.kr_finance_kit.const import (
    FX_USDKRW,
    INDEX_KOSDAQ,
    INDEX_KOSPI,
    MARKET_KR,
    MARKET_US,
)
from custom_components.kr_finance_kit.llm_dispatch import dispatch_query


def _data():
    return {
        "indices": {
            INDEX_KOSPI: {"price": 2500.0, "change_pct": 0.5},
            INDEX_KOSDAQ: {"price": 850.0, "change_pct": -0.3},
        },
        "fx": {FX_USDKRW: {"price": 1400.0, "change_pct": 0.1}},
        "kr_quotes": {
            "005930": {"price": 70000.0, "change_pct": 1.5},
            "000660": {"price": 130000.0, "change_pct": -2.0},
        },
        "us_quotes": {
            "AAPL": {"price": 200.0, "change_pct": 3.0},
            "TSLA": {"price": 150.0, "change_pct": -4.5},
        },
        "positions": [
            {"ticker": "005930", "quantity": 10, "avg_price": 60000.0, "market": MARKET_KR},
            {"ticker": "AAPL", "quantity": 5, "avg_price": 180.0, "market": MARKET_US},
        ],
        "kr_market_open": True,
        "us_market_open": False,
    }


def test_dispatch_unknown_query_type():
    assert dispatch_query({"query_type": "frobnicate"}, _data(), [])["error"].startswith(
        "unknown_query_type"
    )


def test_dispatch_market_unavailable():
    assert dispatch_query({"query_type": "index"}, None, None) == {
        "error": "market_data_unavailable"
    }


def test_dispatch_index_default_is_kospi():
    out = dispatch_query({"query_type": "index"}, _data(), [])
    assert out["symbol"] == INDEX_KOSPI
    assert out["price"] == 2500.0


def test_dispatch_index_kosdaq():
    out = dispatch_query({"query_type": "index", "symbol": INDEX_KOSDAQ}, _data(), [])
    assert out["price"] == 850.0


def test_dispatch_fx():
    out = dispatch_query({"query_type": "fx"}, _data(), [])
    assert out["symbol"] == FX_USDKRW
    assert out["price"] == 1400.0


def test_dispatch_quote_requires_ticker():
    assert dispatch_query({"query_type": "quote"}, _data(), [])["error"] == "ticker_required"


def test_dispatch_quote_kr_default_market():
    out = dispatch_query({"query_type": "quote", "ticker": "005930"}, _data(), [])
    assert out["price"] == 70000.0
    assert out["market"] == MARKET_KR


def test_dispatch_quote_us():
    out = dispatch_query(
        {"query_type": "quote", "ticker": "AAPL", "market": MARKET_US}, _data(), []
    )
    assert out["price"] == 200.0


def test_dispatch_portfolio_includes_totals_and_fx():
    out = dispatch_query({"query_type": "portfolio"}, _data(), [])
    assert out["fx_used"] == 1400.0
    assert out["totals"]["kr_value"] == 700000.0
    # 5 * 200 = 1000 USD * 1400 = 1,400,000 KRW
    assert out["totals"]["krw_total"] == 700000.0 + 1400000.0


def test_dispatch_disclosures_truncates_to_ten():
    payload = [{"corp_code": str(i)} for i in range(20)]
    out = dispatch_query({"query_type": "disclosures"}, _data(), payload)
    assert len(out["disclosures"]) == 10


def test_dispatch_disclosure_for_ticker_filters():
    payload = [
        {"corp_code": "00000001", "report_nm": "X"},
        {"corp_code": "00000002", "report_nm": "Y"},
    ]
    out = dispatch_query(
        {"query_type": "disclosure_for_ticker", "ticker": "00000001"},
        _data(),
        payload,
    )
    assert len(out["disclosures"]) == 1
    assert out["disclosures"][0]["corp_code"] == "00000001"


def test_dispatch_top_movers_orders_correctly():
    out = dispatch_query({"query_type": "top_movers", "limit": 2}, _data(), [])
    # Gainers: AAPL (+3.0), 005930 (+1.5)
    assert out["gainers"][0]["ticker"] == "AAPL"
    assert out["gainers"][1]["ticker"] == "005930"
    # Losers: TSLA (-4.5), 000660 (-2.0)
    assert out["losers"][0]["ticker"] == "TSLA"
    assert out["losers"][1]["ticker"] == "000660"


def test_dispatch_market_summary_bundle():
    out = dispatch_query({"query_type": "market_summary"}, _data(), [])
    assert out["kospi"]["price"] == 2500.0
    assert out["kosdaq"]["price"] == 850.0
    assert out["usdkrw"]["price"] == 1400.0
    assert out["kr_market_open"] is True
    assert out["us_market_open"] is False
    assert out["portfolio_totals"]["krw_total"] == 700000.0 + 1400000.0
