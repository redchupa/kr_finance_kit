"""Portfolio aggregation logic (portfolio.compute_totals)."""
from __future__ import annotations

from custom_components.kr_finance_kit.const import MARKET_KR, MARKET_US
from custom_components.kr_finance_kit.portfolio import compute_totals


def _data(positions, kr_quotes=None, us_quotes=None):
    return {
        "kr_quotes": kr_quotes or {},
        "us_quotes": us_quotes or {},
        "positions": positions,
    }


def test_compute_totals_kr_only_positions():
    totals = compute_totals(
        _data(
            [{"ticker": "005930", "quantity": 10, "avg_price": 60000.0, "market": MARKET_KR}],
            kr_quotes={"005930": {"price": 70000.0}},
        )
    )
    assert totals["kr_value"] == 700000.0
    assert totals["kr_pl"] == 100000.0
    assert totals["us_value"] is None
    # No US holdings → KRW total falls back to the KR slice.
    assert totals["krw_total"] == 700000.0
    assert totals["krw_pl"] == 100000.0


def test_compute_totals_us_only_with_fx():
    totals = compute_totals(
        _data(
            [{"ticker": "AAPL", "quantity": 5, "avg_price": 180.0, "market": MARKET_US}],
            us_quotes={"AAPL": {"price": 200.0}},
        ),
        usdkrw=1400.0,
    )
    assert totals["us_value"] == 1000.0
    assert totals["us_pl"] == 100.0
    # 1000 USD * 1400 KRW = 1,400,000.
    assert totals["krw_total"] == 1400000.0
    assert totals["krw_pl"] == 140000.0


def test_compute_totals_us_only_without_fx_returns_no_krw_total():
    totals = compute_totals(
        _data(
            [{"ticker": "AAPL", "quantity": 5, "avg_price": 180.0, "market": MARKET_US}],
            us_quotes={"AAPL": {"price": 200.0}},
        ),
        usdkrw=None,
    )
    assert totals["us_value"] == 1000.0
    assert totals["krw_total"] is None
    assert totals["krw_pl"] is None


def test_compute_totals_combined_with_fx():
    totals = compute_totals(
        _data(
            [
                {"ticker": "005930", "quantity": 10, "avg_price": 60000.0, "market": MARKET_KR},
                {"ticker": "AAPL", "quantity": 5, "avg_price": 180.0, "market": MARKET_US},
            ],
            kr_quotes={"005930": {"price": 70000.0}},
            us_quotes={"AAPL": {"price": 200.0}},
        ),
        usdkrw=1400.0,
    )
    # KR 700,000 + (5 * 200) USD * 1400 = 700,000 + 1,400,000 = 2,100,000.
    assert totals["krw_total"] == 2100000.0
    # KR pl 100,000 + (5 * (200-180)) USD * 1400 = 100,000 + 140,000 = 240,000.
    assert totals["krw_pl"] == 240000.0


def test_compute_totals_skips_positions_with_no_quote():
    totals = compute_totals(
        _data(
            [
                {"ticker": "005930", "quantity": 1, "avg_price": 60000.0, "market": MARKET_KR},
                {"ticker": "MISSING", "quantity": 1, "avg_price": 50000.0, "market": MARKET_KR},
            ],
            kr_quotes={"005930": {"price": 70000.0}},
        )
    )
    assert totals["kr_value"] == 70000.0
    assert totals["kr_pl"] == 10000.0


def test_compute_totals_returns_none_when_no_quotes_match():
    totals = compute_totals(
        _data(
            [{"ticker": "005930", "quantity": 1, "avg_price": 60000.0, "market": MARKET_KR}],
        )
    )
    assert totals["kr_value"] is None
    assert totals["krw_total"] is None


def test_compute_totals_empty_positions():
    totals = compute_totals(_data([]))
    assert all(v is None for v in totals.values())
