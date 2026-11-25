"""Binary sensors — disclosure notifications + portfolio P/L alert."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DISCLOSURE_CORP_CODES,
    CONF_DISCLOSURE_CORP_NAMES,
    CONF_KR_TICKER_NAMES,
    CONF_PORTFOLIO_PL_ALERT_PCT,
    CONF_US_TICKER_LABELS,
    DOMAIN,
    ENTITY_ID_PREFIX,
    MARKET_KR,
    TZ_KST,
)
from .coordinator import DisclosureCoordinator, MarketCoordinator
from .device import disclosure_device, portfolio_device, ticker_device
from .portfolio import compute_totals

# A disclosure is considered "new" if it landed within this window.
_FRESH_WINDOW = timedelta(hours=24)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]
    config = {**entry.data, **(entry.options or {})}
    entities: list[BinarySensorEntity] = []

    disclosure: DisclosureCoordinator | None = store.get("disclosure")
    if disclosure is not None:
        # Merged config (options over data): corp codes recomputed by the
        # options flow or the sidebar panel live in entry.options. Reading
        # entry.data alone meant KR tickers added after install never got
        # a disclosure binary_sensor.
        corp_codes = config.get(CONF_DISCLOSURE_CORP_CODES, []) or []
        # corp_name lookup feeds the binary_sensor device label so the
        # HA UI shows "삼성전자 신규 공시" instead of "공시 00126380".
        # Read via the options-first projection so Options edits flow
        # through.
        corp_names: dict[str, str] = config.get(CONF_DISCLOSURE_CORP_NAMES, {}) or {}
        entities.extend(
            DisclosureBinarySensor(disclosure, code, label=corp_names.get(code))
            for code in corp_codes
        )

    # Portfolio P/L threshold alert. Only registered when the user has
    # opted in (threshold > 0) AND has at least one position recorded
    # via the add_position service. compute_totals returns None when
    # there's nothing to aggregate, so the sensor itself handles
    # transient empty states by reporting unavailable / off.
    threshold = float(config.get(CONF_PORTFOLIO_PL_ALERT_PCT, 0) or 0)
    market: MarketCoordinator = store["market"]
    if threshold > 0 and market.positions:
        entities.append(PortfolioPLAlertBinarySensor(market, threshold))

    kr_names: dict[str, str] = config.get(CONF_KR_TICKER_NAMES, {}) or {}
    us_labels: dict[str, str] = config.get(CONF_US_TICKER_LABELS, {}) or {}
    for pos in market.positions:
        if pos.get("alert_high") is not None or pos.get("alert_low") is not None:
            pos_market = pos.get("market", MARKET_KR)
            pos_ticker = pos.get("ticker", "")
            if not pos_ticker:
                continue
            label = (kr_names if pos_market == MARKET_KR else us_labels).get(pos_ticker)
            entities.append(
                PositionPriceAlertBinarySensor(
                    market,
                    pos_market,
                    pos_ticker,
                    alert_high=pos.get("alert_high"),
                    alert_low=pos.get("alert_low"),
                    avg_price=pos.get("avg_price"),
                    label=label,
                )
            )

    if entities:
        async_add_entities(entities)


class DisclosureBinarySensor(CoordinatorEntity[DisclosureCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:file-document-alert"

    def __init__(
        self,
        coordinator: DisclosureCoordinator,
        corp_code: str,
        label: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._corp_code = corp_code
        self._attr_unique_id = f"{DOMAIN}_disclosure_{corp_code}"
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_disclosure_{corp_code}"
        # Translation key — friendly name comes from translations/<lang>.json.
        self._attr_translation_key = "new_disclosure"
        self._attr_device_info = disclosure_device(corp_code, label)

    def _latest(self) -> dict[str, Any] | None:
        for item in self.coordinator.data or []:
            if item.get("corp_code") == self._corp_code:
                return item
        return None

    @property
    def is_on(self) -> bool:
        latest = self._latest()
        if not latest:
            return False
        ts = latest.get("rcept_dt_parsed")
        if not isinstance(ts, datetime):
            return False
        return datetime.now(TZ_KST) - ts < _FRESH_WINDOW

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        latest = self._latest() or {}
        return {
            "report_nm": latest.get("report_nm"),
            "rcept_dt": latest.get("rcept_dt"),
            "rcept_no": latest.get("rcept_no"),
            "url": latest.get("url"),
        }


class PortfolioPLAlertBinarySensor(CoordinatorEntity[MarketCoordinator], BinarySensorEntity):
    """Goes ON when the KRW-converted portfolio P/L crosses ±threshold%.

    Threshold is read from CONF_PORTFOLIO_PL_ALERT_PCT in the entry
    options (positive number of percentage points, e.g. 5 → ±5%). The
    sensor is registered only when threshold > 0 and the user has
    actually added positions via the add_position service.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:trending-up"
    _attr_translation_key = "pl_alert"

    def __init__(self, coordinator: MarketCoordinator, threshold_pct: float) -> None:
        super().__init__(coordinator)
        self._threshold = threshold_pct
        self._attr_unique_id = f"{DOMAIN}_portfolio_pl_alert"
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_portfolio_pl_alert"
        self._attr_device_info = portfolio_device()

    def _pct(self) -> float | None:
        """KRW-converted portfolio P/L percent against cost basis.

        Returns None when there's no portfolio data or cost basis is
        zero (so the sensor stays unavailable instead of dividing).
        """
        from .const import FX_USDKRW as _FX
        data = self.coordinator.data or {}
        rate = (data.get("fx", {}) or {}).get(_FX, {}).get("price")
        totals = compute_totals(data, usdkrw=rate)
        krw_total = totals.get("krw_total")
        krw_pl = totals.get("krw_pl")
        if krw_total is None or krw_pl is None:
            return None
        cost_basis = krw_total - krw_pl
        if cost_basis <= 0:
            return None
        return round(krw_pl / cost_basis * 100, 2)

    @property
    def is_on(self) -> bool:
        pct = self._pct()
        if pct is None:
            return False
        return abs(pct) >= self._threshold

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pct = self._pct()
        return {
            "current_pl_pct": pct,
            "threshold_pct": self._threshold,
        }


def evaluate_price_alert(
    price: float | None,
    alert_high: float | None,
    alert_low: float | None,
) -> str | None:
    """Return 'high', 'low', or None depending on threshold crossing."""
    if price is None:
        return None
    if alert_high is not None and price >= alert_high:
        return "high"
    if alert_low is not None and price <= alert_low:
        return "low"
    return None


class PositionPriceAlertBinarySensor(
    CoordinatorEntity[MarketCoordinator], BinarySensorEntity
):
    """Per-holding target / stop-loss price alert binary_sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bell-ring-outline"
    _attr_translation_key = "price_alert"

    def __init__(
        self,
        coordinator: MarketCoordinator,
        market: str,
        ticker: str,
        *,
        alert_high: float | None = None,
        alert_low: float | None = None,
        avg_price: float | None = None,
        label: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._market = market
        self._ticker = ticker
        self._alert_high = alert_high
        self._alert_low = alert_low
        self._avg_price = avg_price
        slug = ticker.lower().replace(".", "_").replace("-", "_")
        self._attr_unique_id = f"{DOMAIN}_price_alert_{market.lower()}_{ticker}"
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_price_alert_{market.lower()}_{slug}"
        self._attr_device_info = ticker_device(market, ticker, label)

    def _current_price(self) -> float | None:
        data = self.coordinator.data or {}
        src = "kr_quotes" if self._market == MARKET_KR else "us_quotes"
        raw = (data.get(src, {}) or {}).get(self._ticker, {}).get("price")
        return float(raw) if isinstance(raw, (int, float)) else None

    @property
    def is_on(self) -> bool:
        return (
            evaluate_price_alert(
                self._current_price(), self._alert_high, self._alert_low
            )
            is not None
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        price = self._current_price()
        triggered = evaluate_price_alert(price, self._alert_high, self._alert_low)
        dist_high = (
            round((self._alert_high / price - 1) * 100, 2)
            if price and price > 0 and self._alert_high is not None
            else None
        )
        dist_low = (
            round((self._alert_low / price - 1) * 100, 2)
            if price and price > 0 and self._alert_low is not None
            else None
        )
        return {
            "ticker": self._ticker,
            "market": self._market,
            "current_price": price,
            "avg_price": self._avg_price,
            "alert_high": self._alert_high,
            "alert_low": self._alert_low,
            "triggered": triggered,
            "distance_high_pct": dist_high,
            "distance_low_pct": dist_low,
        }
