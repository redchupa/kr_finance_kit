"""Portfolio aggregation — kept HA-free for unit tests.

``compute_totals`` returns per-market subtotals and an optional KRW total.
KR positions sum in KRW; US positions sum in USD. When ``usdkrw`` (a
USD/KRW rate) is supplied, ``krw_total`` and ``krw_pl`` are populated by
converting the US slice at that rate.

Sensors render whichever fields they need; downstream consumers (LLM
tool, dashboards) get a single dict.
"""
from __future__ import annotations

from typing import Any

from .const import MARKET_KR, MARKET_US

_EMPTY = {
    "kr_value": None,
    "kr_pl": None,
    "us_value": None,
    "us_pl": None,
    "krw_total": None,
    "krw_pl": None,
}


def _accum(positions: list[dict[str, Any]], quotes: dict[str, dict[str, Any]]) -> tuple[float, float, bool]:
    value = 0.0
    cost = 0.0
    seen = False
    for pos in positions:
        ticker = pos.get("ticker")
        qty = float(pos.get("quantity", 0) or 0)
        avg = float(pos.get("avg_price", 0) or 0)
        quote = quotes.get(ticker, {}) or {}
        price = quote.get("price")
        if price is None:
            continue
        seen = True
        value += float(price) * qty
        cost += avg * qty
    return value, cost, seen


def compute_totals(
    data: dict[str, Any], usdkrw: float | None = None
) -> dict[str, float | None]:
    """Sum portfolio value/P&L per market, optionally rolled into KRW.

    Returns a dict with keys ``kr_value``, ``kr_pl``, ``us_value``,
    ``us_pl``, ``krw_total``, ``krw_pl``. Each is ``None`` when there's no
    data to back it (no positions, or quotes unavailable) so the sensor
    layer can show "unavailable" instead of a misleading zero.
    """
    out = dict(_EMPTY)
    kr_quotes = data.get("kr_quotes", {}) or {}
    us_quotes = data.get("us_quotes", {}) or {}
    positions = data.get("positions", []) or []

    kr_pos = [p for p in positions if p.get("market", MARKET_KR) == MARKET_KR]
    us_pos = [p for p in positions if p.get("market") == MARKET_US]

    kr_value, kr_cost, kr_seen = _accum(kr_pos, kr_quotes)
    us_value, us_cost, us_seen = _accum(us_pos, us_quotes)

    if kr_seen:
        out["kr_value"] = round(kr_value, 2)
        out["kr_pl"] = round(kr_value - kr_cost, 2)
    if us_seen:
        out["us_value"] = round(us_value, 2)
        out["us_pl"] = round(us_value - us_cost, 2)

    # KRW total only makes sense when we have at least one market and
    # (for US) the FX rate to convert with.
    if kr_seen and not us_seen:
        out["krw_total"] = out["kr_value"]
        out["krw_pl"] = out["kr_pl"]
    elif us_seen and not kr_seen and usdkrw:
        out["krw_total"] = round(us_value * usdkrw, 2)
        out["krw_pl"] = round((us_value - us_cost) * usdkrw, 2)
    elif kr_seen and us_seen and usdkrw:
        out["krw_total"] = round(kr_value + us_value * usdkrw, 2)
        out["krw_pl"] = round((kr_value - kr_cost) + (us_value - us_cost) * usdkrw, 2)

    return out
