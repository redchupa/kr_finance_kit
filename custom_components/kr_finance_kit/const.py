"""Constants for KR Finance Kit."""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

DOMAIN = "kr_finance_kit"

# Short prefix used for entity_id slugs ONLY (not for unique_id, which
# stays on DOMAIN so HA's registry uniqueness keeps working even if the
# prefix ever changes). We intentionally use a 2-letter prefix to keep
# entity_ids short and visually distinct from other finance/stock
# integrations in the user's HA (sensor.fi_kospi vs.
# sensor.yahoofinance_kospi etc).
ENTITY_ID_PREFIX = "fi"

LOGGER = logging.getLogger(__package__)
TZ_KST = ZoneInfo("Asia/Seoul")

CONF_OPENDART_API_KEY = "opendart_api_key"
CONF_KR_TICKERS = "kr_tickers"
CONF_US_TICKERS = "us_tickers"
CONF_OTHER_TICKERS = "other_tickers"  # crypto/forex/futures — 24/7 fetch, no market-hours gating
CONF_OTHER_TICKER_LABELS = "other_ticker_labels"  # dict[ticker, friendly_label]
CONF_US_TICKER_LABELS = "us_ticker_labels"  # dict[ticker, friendly_label] — same pattern as KR ticker names
CONF_POSITIONS = "positions"  # list[{ticker, quantity, avg_price, market}]
CONF_DISCLOSURE_CORP_CODES = "disclosure_corp_codes"
CONF_DISCLOSURE_CORP_NAMES = "disclosure_corp_names"  # dict[corp_code, corp_name] for binary_sensor friendly label
CONF_KR_TICKER_NAMES = "kr_ticker_names"  # dict[stock_code, corp_name] for friendly labels
CONF_INCLUDE_INDICES = "include_indices"
CONF_INCLUDE_US_INDICES = "include_us_indices"
CONF_INCLUDE_GLOBAL_INDICES = "include_global_indices"  # Nikkei / Hang Seng / FTSE / DAX
CONF_INCLUDE_FX = "include_fx"
# KRW per asset native currency. Off by default; when set, QuoteSensor
# attributes carry price_krw alongside the native value so dashboards
# can show "BTC ≈ 80,000,000 KRW" without a template.
CONF_TARGET_CURRENCY_KRW = "target_currency_krw"
# Trigger threshold for the portfolio P/L alert binary_sensor. Stored
# as a positive percentage; the sensor goes ON when the absolute
# portfolio_krw_pl_pct crosses ±threshold. 0 disables (default).
CONF_PORTFOLIO_PL_ALERT_PCT = "portfolio_pl_alert_pct"
# OpenDart disclosure category filter. Empty list = all categories
# (current behavior). Codes follow OpenDart's pblntf_ty parameter:
#   A=정기공시, B=주요사항보고, C=발행공시, D=지분공시, E=기타공시,
#   F=외부감사관련, G=펀드공시, H=자산유동화, I=거래소공시, J=공정위공시
CONF_DISCLOSURE_CATEGORIES = "disclosure_categories"
# Fixed list of short-window minutes emitted as change_pct_<N>min
# attributes on every QuoteSensor. Hard-coded instead of an option:
# the blueprint already takes a per-automation minute input, so a
# global CSV in the integration form was a second place to edit the
# same number. Eight values cover the common "alert me on a fast
# move" needs without bloating each sensor with hundreds of
# attributes. Custom values aren't supported — change this tuple
# and reload the integration if a project needs another minute.
DEFAULT_SHORT_WINDOW_MINUTES = (1, 5, 15, 30, 60, 90, 120, 180)
# When True, the coordinator pulls yfinance .info per ticker so sensors
# expose richer attributes (52w high/low, 50d/200d MA, day high/low,
# volumes, dividends, PE, marketState, pre/post-market prices). Costs
# ~1 extra HTTP round-trip per ticker per poll, so it defaults OFF —
# users who want the data turn it on in Options.
CONF_INCLUDE_DETAILED_ATTRS = "include_detailed_attrs"

SCAN_INTERVAL_MARKET = 60       # seconds — at least one market open
SCAN_INTERVAL_MARKET_IDLE = 600  # seconds — both markets closed (overnight, weekends)
SCAN_INTERVAL_DISCLOSURE = 300   # seconds — OpenDart polling

INDEX_KOSPI = "KOSPI"
INDEX_KOSDAQ = "KOSDAQ"
INDEX_NASDAQ = "NASDAQ"
INDEX_DOW = "DOW"
INDEX_SP500 = "SP500"
INDEX_NIKKEI = "NIKKEI"
INDEX_HANGSENG = "HANGSENG"
INDEX_FTSE = "FTSE"
INDEX_DAX = "DAX"
KR_INDICES = (INDEX_KOSPI, INDEX_KOSDAQ)
US_INDICES = (INDEX_NASDAQ, INDEX_DOW, INDEX_SP500)
GLOBAL_INDICES = (INDEX_NIKKEI, INDEX_HANGSENG, INDEX_FTSE, INDEX_DAX)
FX_USDKRW = "USDKRW"

# HA event bus names fired when each market session closes. Picks up
# the transition where the prior coordinator tick saw the market open
# and the current one sees it closed.
EVENT_KR_MARKET_CLOSED = f"{DOMAIN}_kr_market_closed"
EVENT_US_MARKET_CLOSED = f"{DOMAIN}_us_market_closed"

# OpenDart disclosure category codes (pblntf_ty values). Surfaced so
# config_flow can present them as a selector and coordinator can pass
# the filter through to api.opendart.fetch_recent_disclosures.
DISCLOSURE_CATEGORY_CODES = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")

# Korean labels for the OpenDart pblntf_ty codes, used by the
# SelectSelector in config_flow so the dropdown shows
# "A — 정기공시" instead of a bare "A". Code value stays unchanged
# (entry.data + OpenDart request keep using the single-letter form).
DISCLOSURE_CATEGORY_LABELS = {
    "A": "A — 정기공시",
    "B": "B — 주요사항보고",
    "C": "C — 발행공시",
    "D": "D — 지분공시",
    "E": "E — 기타공시",
    "F": "F — 외부감사관련",
    "G": "G — 펀드공시",
    "H": "H — 자산유동화",
    "I": "I — 거래소공시",
    "J": "J — 공정위공시",
}

MARKET_KR = "KR"
MARKET_US = "US"
MARKET_OTHER = "OTHER"  # crypto, forex, futures, commodities — Yahoo ticker passed through

# Donation meta — intentionally public per MASTER_PLAN.md.
DONATION_MANUFACTURER = "우*만"
DONATION_MODEL = "토스 1000-1261-7813"
DONATION_SW_VERSION = "커피 한잔은 사랑입니다 ☕"
