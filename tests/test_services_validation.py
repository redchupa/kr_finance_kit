"""Schema-level validation tests for the add_position / remove_position services.

v0.1.58 hardened the schemas to reject special characters, NaN, Infinity,
negative values, zero, empty strings, and oversized numbers. These tests
lock those guarantees in so future schema edits can't quietly let junk
back into the positions store — the failure mode there is a permanently
unavailable portfolio sensor.

We import the schemas directly (no HA hass instance needed). The schemas
are voluptuous, so they run synchronously.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import voluptuous as vol

# Make custom_components/kr_finance_kit importable.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "custom_components"))

from kr_finance_kit.services import (  # noqa: E402
    _POSITION_SCHEMA,
    _REMOVE_SCHEMA,
    _validate_ticker,
    _finite_positive,
)


# ---- Ticker validator ------------------------------------------------

@pytest.mark.parametrize(
    "good",
    [
        "005930",         # KR KOSPI bare
        "005930.KS",      # KR explicit KOSPI suffix
        "035720.KQ",      # KR KOSDAQ
        "AAPL",           # US
        "MSFT",           # US
        "BRK-B",          # US with hyphen
        "RY.TO",          # Toronto-listed
        "a",              # single-char minimum
        "X" * 20,         # max length
    ],
)
def test_validate_ticker_accepts_real_tickers(good: str) -> None:
    """Every real-world ticker shape we expect must pass."""
    assert _validate_ticker(good) == good.upper().strip()


@pytest.mark.parametrize(
    "bad",
    [
        "",                # empty
        "   ",             # whitespace-only
        "BTC USD",         # internal space
        "005930@KS",       # @ rejected
        "AAPL!",           # !
        "AAPL/MSFT",       # slash
        "EUR=X",           # = (an FX ticker — intentional reject because portfolio is stocks-only)
        "GC=F",            # = futures
        "삼성전자",         # Korean text
        "<script>",        # HTML injection attempt
        "AAPL'; DROP--",   # SQL injection attempt
        "A" * 21,          # too long
        "💎AAPL",          # emoji
        ".AAPL",           # leading dot
        "-AAPL",           # leading hyphen
    ],
)
def test_validate_ticker_rejects_garbage(bad: str) -> None:
    """Anything outside the safe alnum/.-/uppercase grammar must raise."""
    with pytest.raises(vol.Invalid):
        _validate_ticker(bad)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("AAPL ", "AAPL"),
        ("\tAAPL\n", "AAPL"),
        ("  005930  ", "005930"),
    ],
)
def test_validate_ticker_strips_surrounding_whitespace(raw: str, expected: str) -> None:
    """Leading/trailing whitespace is a paste artifact, not garbage — strip it."""
    assert _validate_ticker(raw) == expected


@pytest.mark.parametrize(
    "non_string",
    [None, 0, 1.5, [], {}, ("AAPL",)],
)
def test_validate_ticker_rejects_non_strings(non_string: object) -> None:
    with pytest.raises(vol.Invalid):
        _validate_ticker(non_string)


def test_validate_ticker_normalises_to_upper() -> None:
    """The handler relies on case-folded tickers for the upsert lookup."""
    assert _validate_ticker("aapl") == "AAPL"
    assert _validate_ticker("  AaPl  ") == "AAPL"


# ---- _finite_positive (quantity + avg_price) -------------------------

@pytest.mark.parametrize(
    "good",
    [1, 10, 1.5, 0.0001, 60000, 1_000_000, 999_999_999.0],
)
def test_finite_positive_accepts_real_numbers(good: float) -> None:
    assert _finite_positive(good) == float(good)


@pytest.mark.parametrize(
    "good_str",
    ["1", "10.5", "60000", "0.5"],
)
def test_finite_positive_coerces_numeric_strings(good_str: str) -> None:
    """voluptuous form submissions arrive as strings."""
    assert _finite_positive(good_str) == float(good_str)


@pytest.mark.parametrize(
    "bad,reason",
    [
        (0, "zero"),
        (-1, "negative"),
        (-0.0001, "tiny negative"),
        (float("nan"), "NaN"),
        (float("inf"), "+inf"),
        (-float("inf"), "-inf"),
        (1e10, "above 1e9 ceiling"),
        ("abc", "non-numeric string"),
        ("", "empty string"),
        ("10abc", "mixed numeric/alpha"),
        (None, "None"),
        ([10], "list"),
    ],
)
def test_finite_positive_rejects_bad_values(bad: object, reason: str) -> None:
    with pytest.raises(vol.Invalid):
        _finite_positive(bad)


# ---- Full schema integration ----------------------------------------

def _good_position() -> dict:
    return {
        "ticker": "005930",
        "quantity": 10,
        "avg_price": 60000,
        "market": "KR",
    }


def test_position_schema_accepts_valid_kr() -> None:
    out = _POSITION_SCHEMA(_good_position())
    assert out == {
        "ticker": "005930",
        "quantity": 10.0,
        "avg_price": 60000.0,
        "market": "KR",
    }


def test_position_schema_accepts_valid_us() -> None:
    out = _POSITION_SCHEMA(
        {"ticker": "aapl", "quantity": "10", "avg_price": "180.5", "market": "US"}
    )
    assert out == {
        "ticker": "AAPL",
        "quantity": 10.0,
        "avg_price": 180.5,
        "market": "US",
    }


def test_position_schema_rejects_crypto_market() -> None:
    """The market radio offers KR / US only — OTHER must be rejected at the schema."""
    bad = {"ticker": "BTC-USD", "quantity": 1, "avg_price": 50000, "market": "OTHER"}
    with pytest.raises(vol.Invalid):
        _POSITION_SCHEMA(bad)


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("ticker", ""),
        ("ticker", "BTC USD"),
        ("ticker", "<script>"),
        ("quantity", 0),
        ("quantity", -1),
        ("quantity", float("nan")),
        ("avg_price", 0),
        ("avg_price", -100),
        ("avg_price", float("inf")),
        ("market", "OTHER"),
        ("market", "kr"),  # case-sensitive — must be uppercase
        ("market", ""),
    ],
)
def test_position_schema_rejects_bad_field(field: str, bad_value: object) -> None:
    payload = _good_position()
    payload[field] = bad_value
    with pytest.raises(vol.Invalid):
        _POSITION_SCHEMA(payload)


def test_position_schema_rejects_missing_required() -> None:
    for missing in ("ticker", "quantity", "avg_price", "market"):
        payload = _good_position()
        del payload[missing]
        with pytest.raises(vol.Invalid):
            _POSITION_SCHEMA(payload)


# ---- Remove schema ---------------------------------------------------

def test_remove_schema_round_trips() -> None:
    out = _REMOVE_SCHEMA({"ticker": "005930", "market": "KR"})
    assert out == {"ticker": "005930", "market": "KR"}


def test_remove_schema_rejects_bad_ticker() -> None:
    with pytest.raises(vol.Invalid):
        _REMOVE_SCHEMA({"ticker": "<script>", "market": "KR"})


def test_remove_schema_rejects_other_market() -> None:
    with pytest.raises(vol.Invalid):
        _REMOVE_SCHEMA({"ticker": "BTC-USD", "market": "OTHER"})
