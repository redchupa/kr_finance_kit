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
    FX_USDKRW,
    KR_INDICES,
    MARKET_KR,
    MARKET_US,
    US_INDICES,
)
from .coordinator import MarketCoordinator
from .device import market_device, portfolio_device, ticker_device, us_market_device
from .portfolio import compute_totals


def _entry_value(entry: ConfigEntry, key: str, default: Any) -> Any:
    return (entry.options or entry.data).get(key, default)


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
    for ticker in market.kr_tickers:
        entities.append(QuoteSensor(market, MARKET_KR, ticker, label=kr_names.get(ticker)))
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

    def __init__(self, coordinator: MarketCoordinator, index: str, market: str = MARKET_KR) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_unique_id = f"{DOMAIN}_index_{index.lower()}"
        # Pin entity_id to an English slug regardless of the (Korean)
        # device name — has_entity_name=True would otherwise produce
        # `sensor.hangug_sijang_jipyo_kospi` style slugs that don't match
        # what the README and the example automations document.
        self._attr_suggested_object_id = f"{DOMAIN}_{index.lower()}"
        self._attr_name = index
        self._attr_device_info = us_market_device() if market == MARKET_US else market_device()

    @property
    def native_value(self) -> float | None:
        data = (self.coordinator.data or {}).get("indices", {})
        return _finite(data.get(self._index, {}).get("price"))

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
        self._attr_suggested_object_id = f"{DOMAIN}_{pair.lower()}"
        self._attr_name = pair
        self._attr_device_info = market_device()

    @property
    def native_value(self) -> float | None:
        v = (self.coordinator.data or {}).get("fx", {}).get(self._pair, {}).get("price")
        return _finite(v)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = (self.coordinator.data or {}).get("fx", {}).get(self._pair, {})
        return {k: v for k, v in data.items() if k != "price"}


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
        self._attr_suggested_object_id = f"{DOMAIN}_{market.lower()}_{ticker.lower()}"
        # Device label is the single source of truth for the friendly
        # name: "삼성전자" when resolved, "KR 005930" otherwise. Both the
        # unique_id and entity_id stay code-based so automations don't
        # break when names are added/removed later.
        self._attr_device_info = ticker_device(market, ticker, label)
        self._attr_native_unit_of_measurement = "KRW" if market == MARKET_KR else "USD"

    @property
    def _quote(self) -> dict[str, Any]:
        key = "kr_quotes" if self._market == MARKET_KR else "us_quotes"
        return (self.coordinator.data or {}).get(key, {}).get(self._ticker, {}) or {}

    @property
    def native_value(self) -> float | None:
        return _finite(self._quote.get("price"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {k: v for k, v in self._quote.items() if k != "price"}


def _usdkrw(coord: MarketCoordinator) -> float | None:
    rate = (coord.data or {}).get("fx", {}).get(FX_USDKRW, {}).get("price")
    return _finite(rate)


class _PortfolioBase(_MarketBase):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MarketCoordinator, key: str, name: str, unit: str, icon: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{DOMAIN}_portfolio_{key}"
        self._attr_suggested_object_id = f"{DOMAIN}_portfolio_{key.lower()}"
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
