"""Pure dispatch logic for the ``finance_query`` LLM tool.

Split from ``llm_tool`` so the per-query_type branches can be unit-tested
without standing up a Home Assistant fixture. ``llm_tool.FinanceQueryTool``
calls ``dispatch_query`` with the raw coordinator data and forwards the
returned dict to the LLM.
"""
from __future__ import annotations

from typing import Any

from .const import FX_USDKRW, INDEX_KOSDAQ, INDEX_KOSPI, MARKET_KR, MARKET_US
from .portfolio import compute_totals

QUERY_TYPES = (
    "index",
    "fx",
    "quote",
    "portfolio",
    "disclosures",
    "disclosure_for_ticker",
    "top_movers",
    "market_summary",
)


def _usdkrw(market_data: dict[str, Any]) -> float | None:
    rate = (market_data.get("fx", {}) or {}).get(FX_USDKRW, {}).get("price")
    return float(rate) if rate else None


def _all_quotes(market_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten KR + US quotes into a uniform shape with market labels."""
    rows: list[dict[str, Any]] = []
    for ticker, q in (market_data.get("kr_quotes") or {}).items():
        if q:
            rows.append({"market": MARKET_KR, "ticker": ticker, **q})
    for ticker, q in (market_data.get("us_quotes") or {}).items():
        if q:
            rows.append({"market": MARKET_US, "ticker": ticker, **q})
    return rows


def dispatch_query(
    args: dict[str, Any],
    market_data: dict[str, Any] | None,
    disclosure_data: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Run a single ``finance_query`` invocation.

    Returns the dict the LLM tool layer hands back to the assistant. Never
    raises — invalid inputs become ``{"error": ...}`` so the LLM can
    repair its arguments and retry.
    """
    qt = args.get("query_type")
    if qt not in QUERY_TYPES:
        return {"error": f"unknown_query_type: {qt}"}
    if market_data is None:
        return {"error": "market_data_unavailable"}

    if qt == "index":
        sym = args.get("symbol", INDEX_KOSPI)
        return {"symbol": sym, **(market_data.get("indices", {}).get(sym, {}) or {})}

    if qt == "fx":
        sym = args.get("symbol", FX_USDKRW)
        return {"symbol": sym, **(market_data.get("fx", {}).get(sym, {}) or {})}

    if qt == "quote":
        ticker = args.get("ticker")
        if not ticker:
            return {"error": "ticker_required"}
        mkt = args.get("market", MARKET_KR)
        key = "kr_quotes" if mkt == MARKET_KR else "us_quotes"
        return {
            "ticker": ticker,
            "market": mkt,
            **(market_data.get(key, {}).get(ticker, {}) or {}),
        }

    if qt == "portfolio":
        rate = _usdkrw(market_data)
        return {
            "positions": market_data.get("positions", []),
            "totals": compute_totals(market_data, usdkrw=rate),
            "fx_used": rate,
        }

    if qt == "disclosures":
        return {"disclosures": (disclosure_data or [])[:10]}

    if qt == "disclosure_for_ticker":
        ticker = args.get("ticker")
        if not ticker:
            return {"error": "ticker_required"}
        # Disclosures store corp_code, not the original stock_code, so the
        # match is best-effort — we match either field. Most users seed
        # corp_codes via the stock_code resolver, which means both forms
        # may be useful here.
        rows = [
            d for d in (disclosure_data or [])
            if d.get("corp_code") == ticker or (d.get("rcept_no") or "").startswith(ticker)
        ]
        return {"ticker": ticker, "disclosures": rows[:5]}

    if qt == "top_movers":
        limit = int(args.get("limit", 3) or 3)
        rows = [q for q in _all_quotes(market_data) if q.get("change_pct") is not None]
        rows.sort(key=lambda r: r["change_pct"], reverse=True)
        return {
            "gainers": rows[:limit],
            "losers": list(reversed(rows[-limit:])) if len(rows) >= limit else list(reversed(rows)),
        }

    if qt == "market_summary":
        indices = market_data.get("indices", {})
        fx = market_data.get("fx", {})
        rate = _usdkrw(market_data)
        totals = compute_totals(market_data, usdkrw=rate)
        return {
            "kospi": indices.get(INDEX_KOSPI, {}),
            "kosdaq": indices.get(INDEX_KOSDAQ, {}),
            "usdkrw": fx.get(FX_USDKRW, {}),
            "kr_market_open": market_data.get("kr_market_open"),
            "us_market_open": market_data.get("us_market_open"),
            "portfolio_totals": totals,
        }

    # Unreachable — QUERY_TYPES guard above prevents this branch.
    return {"error": f"unhandled: {qt}"}
