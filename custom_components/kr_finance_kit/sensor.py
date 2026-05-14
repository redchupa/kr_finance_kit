"""Sensor platform — indices, FX, ticker quotes, portfolio P/L."""
from __future__ import annotations

import math
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_INCLUDE_FX,
    CONF_INCLUDE_GLOBAL_INDICES,
    CONF_INCLUDE_INDICES,
    CONF_INCLUDE_US_INDICES,
    CONF_KR_TICKER_NAMES,
    CONF_TARGET_CURRENCY_KRW,
    DEFAULT_SHORT_WINDOW_MINUTES,
    DOMAIN,
    ENTITY_ID_PREFIX,
    FX_USDKRW,
    GLOBAL_INDICES,
    KR_INDICES,
    MARKET_KR,
    MARKET_OTHER,
    MARKET_US,
    US_INDICES,
)
from .coordinator import MarketCoordinator
from .device import global_market_device, market_device, portfolio_device, ticker_device, us_market_device
from .portfolio import compute_totals


def _entry_value(entry: ConfigEntry, key: str, default: Any) -> Any:
    """Look up a config value, options layered on top of data.

    Merge (not ``entry.options or entry.data``) so a partial options
    dict — e.g. only the toggles the user has saved, with tickers and
    labels still living in data — doesn't blackhole the entry.data
    side. Matches coordinator._config and config_flow._current; under
    the OR form a single key in options would shadow everything in
    data and the sensor platform would skip half the entities.
    """
    merged = {**(entry.data or {}), **(entry.options or {})}
    return merged.get(key, default)


def _slug(value: str) -> str:
    """Sanitize a ticker/index into an entity_id-safe slug.

    HA's entity_id grammar allows only ``[a-z0-9_]``. Tickers from
    Yahoo carry hyphens, equals signs, and occasional whitespace
    (``BTC-USD``, ``EUR=X``, ``GC=F``, ``Hang Seng``). We pre-collapse
    every non-alphanumeric run — including spaces — to a single
    underscore so every QuoteSensor lands on a predictable slug
    (``sensor.fi_other_btc_usd``, ``sensor.fi_other_eur_x`` etc.).
    """
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")


def _short_window_attrs(coordinator: "MarketCoordinator", ticker: str) -> dict[str, Any]:
    """Per-ticker rolling-window % change attributes.

    Emits one ``change_pct_<N>min`` attribute per minute in
    ``DEFAULT_SHORT_WINDOW_MINUTES`` (1, 5, 15, 30, 60, 90, 120, 180).
    The list is hard-coded — the user-facing option that used to feed
    this in v0.1.52 was removed because blueprint authors set the
    target minute per-automation; a per-integration CSV was just an
    extra UI step. Values whose ring buffer hasn't filled yet are
    dropped so the sensor doesn't surface misleading leading zeros
    during the HA-restart warm-up window.
    """
    out: dict[str, Any] = {}
    for minutes in DEFAULT_SHORT_WINDOW_MINUTES:
        pct = coordinator.price_change_pct(ticker, minutes)
        if pct is not None:
            out[f"change_pct_{minutes}min"] = pct
    return out


def _krw_attr(coordinator: "MarketCoordinator", market: str, price: float | None) -> dict[str, Any]:
    """Add a ``price_krw`` attribute for USD-denominated assets when the
    target-currency option is enabled.

    Applies to US and OTHER tickers — those are USD on yfinance for the
    common cases (AAPL, BTC-USD, ETH-USD, GC=F). KR tickers are already
    in KRW and are skipped. Non-USD OTHER tickers (e.g. EUR=X) would
    produce a misleading number; users with those should leave the
    option off or interpret the attribute accordingly.
    """
    if not coordinator._config.get(CONF_TARGET_CURRENCY_KRW, False):
        return {}
    if market not in (MARKET_US, MARKET_OTHER):
        return {}
    if price is None:
        return {}
    rate = _usdkrw(coordinator)
    if rate is None:
        return {}
    return {"price_krw": round(price * rate, 2)}


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
    if _entry_value(entry, CONF_INCLUDE_GLOBAL_INDICES, False):
        entities += [IndexSensor(market, idx, "GLOBAL") for idx in GLOBAL_INDICES]
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
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_{_slug(index)}"
        self._attr_name = index
        if market == MARKET_US:
            self._attr_device_info = us_market_device()
        elif market == "GLOBAL":
            self._attr_device_info = global_market_device()
        else:
            self._attr_device_info = market_device()

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
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_{_slug(pair)}"
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
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_{market.lower()}_{_slug(ticker)}"
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
        base.update(_krw_attr(self.coordinator, self._market, self.native_value))
        base.update(_short_window_attrs(self.coordinator, self._ticker))
        return base


def _usdkrw(coord: MarketCoordinator) -> float | None:
    rate = (coord.data or {}).get("fx", {}).get(FX_USDKRW, {}).get("price")
    return _finite(rate)


class _PortfolioBase(_MarketBase):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MarketCoordinator, key: str, unit: str, icon: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{DOMAIN}_portfolio_{key}"
        self._attr_suggested_object_id = f"{ENTITY_ID_PREFIX}_portfolio_{key.lower()}"
        # Friendly name resolved via translations/<lang>.json — keeps
        # the entity readable in Korean for ko users AND English for
        # everyone else, without changing the entity_id slug.
        self._attr_translation_key = f"portfolio_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_info = portfolio_device()

    @property
    def native_value(self) -> float | None:
        totals = compute_totals(self.coordinator.data or {}, usdkrw=_usdkrw(self.coordinator))
        return _finite(totals.get(self._key))


class PortfolioKRValueSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "kr_value", "KRW", "mdi:briefcase-variant")


class PortfolioKRPLSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "kr_pl", "KRW", "mdi:trending-up")


class PortfolioUSValueSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "us_value", "USD", "mdi:briefcase-variant")


class PortfolioUSPLSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "us_pl", "USD", "mdi:trending-up")


class PortfolioKRWTotalSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "krw_total", "KRW", "mdi:briefcase-check")


def _positions_breakdown(coord: "MarketCoordinator") -> list[dict[str, Any]]:
    """Per-position enrichment: ticker → qty, avg, current, value, P/L, P/L%.

    Read from coordinator.data (positions + quotes already populated).
    Skips positions whose live quote isn't available yet (sensor is
    still warming up). Returns a list ordered by market (KR first)
    then ticker.
    """
    data = coord.data or {}
    positions = data.get("positions", []) or []
    kr_quotes = data.get("kr_quotes", {}) or {}
    us_quotes = data.get("us_quotes", {}) or {}
    out: list[dict[str, Any]] = []
    for p in positions:
        ticker = p.get("ticker")
        market = p.get("market")
        qty = float(p.get("quantity", 0) or 0)
        avg = float(p.get("avg_price", 0) or 0)
        quotes = kr_quotes if market == MARKET_KR else us_quotes
        current = (quotes.get(ticker) or {}).get("price")
        if current is None or qty <= 0:
            continue
        cost = avg * qty
        value = float(current) * qty
        pl = value - cost
        pl_pct = (pl / cost * 100) if cost > 0 else None
        out.append({
            "ticker": ticker,
            "market": market,
            "quantity": qty,
            "avg_price": avg,
            "current_price": float(current),
            "value": round(value, 2),
            "cost": round(cost, 2),
            "pl": round(pl, 2),
            "pl_pct": round(pl_pct, 2) if pl_pct is not None else None,
        })
    out.sort(key=lambda x: (x["market"] != MARKET_KR, x["ticker"]))
    return out


class PortfolioKRWPLSensor(_PortfolioBase):
    def __init__(self, coordinator: MarketCoordinator) -> None:
        super().__init__(coordinator, "krw_pl", "KRW", "mdi:cash-multiple")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Surfaces per-position breakdown so dashboards / Markdown
        # cards can render a holdings table without needing a new
        # entity per ticker. Attached to the KRW P/L sensor because
        # that's the single "everything rolled up" handle most
        # dashboards already template against.
        return {"positions": _positions_breakdown(self.coordinator)}
