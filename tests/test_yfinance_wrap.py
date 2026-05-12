"""Pure-function tests for yfinance_wrap normalization helpers."""
from __future__ import annotations

from custom_components.kr_finance_kit.api.yfinance_wrap import (
    INDEX_TICKERS,
    FX_TICKERS,
    normalize_kr_ticker,
)
from custom_components.kr_finance_kit.const import (
    FX_USDKRW,
    INDEX_KOSDAQ,
    INDEX_KOSPI,
)


def test_index_tickers_complete():
    assert INDEX_TICKERS[INDEX_KOSPI] == "^KS11"
    assert INDEX_TICKERS[INDEX_KOSDAQ] == "^KQ11"


def test_fx_tickers_complete():
    assert FX_TICKERS[FX_USDKRW] == "KRW=X"


def test_normalize_kr_ticker_appends_ks_for_6_digit_code():
    assert normalize_kr_ticker("005930") == "005930.KS"


def test_normalize_kr_ticker_preserves_existing_suffix():
    assert normalize_kr_ticker("035720.KQ") == "035720.KQ"
    assert normalize_kr_ticker("005930.KS") == "005930.KS"


def test_normalize_kr_ticker_uppercases_lowercase_suffix():
    # Users sometimes type lowercase — we uppercase for yfinance's sake.
    assert normalize_kr_ticker("035720.kq") == "035720.KQ"


def test_normalize_kr_ticker_passthrough_for_non_numeric():
    # Anything that isn't 6 digits and doesn't have a suffix is left alone.
    assert normalize_kr_ticker("BTCUSDT") == "BTCUSDT"


def test_normalize_kr_ticker_handles_empty():
    assert normalize_kr_ticker("") == ""
