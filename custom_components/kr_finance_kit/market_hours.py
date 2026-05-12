"""Market session calendar — KR (KOSPI/KOSDAQ) and US (NYSE/NASDAQ).

We deliberately skip a full Korean public-holidays library — it would add
a heavyweight dependency for a tiny win, and yfinance returns the prior
close on closed days anyway. Weekend handling is built in; on KR
holidays the data simply stops moving (the existing stale-data path
handles that fine).

Two callers use this module:

- ``MarketCoordinator`` — to dial the polling interval up when at least
  one market is open and back down when both are closed.
- ``compute_totals`` consumers (sensors) — to mark a value as "based on
  stale data" once both markets have been closed for a while.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .const import TZ_KST

TZ_NYC = ZoneInfo("America/New_York")

# KRX regular session.
_KR_OPEN = time(9, 0)
_KR_CLOSE = time(15, 30)

# NYSE/NASDAQ regular session (ET).
_US_OPEN = time(9, 30)
_US_CLOSE = time(16, 0)


def _is_weekend(dt: datetime) -> bool:
    return dt.weekday() >= 5  # 5=Sat, 6=Sun


def is_kr_market_open(now: datetime | None = None) -> bool:
    """KOSPI/KOSDAQ regular session check, weekend-aware."""
    n = (now or datetime.now(TZ_KST)).astimezone(TZ_KST)
    if _is_weekend(n):
        return False
    return _KR_OPEN <= n.time() <= _KR_CLOSE


def is_us_market_open(now: datetime | None = None) -> bool:
    """NYSE/NASDAQ regular session check, weekend-aware."""
    n = (now or datetime.now(TZ_NYC)).astimezone(TZ_NYC)
    if _is_weekend(n):
        return False
    return _US_OPEN <= n.time() <= _US_CLOSE


def any_market_open(now: datetime | None = None) -> bool:
    return is_kr_market_open(now) or is_us_market_open(now)


def both_markets_closed_for(now: datetime, hours: float) -> bool:
    """True if neither market has been open in the past ``hours`` hours.

    Used by sensors that want to flag "stale" without losing the last
    known value.
    """
    cutoff = now - timedelta(hours=hours)
    # Sample a few points between cutoff and now. We don't need minute
    # precision — half-hour steps catch open/close transitions.
    step = timedelta(minutes=30)
    t = cutoff
    while t <= now:
        if any_market_open(t):
            return False
        t += step
    return True
