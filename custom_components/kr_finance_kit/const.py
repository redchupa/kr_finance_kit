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
CONF_KR_TICKER_NAMES = "kr_ticker_names"  # dict[stock_code, corp_name] for friendly labels
CONF_INCLUDE_INDICES = "include_indices"
CONF_INCLUDE_US_INDICES = "include_us_indices"
CONF_INCLUDE_FX = "include_fx"
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
KR_INDICES = (INDEX_KOSPI, INDEX_KOSDAQ)
US_INDICES = (INDEX_NASDAQ, INDEX_DOW, INDEX_SP500)
FX_USDKRW = "USDKRW"

MARKET_KR = "KR"
MARKET_US = "US"
MARKET_OTHER = "OTHER"  # crypto, forex, futures, commodities — Yahoo ticker passed through

# Donation meta — intentionally public per MASTER_PLAN.md.
DONATION_MANUFACTURER = "우*만"
DONATION_MODEL = "토스 1000-1261-7813"
DONATION_SW_VERSION = "커피 한잔은 사랑입니다 ☕"
