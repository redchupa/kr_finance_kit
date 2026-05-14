"""yfinance-backed market data fetcher.

We chose yfinance over scraping Naver Finance because:

1. ``daily_market.py`` (the project's existing data pipeline) already runs
   on yfinance daily, so the source is battle-tested for this use case.
2. yfinance ships KOSPI/KOSDAQ as ``^KS11``/``^KQ11`` and KR equities as
   ``005930.KS`` / ``005930.KQ``, so a single client covers indices, FX
   pairs, and per-ticker quotes uniformly.
3. Avoiding scraping eliminates User-Agent / TLS-fingerprint maintenance
   and the risk of IP-level rate-limit bans on Naver — a constraint
   PLAN.md §7 explicitly flags.

All sync ``yfinance`` calls run inside ``hass.async_add_executor_job`` via
``asyncio.get_running_loop().run_in_executor`` so we never block HA's
event loop.

Returned shape per symbol::

    {
        "price": float,         # latest close
        "change": float,        # close - prev_close
        "change_pct": float,    # in percent, two decimals
        "prev_close": float,
        "asof": str,            # ISO timestamp from the bar
    }

Symbols we couldn't fetch return an empty dict — callers decide how to
surface the gap (we keep stale data at the coordinator layer).
"""
from __future__ import annotations

import asyncio
import math
from typing import Any

from ..const import (
    FX_USDKRW,
    GLOBAL_INDICES,
    INDEX_DAX,
    INDEX_DOW,
    INDEX_FTSE,
    INDEX_HANGSENG,
    INDEX_KOSDAQ,
    INDEX_KOSPI,
    INDEX_NASDAQ,
    INDEX_NIKKEI,
    INDEX_SP500,
    KR_INDICES,
    LOGGER,
    MARKET_KR,
    US_INDICES,
)


def _safe_float(value: Any) -> float | None:
    """Coerce yfinance values to a finite float, or ``None`` for NaN/inf.

    yfinance frequently slips a NaN into the last row of a ``history``
    frame (holidays, incomplete sessions, pre-market closes). A bare
    ``float(NaN)`` succeeds but produces a non-finite value, which HA's
    SensorEntity rejects with ValueError when ``state_class`` is set —
    that ValueError kills entity registration entirely. Filter NaN/inf
    out at the data layer and let callers treat ``None`` as "no data".
    """
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f

# Map our domain-internal symbols → yfinance tickers. Keeping this mapping
# inside the data layer lets the rest of the integration stay free of
# vendor-specific ticker formatting.
INDEX_TICKERS: dict[str, str] = {
    INDEX_KOSPI: "^KS11",
    INDEX_KOSDAQ: "^KQ11",
    INDEX_NASDAQ: "^IXIC",
    INDEX_DOW: "^DJI",
    INDEX_SP500: "^GSPC",
    # Global indices verified live against yfinance 0.2.x on
    # 2026-05-14 — all return quoteType=INDEX with non-empty Close.
    INDEX_NIKKEI: "^N225",
    INDEX_HANGSENG: "^HSI",
    INDEX_FTSE: "^FTSE",
    INDEX_DAX: "^GDAXI",
}
FX_TICKERS: dict[str, str] = {
    FX_USDKRW: "KRW=X",
}


def normalize_kr_ticker(raw: str) -> str:
    """Append ``.KS`` to a bare 6-digit Korean ticker.

    Users may type ``005930`` (assumed KOSPI) or ``005930.KQ`` for KOSDAQ;
    if neither suffix is present we default to ``.KS``. yfinance treats
    unknown formats as 404 silently, so this normalization saves a debug
    round-trip for the common case.
    """
    if not raw:
        return raw
    s = raw.strip().upper()
    if s.endswith((".KS", ".KQ")):
        return s
    if s.isdigit() and len(s) == 6:
        return f"{s}.KS"
    return s


def _fetch_via_history(t) -> tuple[float | None, float | None, str | None, int]:
    """Try ``Ticker.history`` first; returns (close, prev_close, asof, bar_count).

    We use ``period="1mo"`` (not ``5d``) because Korean markets observe
    extra holidays (예: Lunar New Year, Chuseok) that can wipe out
    multi-day windows. 1 month guarantees enough trading days even after
    long breaks. Returns (None, None, None, 0) when the request fails or
    yields an empty frame.
    """
    try:
        hist = t.history(period="1mo", auto_adjust=False)
    except Exception as err:  # noqa: BLE001
        LOGGER.debug("yfinance .history failed: %s", err)
        return None, None, None, 0
    if hist is None or hist.empty:
        return None, None, None, 0

    # Walk backwards through the frame for the first finite Close. yfinance
    # often slots a NaN into the most-recent row before the session prints
    # its real close — skipping NaN rows gives us the last *known good*
    # price instead of crashing later.
    close: float | None = None
    asof: str | None = None
    last_idx: int | None = None
    try:
        close_series = hist["Close"]
    except KeyError:
        return None, None, None, 0
    for i in range(len(hist) - 1, -1, -1):
        candidate = _safe_float(close_series.iloc[i])
        if candidate is not None:
            close = candidate
            row = hist.iloc[i]
            asof = row.name.isoformat() if hasattr(row.name, "isoformat") else str(row.name)
            last_idx = i
            break
    if close is None:
        return None, None, None, 0

    prev_close: float | None = None
    # Look for the most recent finite Close *before* the one we used.
    if last_idx is not None and last_idx > 0:
        for i in range(last_idx - 1, -1, -1):
            candidate = _safe_float(close_series.iloc[i])
            if candidate is not None:
                prev_close = candidate
                break
    return close, prev_close, asof, len(hist)


def _fetch_via_fast_info(t) -> tuple[float | None, float | None]:
    """Fallback path: ``Ticker.fast_info`` uses the lightweight chart API.

    Faster and less rate-limited than ``.info``, but doesn't always
    populate every field. We only ask for ``last_price`` and
    ``previous_close``. Returns (None, None) when nothing usable came
    back. NaN/inf are filtered (fast_info can ship them too).
    """
    try:
        info = t.fast_info
        last = info.last_price
        prev = info.previous_close
    except Exception as err:  # noqa: BLE001
        LOGGER.debug("yfinance .fast_info failed: %s", err)
        return None, None
    return _safe_float(last), _safe_float(prev)


def _fetch_single(symbol: str) -> dict[str, Any]:
    """Sync helper — run in executor.

    Strategy: try ``history`` first (gives us prev_close and a precise
    ``asof`` timestamp); if it returns nothing, fall back to
    ``fast_info`` so we at least get a current price. This covers the
    overnight / post-holiday window where ``history`` sometimes returns
    an empty frame for KR equities — the previous v0.1.x behavior of
    returning ``{}`` made HA mark the sensor unavailable.
    """
    import yfinance as yf  # heavy module, lazy-load on first use

    try:
        t = yf.Ticker(symbol)
    except Exception as err:  # noqa: BLE001
        LOGGER.debug("yfinance Ticker(%s) construction failed: %s", symbol, err)
        return {}

    close, prev_close, asof, bar_count = _fetch_via_history(t)

    if close is None:
        # History didn't yield a usable bar — fall back to fast_info.
        close, prev_close_alt = _fetch_via_fast_info(t)
        if close is None:
            LOGGER.debug("yfinance: no data available for %s", symbol)
            return {}
        if prev_close is None:
            prev_close = prev_close_alt

    out: dict[str, Any] = {
        "price": round(close, 4),
        # bar_count < 2 means we have today but no prior trading day in the
        # 1-month window — surface that to consumers so they can label the
        # change figure as missing rather than zero.
        "stale": bar_count < 2,
    }
    if asof:
        out["asof"] = asof
    if prev_close is not None and prev_close:
        change = close - prev_close
        out["prev_close"] = round(prev_close, 4)
        out["change"] = round(change, 4)
        out["change_pct"] = round(change / prev_close * 100, 2)
    return out


async def _gather(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Run executor calls sequentially within this gather.

    yfinance hits Yahoo's chart endpoint and is sensitive to burst patterns
    — sequential calls inside a single coordinator tick are fine because
    SCAN_INTERVAL_MARKET (60s) bounds throughput already.
    """
    if not symbols:
        return {}
    loop = asyncio.get_running_loop()
    out: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        out[sym] = await loop.run_in_executor(None, _fetch_single, sym)
    return out


_INFO_FIELDS_VERIFIED: tuple[str, ...] = (
    # Verified present across EQUITY / INDEX / CRYPTOCURRENCY / CURRENCY in
    # yfinance 0.2.x (see manual probe of AAPL, ^KS11, BTC-USD, 005930.KS,
    # KRW=X). Fields not in this list are dropped silently — we never want
    # the sensor to surface a key whose presence we haven't checked.
    "fiftyTwoWeekHigh",
    "fiftyTwoWeekLow",
    "fiftyDayAverage",
    "twoHundredDayAverage",
    "regularMarketDayHigh",
    "regularMarketDayLow",
    "regularMarketVolume",
    "marketState",
    "currency",
    "quoteType",
    "longName",
    "shortName",
    "averageDailyVolume10Day",
    "averageVolume",
    # Equity-only (None for INDEX/CRYPTOCURRENCY/CURRENCY); we surface them
    # when yfinance returns a finite number, drop otherwise.
    "dividendRate",
    "dividendYield",
    "trailingAnnualDividendRate",
    "dividendDate",
    "forwardPE",
    "trailingPE",
    "preMarketPrice",
    "postMarketPrice",
)


def _fetch_info_sync(symbol: str) -> dict[str, Any]:
    """Pull yfinance .info for a single symbol and filter to verified keys.

    Heavy call (extra HTTP round-trip vs. fast_info). Caller must gate
    this behind the user's detailed-attrs option to avoid bloating the
    polling budget.
    """
    import yfinance as yf
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception as err:  # noqa: BLE001
        LOGGER.debug("yfinance .info(%s) failed: %s", symbol, err)
        return {}
    out: dict[str, Any] = {}
    for key in _INFO_FIELDS_VERIFIED:
        v = info.get(key)
        if v is None:
            continue
        # NaN/inf guard for numeric fields (yfinance occasionally returns
        # NaN for stale equity rows). String fields pass through.
        if isinstance(v, (int, float)):
            f = _safe_float(v)
            if f is None:
                continue
            out[key] = f
        else:
            out[key] = v
    return out


async def fetch_info(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch yfinance .info for many symbols, sequentially in executor."""
    if not symbols:
        return {}
    loop = asyncio.get_running_loop()
    out: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        out[sym] = await loop.run_in_executor(None, _fetch_info_sync, sym)
    return out


async def fetch_indices(names: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """Fetch index quotes. ``names`` filters which subset to actually hit yfinance for.

    Passing ``None`` keeps the legacy behavior (all known indices). Passing
    an empty list returns ``{}`` without any network — used when the
    coordinator wants to skip indices entirely under user options.
    """
    if names is None:
        wanted = INDEX_TICKERS
    else:
        wanted = {n: INDEX_TICKERS[n] for n in names if n in INDEX_TICKERS}
    if not wanted:
        return {}
    raw = await _gather(list(wanted.values()))
    # Re-key back to our domain symbol for sensor lookup.
    return {name: raw.get(tkr, {}) for name, tkr in wanted.items()}


async def fetch_fx() -> dict[str, dict[str, Any]]:
    raw = await _gather(list(FX_TICKERS.values()))
    return {name: raw.get(tkr, {}) for name, tkr in FX_TICKERS.items()}


async def fetch_quotes(tickers: list[str], market: str = MARKET_KR) -> dict[str, dict[str, Any]]:
    """Fetch per-ticker quotes for a single market.

    KR tickers get yfinance suffix normalization (``005930`` → ``005930.KS``).
    Result is keyed by the user-facing ticker so sensor lookups stay
    straightforward.
    """
    if not tickers:
        return {}
    if market == MARKET_KR:
        symbols = [normalize_kr_ticker(t) for t in tickers]
        raw = await _gather(symbols)
        return {orig: raw.get(sym, {}) for orig, sym in zip(tickers, symbols)}
    raw = await _gather(tickers)
    return raw
