"""Sensor platform — indices, FX, ticker quotes, portfolio P/L."""
from __future__ import annotations

import math
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_INCLUDE_FX,
    CONF_INCLUDE_INDICES,
    CONF_INCLUDE_US_INDICES,
    CONF_KR_TICKER_NAMES,
    DOMAIN,
    ENTITY_ID_PREFIX,
    FX_USDKRW,
    KR_INDICES,
    MARKET_KR,
    MARKET_OTHER,
    MARKET_US,
    US_INDICES,
)
from .coordinator import MarketCoordinator
from .device import market_device, portfolio_device, ticker_device, us_market_device
from .portfolio import compute_totals


def _entry_value(entry: ConfigEntry, key: str, default: Any) -> Any:
    return (entry.options or entry.data).get(key, default)


_INFO_KEY_MAP: dict[str, str] = {
    "fiftyTwoWeekHigh": "fifty_two_week_high",
    "fiftyTwoWeekLow": "fifty_two_week_low",
    "fiftyDayAverage": "fifty_day_average",
    "twoHundredDayAverage": "two_hundred_day_average",
    "regularMarketDayHigh": "regular_market_day_high",
    "regularMarketDayLow": "regular_market_day_low",
    "regularMarketVolume": "regular_market_volume",
    "marketState": "market_state",
    "currency": "currency",
    "quoteType": "quote_type",
    "longName": "long_name",
    "shortName": "short_name",
    "averageDailyVolume10Day": "average_daily_volume_10_day",
    "averageVolume": "average_volume",
    # Equity-only — surfaced only when present in .info (None entries are
    # dropped by the yfinance_wrap filter, so absence here means the asset
    # class doesn't carry the field).
    "dividendRate": "dividend_rate",
    "dividendYield": "dividend_yield",
    "trailingAnnualDividendRate": "trailing_annual_dividend_rate",
    "dividendDate": "dividend_date",
    "forwardPE": "forward_pe",
    "trailingPE": "trailing_pe",
    "preMarketPrice": "pre_market_price",
    "postMarketPrice": "post_market_price",
}


def _info_attrs(coordinator: MarketCoordinator, key: str, price: float | None) -> dict[str, Any]:
    """Translate yfinance .info into snake_case attrs + derived change_pct.

    iprak/yahoofinance gets ``fiftyTwoWeekHighChangePercent`` etc. directly
    from Yahoo's v7 quote API. yfinance's .info doesn't ship those derived
    percentages so we compute them ourselves against the current price.
    Returns ``{}`` when detailed-attrs is off or yfinance returned nothing
    for this symbol.
    """
    info = (coordinator.data or {}).get("info", {}).get(key, {}) or {}
    if not info:
        return {}
    out: dict[str, Any] = {}
    for src, dst in _INFO_KEY_MAP.items():
        v = info.get(src)
        if v is not None:
            out[dst] = v
    if price is not None and price > 0:
        for src, dst in (
            ("fiftyTwoWeekHigh", "fifty_two_week_high_change_pct"),
            ("fiftyTwoWeekLow", "fifty_two_week_low_change_pct"),
            ("fiftyDayAverage", "fifty_day_average_change_pct"),
            ("twoHundredDayAverage", "two_hundred_day_average_change_pct"),
        ):
            base = info.get(src)
            if isinstance(base, (int, float)) and base > 0:
                out[dst] = round((price / base - 1) * 100, 2)
    return out


def _finite(value: Any) -> float | None:
    """Defense-in-depth guard for native_value.

    Even though the yfinance layer filters NaN, a future data source might
    not. HA's SensorEntity raises ValueError on non-finite values when
    ``state_class`` is set, which crashes entity registration. Returning
    ``None`` here makes the sensor show "unknown" instead of breaking.
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]
    market: MarketCoordinator = store["market"]

    entities: list[SensorEntity] = []

    if _entry_value(entry, CONF_INCLUDE_INDICES, True):
        entities += [IndexSensor(market, idx, MARKET_KR) for idx in KR_INDICES]
    if _entry_value(entry, CONF_INCLUDE_US_INDICES, True):
        entities += [IndexSensor(market, idx, MARKET_US) for idx in US_INDICES]
    if _entry_value(entry, CONF_INCLUDE_FX, True):
        entities.append(FXSensor(market, FX_USDKRW))

    kr_names: dict[str, str] = _entry_value(entry, CONF_KR_TICKER_NAMES, {}) or {}
    us_labels = market.us_ticker_labels
    other_labels = market.other_ticker_labels
    for ticker in market.kr_tickers:
        entities.append(QuoteSensor(market, MARKET_KR, ticker, label=kr_names.get(ticker)))
    for ticker in market.us_tickers:
        entities.append(QuoteSensor(market, MARKET_US, ticker, label=us_labels.get(ticker)))
    for ticker in market.other_tickers:
        entities.append(QuoteSensor(market, MARKET_OTHER, ticker, label=other_labels.get(ticker)))

    if market.positions:
        entities += [
            PortfolioKRValueSensor(market),
            PortfolioKRPLSensor(market),
            PortfolioUSValueSensor(market),
            PortfolioUSPLSensor(market),
            PortfolioKRWTotalSensor(market),
            PortfolioKRWPLSensor(market),
        ]

    if entities:
        async_add_entities(entities)


class _MarketBase(CoordinatorEntity[MarketCoordinator], SensorEntity):
    _attr_has_entity_name = True


class IndexSensor(_MarketBase):
    _attr_icon = "mdi:chart-line"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MarketCoordinator, index: str, market: str = MARKET_KR) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_unique_id = f"{DOMAIN}_index_{index.lower()}"
        # Pin entity_id to a short English slug (sensor.fi_kospi etc.).
        # unique_id stays on DOMAIN so HA registry uniqueness survives,
        # but entity_id is the shorter ENTITY_ID_PREFIX form to keep
        # automations + dashboards readable and to dodge collisions
        # with other finance integrations in the user's HA.
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_{index.lower()}"
        self._attr_name = index
        self._attr_device_info = us_market_device() if market == MARKET_US else market_device()

    @property
    def native_value(self) -> float | None:
        data = (self.coordinator.data or {}).get("indices", {})
        return _finite(data.get(self._index, {}).get("price"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = (self.coordinator.data or {}).get("indices", {})
        base = {k: v for k, v in data.get(self._index, {}).items() if k != "price"}
        base.update(_info_attrs(self.coordinator, self._index, self.native_value))
        return base


class FXSensor(_MarketBase):
    _attr_icon = "mdi:currency-usd"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "KRW"

    def __init__(self, coordinator: MarketCoordinator, pair: str) -> None:
        super().__init__(coordinator)
        self._pair = pair
        self._attr_unique_id = f"{DOMAIN}_fx_{pair.lower()}"
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_{pair.lower()}"
        self._attr_name = pair
        self._attr_device_info = market_device()

    @property
    def native_value(self) -> float | None:
        v = (self.coordinator.data or {}).get("fx", {}).get(self._pair, {}).get("price")
        return _finite(v)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = (self.coordinator.data or {}).get("fx", {}).get(self._pair, {})
        base = {k: v for k, v in data.items() if k != "price"}
        base.update(_info_attrs(self.coordinator, self._pair, self.native_value))
        return base


class QuoteSensor(_MarketBase):
    _attr_icon = "mdi:cash"
    _attr_state_class = SensorStateClass.MEASUREMENT
    # The device already carries the company/ticker name; with
    # has_entity_name=True (inherited from _MarketBase), setting name=None
    # makes HA use the device name as the friendly name. Setting an entity
    # name here would produce "삼성전자 삼성전자" duplication.
    _attr_name = None

    def __init__(
        self,
        coordinator: MarketCoordinator,
        market: str,
        ticker: str,
        label: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._market = market
        self._ticker = ticker
        self._attr_unique_id = f"{DOMAIN}_{market.lower()}_{ticker}"
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_{market.lower()}_{ticker.lower()}"
        # Device label is the single source of truth for the friendly
        # name: "삼성전자" when resolved, "KR 005930" otherwise. Both the
        # unique_id and entity_id stay code-based so automations don't
        # break when names are added/removed later.
        self._attr_device_info = ticker_device(market, ticker, label)
        # KR tickers are reported in KRW; US and "other" assets (crypto,
        # forex, futures) default to USD because Yahoo Finance reports
        # them in USD for the common ticker forms (BTC-USD, ETH-USD,
        # EUR=X, GC=F). Users who want native currency or KRW conversion
        # can layer that on top via target_currency in a later release.
        self._attr_native_unit_of_measurement = "KRW" if market == MARKET_KR else "USD"

    @property
    def _quote(self) -> dict[str, Any]:
        key = {
            MARKET_KR: "kr_quotes",
            MARKET_US: "us_quotes",
            MARKET_OTHER: "other_quotes",
        }.get(self._market, "us_quotes")
        return (self.coordinator.data or {}).get(key, {}).get(self._ticker, {}) or {}

    @property
    def native_value(self) -> float | None:
        return _finite(self._quote.get("price"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        base = {k: v for k, v in self._quote.items() if k != "price"}
        base.update(_info_attrs(self.coordinator, self._ticker, self.native_value))
        return base


def _usdkrw(coord: MarketCoordinator) -> float | None:
    rate = (coord.data or {}).get("fx", {}).get(FX_USDKRW, {}).get("price")
    return _finite(rate)


class _PortfolioBase(_MarketBase):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MarketCoordinator, key: str, name: str, unit: str, icon: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{DOMAIN}_portfolio_{key}"
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_portfolio_{key.lower()}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_info = portfolio_device()

    @property
    def native_value(self) -> float | None:
        totals = compute_totals(self.coordinator.data or {}, usdkrw=_usdkrw(self.coordinator))
        return _finite(totals.get(self._key))


class PortfolioKRValueSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "kr_value", "한국 보유 평가금액", "KRW", "mdi:briefcase-variant")


class PortfolioKRPLSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "kr_pl", "한국 보유 평가손익", "KRW", "mdi:trending-up")


class PortfolioUSValueSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "us_value", "미국 보유 평가금액", "USD", "mdi:briefcase-variant")


class PortfolioUSPLSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "us_pl", "미국 보유 평가손익", "USD", "mdi:trending-up")


class PortfolioKRWTotalSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "krw_total", "총 평가금액 (KRW 환산)", "KRW", "mdi:briefcase-check")


class PortfolioKRWPLSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "krw_pl", "총 평가손익 (KRW 환산)", "KRW", "mdi:cash-multiple")
