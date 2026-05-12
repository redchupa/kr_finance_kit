"""Constants for KR Finance Kit."""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

DOMAIN = "kr_finance_kit"
LOGGER = logging.getLogger(__package__)
TZ_KST = ZoneInfo("Asia/Seoul")

CONF_OPENDART_API_KEY = "opendart_api_key"
CONF_KR_TICKERS = "kr_tickers"
CONF_US_TICKERS = "us_tickers"
CONF_POSITIONS = "positions"  # list[{ticker, quantity, avg_price, market}]
CONF_DISCLOSURE_CORP_CODES = "disclosure_corp_codes"
CONF_KR_TICKER_NAMES = "kr_ticker_names"  # dict[stock_code, corp_name] for friendly labels
CONF_INCLUDE_INDICES = "include_indices"
CONF_INCLUDE_FX = "include_fx"

SCAN_INTERVAL_MARKET = 60       # seconds — at least one market open
SCAN_INTERVAL_MARKET_IDLE = 600  # seconds — both markets closed (overnight, weekends)
SCAN_INTERVAL_DISCLOSURE = 300   # seconds — OpenDart polling

INDEX_KOSPI = "KOSPI"
INDEX_KOSDAQ = "KOSDAQ"
FX_USDKRW = "USDKRW"

MARKET_KR = "KR"
MARKET_US = "US"

# Donation meta — intentionally public per MASTER_PLAN.md.
DONATION_MANUFACTURER = "우*만"
DONATION_MODEL = "토스 1000-1261-7813"
DONATION_SW_VERSION = "커피 한잔은 사랑입니다 ☕"
