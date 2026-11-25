"""Pure helpers behind the sidebar panel — kept HA-free for unit tests.

Everything the panel's websocket handlers need that *isn't* Home
Assistant plumbing lives here:

- ``sanitize_prefs``        — validate per-user display preferences
- ``normalize_watch_input`` — turn "BTC" + crypto/KRW into ``BTC-KRW`` etc.
- ``watchlist_add`` / ``watchlist_remove`` — compute the new options
  dict (always a spread merge, never an allow-list rebuild — see the
  v0.1.55 incident in services._save_positions)
- ``build_snapshot``        — coordinator.data → panel JSON
- ``kimchi_premium``        — KRW crypto price vs. USD price × USD/KRW
- ``next_session_change``   — KR/US open/close countdown target

The panel never triggers a Yahoo request through ``build_snapshot``;
it only reshapes what the coordinator already holds in memory.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .const import (
    CONF_KR_TICKER_NAMES,
    CONF_KR_TICKERS,
    CONF_OTHER_TICKER_LABELS,
    CONF_OTHER_TICKERS,
    CONF_US_TICKER_LABELS,
    CONF_US_TICKERS,
    FX_USDKRW,
    GLOBAL_INDICES,
    KR_INDICES,
    MARKET_KR,
    MARKET_OTHER,
    MARKET_US,
    TZ_KST,
    US_INDICES,
)
from .portfolio import compute_totals

TZ_NYC = ZoneInfo("America/New_York")

# --------------------------------------------------------------------------
# Preferences
# --------------------------------------------------------------------------

THEMES: tuple[str, ...] = (
    "ha", "midnight", "paper", "terminal", "neon", "glass", "ocean",
    "sunset", "forest", "mono", "pastel", "ink", "amoled",
)
LAYOUTS: tuple[str, ...] = ("cards", "list", "compact", "big", "heatmap", "tape")
SECTIONS: tuple[str, ...] = (
    "summary", "indices", "watchlist", "crypto", "portfolio", "disclosures",
)
LANGS: tuple[str, ...] = ("auto", "ko", "en")
UP_COLORS: tuple[str, ...] = ("auto", "red", "green")
CHART_PERIODS: tuple[str, ...] = ("1d", "5d", "1mo", "6mo", "1y")

DEFAULT_PREFS: dict[str, Any] = {
    "lang": "auto",
    "theme": "ha",
    "layout": "cards",
    "up_color": "auto",
    "sections": [{"id": s, "visible": True} for s in SECTIONS],
    "sparkline": True,
    "spark_period": "1mo",
    "refresh_sec": 30,
    "compact_numbers": False,
    "show_krw": True,
    "order": [],
}

_MAX_ORDER = 200


def sanitize_prefs(raw: Any) -> dict[str, Any]:
    """Return a fully-populated, validated prefs dict.

    Unknown keys are dropped, bad values fall back to defaults. The
    panel can therefore send a partial dict (just the field the user
    touched) merged onto the stored copy and we always persist a
    well-formed document.
    """
    src = raw if isinstance(raw, dict) else {}
    out: dict[str, Any] = {}

    def pick(key: str, allowed: tuple[str, ...]) -> str:
        v = src.get(key)
        return v if isinstance(v, str) and v in allowed else DEFAULT_PREFS[key]

    out["lang"] = pick("lang", LANGS)
    out["theme"] = pick("theme", THEMES)
    out["layout"] = pick("layout", LAYOUTS)
    out["up_color"] = pick("up_color", UP_COLORS)
    out["spark_period"] = pick("spark_period", CHART_PERIODS)

    for key in ("sparkline", "compact_numbers", "show_krw"):
        v = src.get(key)
        out[key] = v if isinstance(v, bool) else DEFAULT_PREFS[key]

    rs = src.get("refresh_sec")
    if isinstance(rs, (int, float)) and not isinstance(rs, bool) and math.isfinite(rs):
        out["refresh_sec"] = int(min(600, max(10, rs)))
    else:
        out["refresh_sec"] = DEFAULT_PREFS["refresh_sec"]

    # Sections: keep the user's order for known ids, drop unknown or
    # duplicate ids, then append any section the user's stored copy
    # doesn't know about yet (new section shipped in a later release).
    seen: set[str] = set()
    sections: list[dict[str, Any]] = []
    raw_sections = src.get("sections")
    if isinstance(raw_sections, list):
        for item in raw_sections:
            if not isinstance(item, dict):
                continue
            sid = item.get("id")
            if sid not in SECTIONS or sid in seen:
                continue
            seen.add(sid)
            sections.append({"id": sid, "visible": bool(item.get("visible", True))})
    for sid in SECTIONS:
        if sid not in seen:
            sections.append({"id": sid, "visible": True})
    out["sections"] = sections

    order: list[str] = []
    raw_order = src.get("order")
    if isinstance(raw_order, list):
        for key in raw_order:
            if isinstance(key, str) and _ORDER_KEY_RE.match(key) and key not in order:
                order.append(key)
            if len(order) >= _MAX_ORDER:
                break
    out["order"] = order
    return out


# --------------------------------------------------------------------------
# Watchlist editing
# --------------------------------------------------------------------------

MARKET_CRYPTO = "CRYPTO"  # panel-only alias — stored under other_tickers
PANEL_MARKETS = (MARKET_KR, MARKET_US, MARKET_CRYPTO, MARKET_OTHER)
CRYPTO_QUOTES = ("USD", "KRW", "USDT", "EUR", "JPY")

# Same grammar as services._TICKER_RE plus "=" and "^" so FX (EUR=X),
# futures (GC=F) and Yahoo index symbols survive.
_WATCH_TICKER_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.\-=^]{0,23}$")
_ORDER_KEY_RE = re.compile(r"^(KR|US|OTHER):[A-Z0-9^][A-Z0-9.\-=^]{0,23}$")
_MAX_LABEL = 40

_MARKET_KEYS = {
    MARKET_KR: (CONF_KR_TICKERS, CONF_KR_TICKER_NAMES),
    MARKET_US: (CONF_US_TICKERS, CONF_US_TICKER_LABELS),
    MARKET_OTHER: (CONF_OTHER_TICKERS, CONF_OTHER_TICKER_LABELS),
}


class WatchlistError(ValueError):
    """Raised with a short machine-readable code the panel translates."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def normalize_watch_input(
    market: str, ticker: str, quote: str | None = None
) -> tuple[str, str]:
    """Validate panel input and map it onto the stored (market, ticker).

    - ``KR``: 6-digit code, optional ``.KS`` / ``.KQ`` suffix.
    - ``US``: alphabetic symbol (``AAPL``, ``BRK-B``).
    - ``CRYPTO``: ``BTC`` + quote currency → ``BTC-USD``; an explicit
      ``BTC-KRW`` passes through. Stored under ``other_tickers``.
    - ``OTHER``: any Yahoo symbol (``EUR=X``, ``GC=F``).
    """
    if market not in PANEL_MARKETS:
        raise WatchlistError("invalid_market")
    if not isinstance(ticker, str):
        raise WatchlistError("invalid_ticker")
    t = ticker.strip().upper().replace(" ", "")
    if not t:
        raise WatchlistError("invalid_ticker")

    if market == MARKET_KR:
        base, _, suffix = t.partition(".")
        if not (base.isdigit() and len(base) == 6) or suffix not in ("", "KS", "KQ"):
            raise WatchlistError("invalid_kr_ticker")
        return MARKET_KR, t

    if market == MARKET_CRYPTO:
        q = (quote or "USD").strip().upper()
        if q not in CRYPTO_QUOTES:
            raise WatchlistError("invalid_quote")
        if "-" not in t:
            t = f"{t}-{q}"
        if not _WATCH_TICKER_RE.match(t):
            raise WatchlistError("invalid_ticker")
        return MARKET_OTHER, t

    if not _WATCH_TICKER_RE.match(t):
        raise WatchlistError("invalid_ticker")
    if market == MARKET_US and t.isdigit():
        raise WatchlistError("invalid_us_ticker")
    return market, t


def merged_config(data: dict[str, Any] | None, options: dict[str, Any] | None) -> dict[str, Any]:
    """Options layered on data — the only safe read (see v0.1.56)."""
    return {**(data or {}), **(options or {})}


def watchlist_add(
    data: dict[str, Any] | None,
    options: dict[str, Any] | None,
    market: str,
    ticker: str,
    label: str | None = None,
) -> dict[str, Any]:
    """Return the new ``entry.options`` with ``ticker`` appended.

    ``market`` / ``ticker`` must already be normalized. Raises
    ``WatchlistError("duplicate")`` when the ticker is already there so
    the panel can tell the user instead of silently reloading.
    """
    list_key, label_key = _MARKET_KEYS[market]
    cfg = merged_config(data, options)
    tickers = list(cfg.get(list_key, []) or [])
    if ticker in tickers:
        raise WatchlistError("duplicate")
    tickers.append(ticker)
    new_options = {**(options or {}), list_key: tickers}
    clean_label = (label or "").strip()[:_MAX_LABEL]
    if clean_label:
        labels = dict(cfg.get(label_key, {}) or {})
        labels[ticker] = clean_label
        new_options[label_key] = labels
    return new_options


def watchlist_remove(
    data: dict[str, Any] | None,
    options: dict[str, Any] | None,
    market: str,
    ticker: str,
) -> dict[str, Any]:
    """Return the new ``entry.options`` with ``ticker`` removed."""
    if market not in _MARKET_KEYS:
        raise WatchlistError("invalid_market")
    list_key, label_key = _MARKET_KEYS[market]
    cfg = merged_config(data, options)
    tickers = list(cfg.get(list_key, []) or [])
    if ticker not in tickers:
        raise WatchlistError("not_found")
    tickers = [t for t in tickers if t != ticker]
    new_options = {**(options or {}), list_key: tickers}
    labels = dict(cfg.get(label_key, {}) or {})
    if ticker in labels:
        labels.pop(ticker)
        new_options[label_key] = labels
    return new_options


# --------------------------------------------------------------------------
# Snapshot
# --------------------------------------------------------------------------

def _finite(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def asset_kind(market: str, ticker: str, info: dict[str, Any] | None = None) -> str:
    """Classify a watchlist symbol for grouping + icons."""
    if market in (MARKET_KR, MARKET_US):
        return "stock"
    qt = str((info or {}).get("quoteType") or "").upper()
    if qt == "CRYPTOCURRENCY":
        return "crypto"
    t = ticker.upper()
    if t.endswith("=X") or qt == "CURRENCY":
        return "fx"
    if t.endswith("=F") or qt == "FUTURE":
        return "future"
    if t.startswith("^") or qt == "INDEX":
        return "index"
    if "-" in t:
        quote = t.rsplit("-", 1)[1]
        if quote in CRYPTO_QUOTES or quote in ("BTC", "ETH"):
            return "crypto"
    return "other"


def asset_currency(market: str, ticker: str, info: dict[str, Any] | None = None) -> str | None:
    """Best-effort price currency (None for FX rates, which are ratios)."""
    if market == MARKET_KR:
        return "KRW"
    ccy = (info or {}).get("currency")
    if isinstance(ccy, str) and ccy:
        return ccy.upper()
    if market == MARKET_US:
        return "USD"
    t = ticker.upper()
    if t.endswith("=X"):
        return None
    if "-" in t:
        quote = t.rsplit("-", 1)[1]
        if quote in CRYPTO_QUOTES:
            return "USD" if quote == "USDT" else quote
    return "USD"


def kimchi_premium(
    other_quotes: dict[str, dict[str, Any]], usdkrw: float | None
) -> list[dict[str, Any]]:
    """KRW-market crypto price vs. global USD price converted at USD/KRW.

    Emitted for every ``X-KRW`` that has a matching ``X-USD`` (or
    ``X-USDT``) on the watchlist. Positive % = Korean exchanges trade
    at a premium.
    """
    if not usdkrw or usdkrw <= 0:
        return []
    out: list[dict[str, Any]] = []
    for sym, q in (other_quotes or {}).items():
        if not sym.upper().endswith("-KRW"):
            continue
        base = sym.upper()[:-4]
        krw = _finite((q or {}).get("price"))
        usd = None
        for alt in (f"{base}-USD", f"{base}-USDT"):
            usd = _finite((other_quotes.get(alt) or {}).get("price"))
            if usd:
                break
        if not krw or not usd:
            continue
        global_krw = usd * usdkrw
        out.append({
            "asset": base,
            "krw_price": round(krw, 2),
            "global_krw_price": round(global_krw, 2),
            "premium_pct": round((krw / global_krw - 1) * 100, 2),
        })
    out.sort(key=lambda x: x["asset"])
    return out


_KR_OPEN, _KR_CLOSE = time(9, 0), time(15, 30)
_US_OPEN, _US_CLOSE = time(9, 30), time(16, 0)


def next_session_change(market: str, now: datetime | None = None) -> dict[str, Any]:
    """Return ``{"open": bool, "next": iso}`` — the next open or close.

    Weekend-aware, holiday-unaware (same simplification as
    market_hours.py — on a holiday the countdown points at an open
    that then doesn't happen, which is harmless).
    """
    tz, o, c = (TZ_KST, _KR_OPEN, _KR_CLOSE) if market == MARKET_KR else (TZ_NYC, _US_OPEN, _US_CLOSE)
    n = (now or datetime.now(tz)).astimezone(tz)
    weekday = n.weekday() < 5
    if weekday and o <= n.time() <= c:
        target = datetime.combine(n.date(), c, tz)
        return {"open": True, "next": target.isoformat()}
    day = n.date()
    if not (weekday and n.time() < o):
        day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return {"open": False, "next": datetime.combine(day, o, tz).isoformat()}


_INFO_KEYS = (
    "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "regularMarketDayHigh",
    "regularMarketDayLow", "regularMarketVolume", "marketState",
    "trailingPE", "dividendYield", "preMarketPrice", "postMarketPrice",
)

_INDEX_GROUP = {
    **{i: MARKET_KR for i in KR_INDICES},
    **{i: MARKET_US for i in US_INDICES},
    **{i: "GLOBAL" for i in GLOBAL_INDICES},
}


def _quote_row(
    key: str,
    quote: dict[str, Any] | None,
    info: dict[str, Any] | None,
) -> dict[str, Any]:
    q = quote or {}
    row: dict[str, Any] = {
        "price": _finite(q.get("price")),
        "change": _finite(q.get("change")),
        "change_pct": _finite(q.get("change_pct")),
        "prev_close": _finite(q.get("prev_close")),
        "asof": q.get("asof"),
        "stale": bool(q.get("stale", False)),
    }
    extra = {}
    for k in _INFO_KEYS:
        v = (info or {}).get(k)
        if v is not None:
            extra[k] = v
    if extra:
        row["info"] = extra
    return row


def positions_breakdown(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-position value / P&L — mirrors sensor._positions_breakdown,
    plus positions without a live quote (shown greyed out in the panel)."""
    kr_quotes = data.get("kr_quotes", {}) or {}
    us_quotes = data.get("us_quotes", {}) or {}
    out: list[dict[str, Any]] = []
    for p in data.get("positions", []) or []:
        ticker = p.get("ticker")
        market = p.get("market", MARKET_KR)
        qty = _finite(p.get("quantity")) or 0.0
        avg = _finite(p.get("avg_price")) or 0.0
        quotes = kr_quotes if market == MARKET_KR else us_quotes
        current = _finite((quotes.get(ticker) or {}).get("price"))
        row: dict[str, Any] = {
            "ticker": ticker,
            "market": market,
            "quantity": qty,
            "avg_price": avg,
            "current_price": current,
            "cost": round(avg * qty, 2),
            "value": None,
            "pl": None,
            "pl_pct": None,
        }
        if current is not None and qty > 0:
            value = current * qty
            row["value"] = round(value, 2)
            row["pl"] = round(value - avg * qty, 2)
            if avg > 0:
                row["pl_pct"] = round((current / avg - 1) * 100, 2)
        out.append(row)
    out.sort(key=lambda x: (x["market"] != MARKET_KR, str(x["ticker"])))
    return out


def build_snapshot(
    data: dict[str, Any] | None,
    cfg: dict[str, Any],
    disclosures: list[dict[str, Any]] | None = None,
    entity_ids: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Reshape coordinator.data into the panel's JSON document.

    ``entity_ids`` maps ``"KR:005930"`` / ``"INDEX:KOSPI"`` /
    ``"FX:USDKRW"`` → entity_id so the panel can open HA's more-info
    dialog (history graph) on long-press.
    """
    d = data or {}
    ids = entity_ids or {}
    info_all: dict[str, dict[str, Any]] = d.get("info", {}) or {}
    usdkrw = _finite(((d.get("fx", {}) or {}).get(FX_USDKRW, {}) or {}).get("price"))

    indices = []
    for name, q in (d.get("indices", {}) or {}).items():
        row = _quote_row(name, q, info_all.get(name))
        row.update({"key": name, "group": _INDEX_GROUP.get(name, "GLOBAL"),
                    "entity_id": ids.get(f"INDEX:{name}")})
        indices.append(row)

    fx = []
    for pair, q in (d.get("fx", {}) or {}).items():
        row = _quote_row(pair, q, info_all.get(pair))
        row.update({"key": pair, "entity_id": ids.get(f"FX:{pair}")})
        fx.append(row)

    kr_names = cfg.get(CONF_KR_TICKER_NAMES, {}) or {}
    us_labels = cfg.get(CONF_US_TICKER_LABELS, {}) or {}
    other_labels = cfg.get(CONF_OTHER_TICKER_LABELS, {}) or {}

    quotes: list[dict[str, Any]] = []
    for market, list_key, src, names in (
        (MARKET_KR, CONF_KR_TICKERS, "kr_quotes", kr_names),
        (MARKET_US, CONF_US_TICKERS, "us_quotes", us_labels),
        (MARKET_OTHER, CONF_OTHER_TICKERS, "other_quotes", other_labels),
    ):
        src_quotes = d.get(src, {}) or {}
        for ticker in cfg.get(list_key, []) or []:
            info = info_all.get(ticker)
            row = _quote_row(ticker, src_quotes.get(ticker), info)
            row.update({
                "key": f"{market}:{ticker}",
                "ticker": ticker,
                "market": market,
                "name": names.get(ticker) or (info or {}).get("shortName") or ticker,
                "kind": asset_kind(market, ticker, info),
                "currency": asset_currency(market, ticker, info),
                "entity_id": ids.get(f"{market}:{ticker}"),
            })
            if usdkrw and row["price"] is not None and row["currency"] == "USD":
                row["price_krw"] = round(row["price"] * usdkrw, 2)
            quotes.append(row)

    totals = compute_totals(d, usdkrw=usdkrw) if d else compute_totals({})
    positions = positions_breakdown(d)
    krw_total = totals.get("krw_total")
    krw_pl = totals.get("krw_pl")
    pl_pct = None
    if krw_total is not None and krw_pl is not None and (krw_total - krw_pl) > 0:
        pl_pct = round(krw_pl / (krw_total - krw_pl) * 100, 2)
    # Allocation share (KRW-converted) for the composition bar.
    if krw_total:
        for p in positions:
            if p["value"] is None:
                p["weight_pct"] = None
                continue
            krw_value = p["value"] * (usdkrw or 0) if p["market"] == MARKET_US else p["value"]
            p["weight_pct"] = round(krw_value / krw_total * 100, 2) if krw_value else None

    disc_rows = []
    for item in (disclosures or [])[:30]:
        disc_rows.append({
            "corp_name": item.get("corp_name"),
            "report_nm": item.get("report_nm"),
            "rcept_dt": item.get("rcept_dt"),
            "rcept_no": item.get("rcept_no"),
            "url": item.get("url"),
        })

    return {
        "ready": bool(d),
        "fetched_at": d.get("fetched_at"),
        "sessions": {
            MARKET_KR: next_session_change(MARKET_KR, now),
            MARKET_US: next_session_change(MARKET_US, now),
        },
        "usdkrw": usdkrw,
        "indices": indices,
        "fx": fx,
        "quotes": quotes,
        "kimchi": kimchi_premium(d.get("other_quotes", {}) or {}, usdkrw),
        "portfolio": {
            **totals,
            "krw_pl_pct": pl_pct,
            "positions": positions,
        },
        "disclosures": disc_rows,
        "disclosure_enabled": disclosures is not None,
    }


def match_kr_companies(
    mapping: dict[str, tuple[str, str]], query: str, limit: int = 8
) -> list[dict[str, Any]]:
    """Search OpenDart's listed-company map by Korean name or code prefix.

    ``mapping`` is ``stock_code → (corp_code, corp_name)`` (the cached
    corpCode.xml index). Ranking: exact name, then prefix, then
    substring; shorter names first within a tier so "삼성전자" beats
    "삼성전자우" style long tails.
    """
    q = (query or "").strip()
    if not q or not mapping:
        return []
    q_low = q.lower().replace(" ", "")
    scored: list[tuple[int, int, str, str]] = []
    for code, (_corp, name) in mapping.items():
        n_low = (name or "").lower().replace(" ", "")
        if q.isdigit():
            if code.startswith(q):
                scored.append((0 if code == q else 1, len(name), code, name))
            continue
        if not n_low:
            continue
        if n_low == q_low:
            tier = 0
        elif n_low.startswith(q_low):
            tier = 1
        elif q_low in n_low:
            tier = 2
        else:
            continue
        scored.append((tier, len(name), code, name))
    scored.sort()
    return [
        {"symbol": code, "name": name, "exchange": "KRX", "market": MARKET_KR}
        for _t, _l, code, name in scored[:limit]
    ]


def classify_search_hit(symbol: str, quote_type: str) -> tuple[str, str]:
    """Map a Yahoo search hit onto (panel_market, stored_ticker)."""
    s = symbol.upper()
    qt = (quote_type or "").upper()
    if s.endswith((".KS", ".KQ")):
        return MARKET_KR, s
    if qt == "CRYPTOCURRENCY":
        return MARKET_CRYPTO, s
    if qt in ("EQUITY", "ETF", "MUTUALFUND") and "." not in s and "=" not in s and not s.startswith("^"):
        return MARKET_US, s
    return MARKET_OTHER, s



# --------------------------------------------------------------------------
# First-install sample symbols
# --------------------------------------------------------------------------

# Large, widely-held public symbols only — never anyone's actual holdings.
DEFAULT_KR_TICKERS = ("005930", "000660")
DEFAULT_US_TICKERS = ("AAPL", "NVDA", "MSFT")
_DEFAULT_NAMES = {
    "ko": {
        "kr": {"005930": "삼성전자", "000660": "SK하이닉스"},
        "us": {"AAPL": "애플", "NVDA": "엔비디아", "MSFT": "마이크로소프트"},
        "other": {"BTC-KRW": "비트코인 (원화)", "BTC-USD": "비트코인 (달러)", "ETH-USD": "이더리움"},
    },
    "en": {
        "kr": {"005930": "Samsung Electronics", "000660": "SK hynix"},
        "us": {"AAPL": "Apple", "NVDA": "NVIDIA", "MSFT": "Microsoft"},
        "other": {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum"},
    },
}


def default_symbols(language: str | None) -> dict[str, Any]:
    """Sample watchlist for a first install with every ticker field blank.

    Korean-language installs also get ``BTC-KRW`` so the panel can show
    the kimchi premium out of the box. Labels are pre-filled so names show
    without an OpenDart key and without an extra Yahoo lookup during setup.
    """
    lang = "ko" if str(language or "").lower().startswith("ko") else "en"
    names = _DEFAULT_NAMES[lang]
    return {
        "kr": list(DEFAULT_KR_TICKERS),
        "us": list(DEFAULT_US_TICKERS),
        "other": list(names["other"]),
        "kr_names": dict(names["kr"]),
        "us_labels": dict(names["us"]),
        "other_labels": dict(names["other"]),
    }


# --------------------------------------------------------------------------
# Curated symbol catalog & code lookup URLs (broad selection in Add sheet)
# --------------------------------------------------------------------------

# Public, well-known market-cap leaders, major ETFs, top crypto assets,
# commodities, FX pairs, and global benchmarks only.
CODE_LOOKUP_URLS: dict[str, list[dict[str, str]]] = {
    MARKET_KR: [
        {
            "id": "krx",
            "label_ko": "KRX 상장법인 목록",
            "label_en": "KRX Listed Companies",
            "url": "https://kind.krx.co.kr/corpgeneral/corpList.do?method=loadInitPage",
        },
        {
            "id": "naver",
            "label_ko": "네이버 금융 시세",
            "label_en": "Naver Finance",
            "url": "https://finance.naver.com/sise/sise_market_sum.naver",
        },
    ],
    MARKET_US: [
        {
            "id": "yahoo_lookup",
            "label_ko": "Yahoo Finance 종목 검색",
            "label_en": "Yahoo Finance Lookup",
            "url": "https://finance.yahoo.com/lookup",
        },
    ],
    MARKET_CRYPTO: [
        {
            "id": "yahoo_crypto",
            "label_ko": "Yahoo Finance 코인 목록",
            "label_en": "Yahoo Finance Crypto",
            "url": "https://finance.yahoo.com/markets/crypto/all/",
        },
        {
            "id": "yahoo_lookup",
            "label_ko": "Yahoo Finance 검색",
            "label_en": "Yahoo Finance Lookup",
            "url": "https://finance.yahoo.com/lookup",
        },
    ],
    MARKET_OTHER: [
        {
            "id": "yahoo_lookup",
            "label_ko": "Yahoo Finance 검색",
            "label_en": "Yahoo Finance Lookup",
            "url": "https://finance.yahoo.com/lookup",
        },
        {
            "id": "yahoo_commodities",
            "label_ko": "Yahoo Finance 원자재·선물",
            "label_en": "Yahoo Finance Commodities",
            "url": "https://finance.yahoo.com/markets/commodities/",
        },
    ],
}

CATALOG_CATEGORIES: dict[str, list[tuple[str, str, str]]] = {
    # (category_id, label_ko, label_en)
    MARKET_KR: [
        ("all", "전체", "All"),
        ("tech", "반도체·IT", "Tech & Semi"),
        ("industrial", "자동차·배터리·중공업", "Auto & Industrial"),
        ("bio_fin", "바이오·금융·소비재", "Bio & Finance"),
        ("kosdaq", "코스닥 (.KQ)", "KOSDAQ (.KQ)"),
        ("etf", "국내 ETF", "KR ETF"),
    ],
    MARKET_US: [
        ("all", "전체", "All"),
        ("tech", "빅테크·AI", "Big Tech & AI"),
        ("bluechip", "금융·소비재·헬스", "Blue Chips"),
        ("etf", "미국 ETF", "US ETF"),
    ],
    MARKET_CRYPTO: [
        ("all", "전체", "All"),
        ("major", "메이저", "Major"),
        ("alt", "알트·밈", "Alt & Meme"),
    ],
    MARKET_OTHER: [
        ("all", "전체", "All"),
        ("commodity", "원자재·선물", "Commodities"),
        ("fx", "환율", "FX"),
        ("macro", "채권·변동성·글로벌", "Rates & Global"),
    ],
}

# Tuple layout: (symbol, name_ko, name_en, category, exchange)
SYMBOL_CATALOG: dict[str, tuple[tuple[str, str, str, str, str], ...]] = {
    MARKET_KR: (
        # tech
        ("005930", "삼성전자", "Samsung Electronics", "tech", "KOSPI"),
        ("000660", "SK하이닉스", "SK hynix", "tech", "KOSPI"),
        ("035420", "NAVER", "NAVER", "tech", "KOSPI"),
        ("035720", "카카오", "Kakao", "tech", "KOSPI"),
        ("006400", "삼성SDI", "Samsung SDI", "tech", "KOSPI"),
        ("009150", "삼성전기", "Samsung Electro-Mechanics", "tech", "KOSPI"),
        ("018260", "삼성에스디에스", "Samsung SDS", "tech", "KOSPI"),
        ("066570", "LG전자", "LG Electronics", "tech", "KOSPI"),
        ("017670", "SK텔레콤", "SK Telecom", "tech", "KOSPI"),
        ("030200", "KT", "KT Corp", "tech", "KOSPI"),
        ("259960", "크래프톤", "Krafton", "tech", "KOSPI"),
        # industrial
        ("005380", "현대차", "Hyundai Motor", "industrial", "KOSPI"),
        ("000270", "기아", "Kia", "industrial", "KOSPI"),
        ("012330", "현대모비스", "Hyundai Mobis", "industrial", "KOSPI"),
        ("373220", "LG에너지솔루션", "LG Energy Solution", "industrial", "KOSPI"),
        ("051910", "LG화학", "LG Chem", "industrial", "KOSPI"),
        ("005490", "POSCO홀딩스", "POSCO Holdings", "industrial", "KOSPI"),
        ("012450", "한화에어로스페이스", "Hanwha Aerospace", "industrial", "KOSPI"),
        ("329180", "HD현대중공업", "HD Hyundai Heavy Ind.", "industrial", "KOSPI"),
        ("034020", "두산에너빌리티", "Doosan Enerbility", "industrial", "KOSPI"),
        # bio_fin
        ("207940", "삼성바이오로직스", "Samsung Biologics", "bio_fin", "KOSPI"),
        ("068270", "셀트리온", "Celltrion", "bio_fin", "KOSPI"),
        ("105560", "KB금융", "KB Financial", "bio_fin", "KOSPI"),
        ("055550", "신한지주", "Shinhan Financial", "bio_fin", "KOSPI"),
        ("086790", "하나금융지주", "Hana Financial", "bio_fin", "KOSPI"),
        ("028260", "삼성물산", "Samsung C&T", "bio_fin", "KOSPI"),
        ("032830", "삼성생명", "Samsung Life", "bio_fin", "KOSPI"),
        ("033780", "KT&G", "KT&G", "bio_fin", "KOSPI"),
        # kosdaq
        ("247540.KQ", "에코프로비엠", "EcoPro BM", "kosdaq", "KOSDAQ"),
        ("086520.KQ", "에코프로", "EcoPro", "kosdaq", "KOSDAQ"),
        ("196170.KQ", "알테오젠", "Alteogen", "kosdaq", "KOSDAQ"),
        ("028300.KQ", "HLB", "HLB", "kosdaq", "KOSDAQ"),
        ("058470.KQ", "리노공업", "Leeno Industrial", "kosdaq", "KOSDAQ"),
        ("277810.KQ", "레인보우로보틱스", "Rainbow Robotics", "kosdaq", "KOSDAQ"),
        ("263750.KQ", "펄어비스", "Pearl Abyss", "kosdaq", "KOSDAQ"),
        ("035900.KQ", "JYP Ent.", "JYP Entertainment", "kosdaq", "KOSDAQ"),
        ("041510.KQ", "에스엠", "SM Entertainment", "kosdaq", "KOSDAQ"),
        # etf
        ("069500", "KODEX 200", "KODEX 200 ETF", "etf", "ETF"),
        ("102110", "TIGER 200", "TIGER 200 ETF", "etf", "ETF"),
        ("360750", "TIGER 미국S&P500", "TIGER US S&P500", "etf", "ETF"),
        ("133690", "TIGER 미국나스닥100", "TIGER US Nasdaq100", "etf", "ETF"),
        ("379800", "KODEX 미국S&P500", "KODEX US S&P500", "etf", "ETF"),
        ("379810", "KODEX 미국나스닥100", "KODEX US Nasdaq100", "etf", "ETF"),
        ("122630", "KODEX 레버리지", "KODEX Leverage", "etf", "ETF"),
        ("252670", "KODEX 200선물인버스2X", "KODEX Inverse 2X", "etf", "ETF"),
    ),
    MARKET_US: (
        # tech
        ("AAPL", "애플", "Apple", "tech", "NASDAQ"),
        ("MSFT", "마이크로소프트", "Microsoft", "tech", "NASDAQ"),
        ("NVDA", "엔비디아", "NVIDIA", "tech", "NASDAQ"),
        ("GOOGL", "알파벳 (구글)", "Alphabet (Google)", "tech", "NASDAQ"),
        ("AMZN", "아마존", "Amazon", "tech", "NASDAQ"),
        ("META", "메타", "Meta Platforms", "tech", "NASDAQ"),
        ("TSLA", "테슬라", "Tesla", "tech", "NASDAQ"),
        ("AVGO", "브로드컴", "Broadcom", "tech", "NASDAQ"),
        ("AMD", "AMD", "AMD", "tech", "NASDAQ"),
        ("TSM", "TSMC", "Taiwan Semiconductor", "tech", "NYSE"),
        ("ORCL", "오라클", "Oracle", "tech", "NYSE"),
        ("NFLX", "넷플릭스", "Netflix", "tech", "NASDAQ"),
        ("PLTR", "팔란티어", "Palantir", "tech", "NASDAQ"),
        ("INTC", "인텔", "Intel", "tech", "NASDAQ"),
        ("QCOM", "퀄컴", "Qualcomm", "tech", "NASDAQ"),
        ("ARM", "ARM", "Arm Holdings", "tech", "NASDAQ"),
        # bluechip
        ("BRK-B", "버크셔 해서웨이", "Berkshire Hathaway B", "bluechip", "NYSE"),
        ("JPM", "JP모건", "JPMorgan Chase", "bluechip", "NYSE"),
        ("V", "비자", "Visa", "bluechip", "NYSE"),
        ("MA", "마스터카드", "Mastercard", "bluechip", "NYSE"),
        ("LLY", "일라이 릴리", "Eli Lilly", "bluechip", "NYSE"),
        ("UNH", "유나이티드헬스", "UnitedHealth", "bluechip", "NYSE"),
        ("JNJ", "존슨앤드존슨", "Johnson & Johnson", "bluechip", "NYSE"),
        ("WMT", "월마트", "Walmart", "bluechip", "NYSE"),
        ("COST", "코스트코", "Costco", "bluechip", "NASDAQ"),
        ("KO", "코카콜라", "Coca-Cola", "bluechip", "NYSE"),
        ("PEP", "펩시코", "PepsiCo", "bluechip", "NASDAQ"),
        ("MCD", "맥도날드", "McDonald's", "bluechip", "NYSE"),
        ("SBUX", "스타벅스", "Starbucks", "bluechip", "NASDAQ"),
        ("DIS", "디즈니", "Walt Disney", "bluechip", "NYSE"),
        ("NKE", "나이키", "Nike", "bluechip", "NYSE"),
        ("XOM", "엑슨모빌", "Exxon Mobil", "bluechip", "NYSE"),
        ("BA", "보잉", "Boeing", "bluechip", "NYSE"),
        # etf
        ("SPY", "S&P 500 (SPY)", "SPDR S&P 500 ETF", "etf", "ETF"),
        ("VOO", "Vanguard S&P 500", "Vanguard S&P 500 ETF", "etf", "ETF"),
        ("QQQ", "나스닥 100 (QQQ)", "Invesco QQQ Trust", "etf", "ETF"),
        ("QQQM", "나스닥 100 미니 (QQQM)", "Invesco NASDAQ 100", "etf", "ETF"),
        ("SCHD", "미국 배당 (SCHD)", "Schwab US Dividend ETF", "etf", "ETF"),
        ("SOXX", "반도체 (SOXX)", "iShares Semiconductor ETF", "etf", "ETF"),
        ("SMH", "반에크 반도체 (SMH)", "VanEck Semiconductor ETF", "etf", "ETF"),
        ("TQQQ", "나스닥 3x (TQQQ)", "ProShares UltraPro QQQ", "etf", "ETF"),
        ("SQQQ", "나스닥 인버스 3x", "ProShares UltraPro Short QQQ", "etf", "ETF"),
        ("SOXL", "반도체 3x (SOXL)", "Direxion Semi Bull 3X", "etf", "ETF"),
        ("TLT", "미국 장기국채 (TLT)", "iShares 20+ Yr Treasury", "etf", "ETF"),
        ("GLD", "금 현물 ETF (GLD)", "SPDR Gold Shares", "etf", "ETF"),
        ("JEPI", "커버드콜 배당 (JEPI)", "JPMorgan Equity Premium", "etf", "ETF"),
        ("JEPQ", "나스닥 커버드콜 (JEPQ)", "JPMorgan Nasdaq Premium", "etf", "ETF"),
        ("IBIT", "비트코인 현물 ETF", "iShares Bitcoin Trust", "etf", "ETF"),
    ),
    MARKET_CRYPTO: (
        # major
        ("BTC", "비트코인", "Bitcoin", "major", "Crypto"),
        ("ETH", "이더리움", "Ethereum", "major", "Crypto"),
        ("SOL", "솔라나", "Solana", "major", "Crypto"),
        ("XRP", "리플", "XRP", "major", "Crypto"),
        ("BNB", "바이낸스코인", "BNB", "major", "Crypto"),
        ("ADA", "에이다", "Cardano", "major", "Crypto"),
        ("AVAX", "아발란체", "Avalanche", "major", "Crypto"),
        ("LINK", "체인링크", "Chainlink", "major", "Crypto"),
        ("DOT", "폴카닷", "Polkadot", "major", "Crypto"),
        ("TRX", "트론", "TRON", "major", "Crypto"),
        ("TON", "톤코인", "Toncoin", "major", "Crypto"),
        ("SUI", "수이", "Sui", "major", "Crypto"),
        ("LTC", "라이트코인", "Litecoin", "major", "Crypto"),
        ("BCH", "비트코인캐시", "Bitcoin Cash", "major", "Crypto"),
        ("UNI", "유니스왑", "Uniswap", "major", "Crypto"),
        ("ATOM", "코스모스", "Cosmos", "major", "Crypto"),
        ("NEAR", "니어프로토콜", "NEAR Protocol", "major", "Crypto"),
        ("APT", "앱토스", "Aptos", "major", "Crypto"),
        # alt
        ("DOGE", "도지코인", "Dogecoin", "alt", "Crypto"),
        ("SHIB", "시바이누", "Shiba Inu", "alt", "Crypto"),
        ("PEPE", "페페", "Pepe", "alt", "Crypto"),
        ("POL", "폴리곤", "Polygon", "alt", "Crypto"),
        ("XLM", "스텔라루멘", "Stellar", "alt", "Crypto"),
        ("ETC", "이더리움클래식", "Ethereum Classic", "alt", "Crypto"),
        ("HBAR", "헤데라", "Hedera", "alt", "Crypto"),
    ),
    MARKET_OTHER: (
        # commodity
        ("GC=F", "금 선물", "Gold Futures", "commodity", "COMEX"),
        ("SI=F", "은 선물", "Silver Futures", "commodity", "COMEX"),
        ("HG=F", "구리 선물", "Copper Futures", "commodity", "COMEX"),
        ("CL=F", "WTI 원유", "Crude Oil (WTI)", "commodity", "NYMEX"),
        ("BZ=F", "브렌트유", "Brent Crude Oil", "commodity", "ICE"),
        ("NG=F", "천연가스", "Natural Gas", "commodity", "NYMEX"),
        ("ZW=F", "밀 선물", "Wheat Futures", "commodity", "CBOT"),
        ("ZC=F", "옥수수 선물", "Corn Futures", "commodity", "CBOT"),
        # fx
        ("JPYKRW=X", "엔/원 환율", "JPY/KRW", "fx", "FX"),
        ("EURKRW=X", "유로/원 환율", "EUR/KRW", "fx", "FX"),
        ("CNYKRW=X", "위안/원 환율", "CNY/KRW", "fx", "FX"),
        ("EURUSD=X", "유로/달러", "EUR/USD", "fx", "FX"),
        ("USDJPY=X", "달러/엔", "USD/JPY", "fx", "FX"),
        ("GBPUSD=X", "파운드/달러", "GBP/USD", "fx", "FX"),
        ("DX-Y.NYB", "달러 인덱스 (DXY)", "US Dollar Index", "fx", "ICE"),
        # macro
        ("^VIX", "공포지수 (VIX)", "CBOE Volatility Index", "macro", "CBOE"),
        ("^TNX", "미국 10년물 국채금리", "US 10-Yr Treasury Yield", "macro", "CBOE"),
        ("^TYX", "미국 30년물 국채금리", "US 30-Yr Treasury Yield", "macro", "CBOE"),
        ("^IRX", "미국 13주 국채금리", "US 13-Week T-Bill", "macro", "CBOE"),
        ("7203.T", "토요타 (일본)", "Toyota Motor", "macro", "TSE"),
        ("6758.T", "소니 (일본)", "Sony Group", "macro", "TSE"),
        ("9988.HK", "알리바바 (홍콩)", "Alibaba Group", "macro", "HKEX"),
        ("0700.HK", "텐센트 (홍콩)", "Tencent Holdings", "macro", "HKEX"),
    ),
}


def catalog_for_market(
    market: str,
    *,
    category: str = "all",
    lang: str = "ko",
    query: str = "",
    extra_kr_map: dict[str, tuple[str, str]] | None = None,
    limit: int = 80,
) -> dict[str, Any]:
    """Return browsable symbol catalog, categories, and code-lookup URLs.

    When ``market == "KR"`` and ``extra_kr_map`` (OpenDart's full ~2,600
    listed company map) is supplied, an extra ``krx_all`` category lets the
    user browse or filter every KRX listed stock directly.
    """
    is_ko = str(lang or "").lower().startswith("ko")
    m = market if market in SYMBOL_CATALOG else MARKET_KR
    q = (query or "").strip().lower().replace(" ", "")

    categories = [
        {"id": cid, "label": l_ko if is_ko else l_en}
        for cid, l_ko, l_en in CATALOG_CATEGORIES.get(m, [])
    ]
    if m == MARKET_KR and extra_kr_map:
        categories.append({
            "id": "krx_all",
            "label": f"KRX 전체 ({len(extra_kr_map):,})" if is_ko else f"All KRX ({len(extra_kr_map):,})",
        })

    links = [
        {
            "id": link["id"],
            "label": link["label_ko"] if is_ko else link["label_en"],
            "url": link["url"],
        }
        for link in CODE_LOOKUP_URLS.get(m, [])
    ]

    items: list[dict[str, Any]] = []
    if m == MARKET_KR and category == "krx_all" and extra_kr_map:
        if q:
            items = match_kr_companies(extra_kr_map, query, limit=limit)
        else:
            ordered = sorted(extra_kr_map.items(), key=lambda kv: (kv[1][1] or kv[0]))
            items = [
                {"symbol": code, "name": name, "exchange": "KRX", "market": MARKET_KR, "category": "krx_all"}
                for code, (_corp, name) in ordered[:limit]
            ]
    else:
        for sym, name_ko, name_en, cat, exch in SYMBOL_CATALOG[m]:
            if category and category != "all" and cat != category:
                continue
            if q:
                hay = f"{sym} {name_ko} {name_en} {exch}".lower().replace(" ", "")
                if q not in hay:
                    continue
            items.append({
                "symbol": sym,
                "name": name_ko if is_ko else name_en,
                "name_en": name_en,
                "category": cat,
                "exchange": exch,
                "market": m,
            })
            if len(items) >= limit:
                break

    return {
        "market": m,
        "categories": categories,
        "items": items,
        "links": links,
        "krx_total": len(extra_kr_map) if (m == MARKET_KR and extra_kr_map) else 0,
    }


def match_catalog(
    query: str,
    *,
    market: str | None = None,
    lang: str = "ko",
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Search the built-in catalog by Korean/English name or symbol.

    Gives instant Korean-name search even without an OpenDart API key,
    and complements Yahoo Search (which doesn't index Korean names).
    """
    q = (query or "").strip()
    if not q:
        return []
    q_low = q.lower().replace(" ", "")
    is_ko = str(lang or "").lower().startswith("ko")
    markets = (market,) if market in SYMBOL_CATALOG else tuple(SYMBOL_CATALOG)
    scored: list[tuple[int, int, str, str, str, str]] = []
    for m in markets:
        for sym, name_ko, name_en, _cat, exch in SYMBOL_CATALOG[m]:
            sym_low = sym.lower()
            ko_low = name_ko.lower().replace(" ", "")
            en_low = name_en.lower().replace(" ", "")
            if q_low in (sym_low, sym_low.split(".")[0], ko_low, en_low):
                tier = 0
            elif sym_low.startswith(q_low) or ko_low.startswith(q_low) or en_low.startswith(q_low):
                tier = 1
            elif q_low in sym_low or q_low in ko_low or q_low in en_low:
                tier = 2
            else:
                continue
            display = name_ko if is_ko else name_en
            scored.append((tier, len(display), sym, display, exch, m))
    scored.sort()
    return [
        {"symbol": sym, "name": display, "exchange": exch, "market": m}
        for _t, _l, sym, display, exch, m in scored[:limit]
    ]
