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
from typing import Any

from ..const import (
    FX_USDKRW,
    INDEX_KOSDAQ,
    INDEX_KOSPI,
    LOGGER,
    MARKET_KR,
)

# Map our domain-internal symbols → yfinance tickers. Keeping this mapping
# inside the data layer lets the rest of the integration stay free of
# vendor-specific ticker formatting.
INDEX_TICKERS: dict[str, str] = {
    INDEX_KOSPI: "^KS11",
    INDEX_KOSDAQ: "^KQ11",
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


def _fetch_single(symbol: str) -> dict[str, Any]:
    """Sync helper — run in executor."""
    import yfinance as yf  # heavy module, lazy-load on first use

    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="5d", auto_adjust=False)
    except Exception as err:  # noqa: BLE001 — yfinance raises bare Exception subclasses
        LOGGER.debug("yfinance fetch %s failed: %s", symbol, err)
        return {}
    if hist is None or hist.empty:
        return {}

    last = hist.iloc[-1]
    try:
        close = float(last["Close"])
    except (KeyError, ValueError, TypeError):
        return {}

    out: dict[str, Any] = {
        "price": round(close, 4),
        "asof": last.name.isoformat() if hasattr(last.name, "isoformat") else str(last.name),
        # On Korean holidays yfinance can return a single bar (no prior session
        # in the 5-day window). The "stale" flag lets sensors and the LLM tool
        # surface "no fresh trading day available" without dropping the price.
        "stale": len(hist) < 2,
    }
    if len(hist) >= 2:
        prev = hist.iloc[-2]
        try:
            prev_close = float(prev["Close"])
        except (KeyError, ValueError, TypeError):
            return out
        if prev_close:
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


async def fetch_indices() -> dict[str, dict[str, Any]]:
    raw = await _gather(list(INDEX_TICKERS.values()))
    # Re-key back to our domain symbol (KOSPI/KOSDAQ) for sensor lookup.
    return {name: raw.get(tkr, {}) for name, tkr in INDEX_TICKERS.items()}


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
