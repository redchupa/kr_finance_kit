"""Sensor platform — indices, FX, ticker quotes, portfolio P/L."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_INCLUDE_FX,
    CONF_INCLUDE_INDICES,
    DOMAIN,
    FX_USDKRW,
    INDEX_KOSDAQ,
    INDEX_KOSPI,
    MARKET_KR,
    MARKET_US,
)
from .coordinator import MarketCoordinator
from .device import market_device, portfolio_device, ticker_device
from .portfolio import compute_totals


def _entry_value(entry: ConfigEntry, key: str, default: Any) -> Any:
    return (entry.options or entry.data).get(key, default)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]
    market: MarketCoordinator = store["market"]

    entities: list[SensorEntity] = []

    if _entry_value(entry, CONF_INCLUDE_INDICES, True):
        entities += [
            IndexSensor(market, INDEX_KOSPI),
            IndexSensor(market, INDEX_KOSDAQ),
        ]
    if _entry_value(entry, CONF_INCLUDE_FX, True):
        entities.append(FXSensor(market, FX_USDKRW))

    for ticker in market.kr_tickers:
        entities.append(QuoteSensor(market, MARKET_KR, ticker))
    for ticker in market.us_tickers:
        entities.append(QuoteSensor(market, MARKET_US, ticker))

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

    def __init__(self, coordinator: MarketCoordinator, index: str) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_unique_id = f"{DOMAIN}_index_{index.lower()}"
        self._attr_name = index
        self._attr_device_info = market_device()

    @property
    def native_value(self) -> float | None:
        data = (self.coordinator.data or {}).get("indices", {})
        v = data.get(self._index, {}).get("price")
        return float(v) if v is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = (self.coordinator.data or {}).get("indices", {})
        return {k: v for k, v in data.get(self._index, {}).items() if k != "price"}


class FXSensor(_MarketBase):
    _attr_icon = "mdi:currency-usd"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "KRW"

    def __init__(self, coordinator: MarketCoordinator, pair: str) -> None:
        super().__init__(coordinator)
        self._pair = pair
        self._attr_unique_id = f"{DOMAIN}_fx_{pair.lower()}"
        self._attr_name = pair
        self._attr_device_info = market_device()

    @property
    def native_value(self) -> float | None:
        v = (self.coordinator.data or {}).get("fx", {}).get(self._pair, {}).get("price")
        return float(v) if v is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = (self.coordinator.data or {}).get("fx", {}).get(self._pair, {})
        return {k: v for k, v in data.items() if k != "price"}


class QuoteSensor(_MarketBase):
    _attr_icon = "mdi:cash"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MarketCoordinator, market: str, ticker: str) -> None:
        super().__init__(coordinator)
        self._market = market
        self._ticker = ticker
        self._attr_unique_id = f"{DOMAIN}_{market.lower()}_{ticker}"
        self._attr_name = f"{ticker}"
        self._attr_device_info = ticker_device(market, ticker)
        self._attr_native_unit_of_measurement = "KRW" if market == MARKET_KR else "USD"

    @property
    def _quote(self) -> dict[str, Any]:
        key = "kr_quotes" if self._market == MARKET_KR else "us_quotes"
        return (self.coordinator.data or {}).get(key, {}).get(self._ticker, {}) or {}

    @property
    def native_value(self) -> float | None:
        v = self._quote.get("price")
        return float(v) if v is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {k: v for k, v in self._quote.items() if k != "price"}


def _usdkrw(coord: MarketCoordinator) -> float | None:
    rate = (coord.data or {}).get("fx", {}).get(FX_USDKRW, {}).get("price")
    return float(rate) if rate else None


class _PortfolioBase(_MarketBase):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MarketCoordinator, key: str, name: str, unit: str, icon: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{DOMAIN}_portfolio_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_info = portfolio_device()

    @property
    def native_value(self) -> float | None:
        totals = compute_totals(self.coordinator.data or {}, usdkrw=_usdkrw(self.coordinator))
        return totals.get(self._key)


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
