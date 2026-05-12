"""Market hours helper tests."""
from __future__ import annotations

from datetime import datetime

from custom_components.kr_finance_kit.const import TZ_KST
from custom_components.kr_finance_kit.market_hours import (
    TZ_NYC,
    any_market_open,
    both_markets_closed_for,
    is_kr_market_open,
    is_us_market_open,
)


def test_kr_market_open_at_noon_weekday():
    # Wednesday 2026-05-13 12:00 KST — clearly within KRX session.
    dt = datetime(2026, 5, 13, 12, 0, tzinfo=TZ_KST)
    assert is_kr_market_open(dt) is True


def test_kr_market_closed_after_close():
    dt = datetime(2026, 5, 13, 16, 0, tzinfo=TZ_KST)
    assert is_kr_market_open(dt) is False


def test_kr_market_closed_on_weekend():
    dt = datetime(2026, 5, 16, 12, 0, tzinfo=TZ_KST)  # Saturday
    assert is_kr_market_open(dt) is False


def test_us_market_open_at_noon_eastern_weekday():
    # 2026-05-13 12:00 ET — within NYSE session.
    dt = datetime(2026, 5, 13, 12, 0, tzinfo=TZ_NYC)
    assert is_us_market_open(dt) is True


def test_us_market_closed_before_open():
    dt = datetime(2026, 5, 13, 8, 0, tzinfo=TZ_NYC)
    assert is_us_market_open(dt) is False


def test_us_market_closed_on_weekend():
    dt = datetime(2026, 5, 16, 12, 0, tzinfo=TZ_NYC)  # Saturday
    assert is_us_market_open(dt) is False


def test_any_market_open_during_kr_session():
    # KR noon Wed → KR open, US closed (it's ~22:00 ET prev day → no, actually KR Wed noon = US Tue 23:00 ET, weekend? Tue 23:00 closed).
    dt = datetime(2026, 5, 13, 12, 0, tzinfo=TZ_KST)
    assert any_market_open(dt) is True


def test_any_market_open_during_us_session_overnight_kst():
    # 2026-05-14 03:00 KST = 2026-05-13 14:00 ET — Wed, US open.
    dt = datetime(2026, 5, 14, 3, 0, tzinfo=TZ_KST)
    assert any_market_open(dt) is True


def test_both_closed_overnight_weekend():
    # Saturday 03:00 KST — KR weekend, US closed (Fri 14:00 ET? actually Fri 14:00 ET is open).
    # Pick Saturday 23:00 KST = Saturday 10:00 ET — both KR and US weekend.
    dt = datetime(2026, 5, 16, 23, 0, tzinfo=TZ_KST)
    assert any_market_open(dt) is False
    assert both_markets_closed_for(dt, hours=4) is True
