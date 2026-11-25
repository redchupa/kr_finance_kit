"""DataUpdateCoordinators for Finance Kit.

Two coordinators run independently:

- ``MarketCoordinator`` — KOSPI/KOSDAQ, USD/KRW, and per-ticker quotes for
  KR and US markets, all sourced from yfinance. The polling interval is
  adjusted based on market hours: tight (``SCAN_INTERVAL_MARKET``) when
  at least one market is open, relaxed (``SCAN_INTERVAL_MARKET_IDLE``)
  when both are closed. This cuts yfinance traffic by ~80% overnight
  without sacrificing freshness during the trading day.
- ``DisclosureCoordinator`` — OpenDart ``list.json`` polling for a
  watch-list of corp_codes.

Both tolerate transient errors: a short streak of failures keeps stale
data instead of marking the integration unavailable.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import opendart, yfinance_wrap
from .const import (
    CONF_INCLUDE_DETAILED_ATTRS,
    CONF_INCLUDE_FX,
    CONF_INCLUDE_GLOBAL_INDICES,
    CONF_INCLUDE_INDICES,
    CONF_INCLUDE_US_INDICES,
    CONF_KR_TICKER_NAMES,
    CONF_KR_TICKERS,
    CONF_OTHER_TICKER_LABELS,
    CONF_OTHER_TICKERS,
    CONF_POSITIONS,
    CONF_US_TICKER_LABELS,
    CONF_US_TICKERS,
    EVENT_KR_MARKET_CLOSED,
    EVENT_PRICE_ALERT,
    EVENT_US_MARKET_CLOSED,
    FX_USDKRW,
    GLOBAL_INDICES,
    KR_INDICES,
    LOGGER,
    MARKET_KR,
    MARKET_OTHER,
    MARKET_US,
    SCAN_INTERVAL_DISCLOSURE,
    SCAN_INTERVAL_MARKET,
    SCAN_INTERVAL_MARKET_IDLE,
    US_INDICES,
)
from .api.yfinance_wrap import INDEX_TICKERS, FX_TICKERS, normalize_kr_ticker
from .market_hours import any_market_open, is_kr_market_open, is_us_market_open


class MarketCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Indices, FX, and per-ticker quotes via yfinance."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            LOGGER,
            name="kr_finance_kit_market",
            update_interval=timedelta(seconds=SCAN_INTERVAL_MARKET),
        )
        self._entry = entry
        self.startup_quotes = {}
        self._failures = 0
        # Ring buffer per ticker for short-window change_pct attributes.
        # Capacity 300 entries × ~60s polling = ~5 hours, large enough to
        # cover any user-defined window minute (CONF_SHORT_WINDOW_MINUTES)
        # up to 300 with headroom for jitter and the idle-mode interval
        # dial-down. Entries: (utc_timestamp, price). Memory only — lost on
        # HA restart, so attributes return None until the buffer refills
        # to the requested window length.
        self._price_history: dict[str, deque[tuple[datetime, float]]] = {}
        self._history_maxlen = 300
        # Edge-trigger state for per-position price alerts: (market, ticker) -> "high"|"low"|None
        self._alert_states: dict[tuple[str, str], str | None] = {}

    @property
    def _config(self) -> dict[str, Any]:
        return {**self._entry.data, **(self._entry.options or {})}

    @property
    def kr_tickers(self) -> list[str]:
        return list(self._config.get(CONF_KR_TICKERS, []))

    @property
    def us_tickers(self) -> list[str]:
        return list(self._config.get(CONF_US_TICKERS, []))

    @property
    def other_tickers(self) -> list[str]:
        return list(self._config.get(CONF_OTHER_TICKERS, []))

    @property
    def other_ticker_labels(self) -> dict[str, str]:
        return dict(self._config.get(CONF_OTHER_TICKER_LABELS, {}) or {})

    @property
    def us_ticker_labels(self) -> dict[str, str]:
        return dict(self._config.get(CONF_US_TICKER_LABELS, {}) or {})

    @property
    def positions(self) -> list[dict[str, Any]]:
        return list(self._config.get(CONF_POSITIONS, []))

    def _push_price_history(self, data: dict[str, Any]) -> None:
        """Append current prices to the per-ticker ring buffer."""
        now = datetime.now(timezone.utc)
        for src in ("kr_quotes", "us_quotes", "other_quotes"):
            for ticker, quote in (data.get(src) or {}).items():
                price = quote.get("price") if isinstance(quote, dict) else None
                if not isinstance(price, (int, float)):
                    continue
                buf = self._price_history.setdefault(
                    ticker, deque(maxlen=self._history_maxlen)
                )
                buf.append((now, float(price)))

    def price_change_pct(self, ticker: str, minutes: int) -> float | None:
        """Compute % change vs. the oldest sample within the last ``minutes``.

        Returns None when the buffer hasn't accumulated enough data
        (HA fresh restart, ticker just added), the oldest in-window
        sample is zero, or the window is shorter than our polling
        interval. Picks the sample closest to ``now - minutes`` from
        the inside so we never use stale data outside the requested
        window.
        """
        buf = self._price_history.get(ticker)
        if not buf:
            return None
        latest_ts, latest_price = buf[-1]
        if latest_price <= 0:
            return None
        cutoff = latest_ts - timedelta(minutes=minutes)
        baseline = None
        for ts, price in buf:
            if ts >= cutoff and price > 0:
                baseline = price
                break
        if baseline is None or baseline <= 0:
            return None
        return round((latest_price / baseline - 1) * 100, 2)

    def _retune_interval(self) -> None:
        target_secs = SCAN_INTERVAL_MARKET if any_market_open() else SCAN_INTERVAL_MARKET_IDLE
        target = timedelta(seconds=target_secs)
        if self.update_interval != target:
            LOGGER.debug(
                "MarketCoordinator interval %s → %s (any market open: %s)",
                self.update_interval,
                target,
                any_market_open(),
            )
            self.update_interval = target

    async def _async_update_data(self) -> dict[str, Any]:
        cfg = self._config
        include_kr_indices = bool(cfg.get(CONF_INCLUDE_INDICES, True))
        include_us_indices = bool(cfg.get(CONF_INCLUDE_US_INDICES, True))
        include_global_indices = bool(cfg.get(CONF_INCLUDE_GLOBAL_INDICES, False))
        include_fx = bool(cfg.get(CONF_INCLUDE_FX, True))
        kr_open = is_kr_market_open()
        us_open = is_us_market_open()

        # Fire market-close events on the open→closed transition. Reading
        # the previous tick's market state from self.data avoids spamming
        # the bus every poll; only the edge fires.
        prev_for_events = self.data or {}
        if prev_for_events.get("kr_market_open") and not kr_open:
            self.hass.bus.async_fire(EVENT_KR_MARKET_CLOSED, {})
        if prev_for_events.get("us_market_open") and not us_open:
            self.hass.bus.async_fire(EVENT_US_MARKET_CLOSED, {})

        try:
            # Skip per-market quote fetches when that market has been
            # closed long enough that yfinance would return the same
            # prior-close repeatedly. Keep stale data so sensors stay
            # populated with last-known values.
            wanted_indices: list[str] = []
            if include_kr_indices:
                wanted_indices.extend(KR_INDICES)
            if include_us_indices:
                wanted_indices.extend(US_INDICES)
            if include_global_indices:
                wanted_indices.extend(GLOBAL_INDICES)
            prev = self.data or {}

            async def quotes(group, symbols, fetch):
                if prev:
                    return await fetch(symbols) if symbols else {}
                # Publish first-run progress to the read-only sidebar snapshot.
                # Keep coordinator listeners and alerts on complete refreshes.
                rows = {}
                for symbol in symbols:
                    batch = await fetch([symbol])
                    rows.update(batch)
                    if any(row.get("price") is not None for row in batch.values()):
                        self.startup_quotes.setdefault(group, {}).update(batch)
                        self.startup_quotes.update(
                            kr_market_open=kr_open, us_market_open=us_open,
                            fetched_at=datetime.now(timezone.utc).isoformat(),
                        )
                return rows

            indices = await quotes("indices", wanted_indices, yfinance_wrap.fetch_indices)
            fx = await yfinance_wrap.fetch_fx() if include_fx else {}
            if not prev and any(row.get("price") is not None for row in fx.values()):
                self.startup_quotes.update(fx=fx, fetched_at=datetime.now(timezone.utc).isoformat())
            kr_quotes = await quotes("kr_quotes", self.kr_tickers,
                lambda tickers: yfinance_wrap.fetch_quotes(tickers, MARKET_KR)
            ) if kr_open or not prev.get("kr_quotes") else prev["kr_quotes"]
            us_quotes = await quotes("us_quotes", self.us_tickers,
                lambda tickers: yfinance_wrap.fetch_quotes(tickers, MARKET_US)
            ) if us_open or not prev.get("us_quotes") else prev["us_quotes"]
            other_quotes = await quotes("other_quotes", self.other_tickers,
                lambda tickers: yfinance_wrap.fetch_quotes(tickers, MARKET_OTHER))

            # Detailed yfinance .info attributes — toggled separately
            # because each symbol adds one extra HTTP round-trip. We map
            # each user-facing identifier (index name, FX pair, ticker)
            # to the yfinance symbol so .info comes back keyed by what
            # the sensor will look up.
            info: dict[str, dict[str, Any]] = {}
            if cfg.get(CONF_INCLUDE_DETAILED_ATTRS, False):
                lookup: dict[str, str] = {}  # user-key -> yfinance symbol
                for idx in wanted_indices:
                    if idx in INDEX_TICKERS:
                        lookup[idx] = INDEX_TICKERS[idx]
                if include_fx:
                    lookup[FX_USDKRW] = FX_TICKERS.get(FX_USDKRW, "KRW=X")
                for t in self.kr_tickers:
                    lookup[t] = normalize_kr_ticker(t)
                for t in self.us_tickers:
                    lookup[t] = t
                for t in self.other_tickers:
                    lookup[t] = t
                if lookup:
                    raw = await yfinance_wrap.fetch_info(list(lookup.values()))
                    info = {key: raw.get(sym, {}) for key, sym in lookup.items()}
        except Exception as err:  # noqa: BLE001
            self._failures += 1
            if self._failures <= 5 and self.data is not None:
                LOGGER.warning(
                    "MarketCoordinator transient error (%d/5): %s",
                    self._failures,
                    err,
                )
                self._retune_interval()
                return self.data
            raise UpdateFailed(f"Market data fetch failed: {err}") from err

        self._failures = 0
        self._retune_interval()
        result = {
            "indices": indices,
            "fx": fx,
            "kr_quotes": kr_quotes,
            "us_quotes": us_quotes,
            "other_quotes": other_quotes,
            "info": info,
            "positions": self.positions,
            "kr_market_open": kr_open,
            "us_market_open": us_open,
            # Read by the sidebar panel ("updated 12s ago").
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        self._push_price_history(result)
        self._check_position_price_alerts(result, cfg)
        self.startup_quotes = {}
        return result

    def _check_position_price_alerts(
        self, data: dict[str, Any], cfg: dict[str, Any]
    ) -> None:
        """Fire EVENT_PRICE_ALERT once when a holding crosses alert_high/alert_low."""
        kr_names = cfg.get(CONF_KR_TICKER_NAMES, {}) or {}
        us_labels = cfg.get(CONF_US_TICKER_LABELS, {}) or {}
        active_keys: set[tuple[str, str]] = set()
        for pos in data.get("positions", []) or []:
            ticker = pos.get("ticker")
            market = pos.get("market", MARKET_KR)
            alert_high = pos.get("alert_high")
            alert_low = pos.get("alert_low")
            if not ticker or (alert_high is None and alert_low is None):
                continue
            key = (market, ticker)
            active_keys.add(key)
            src = "kr_quotes" if market == MARKET_KR else "us_quotes"
            price = (data.get(src, {}) or {}).get(ticker, {}).get("price")
            if not isinstance(price, (int, float)):
                continue
            state: str | None = None
            target: float | None = None
            if alert_high is not None and price >= alert_high:
                state, target = "high", float(alert_high)
            elif alert_low is not None and price <= alert_low:
                state, target = "low", float(alert_low)
            prev_state = self._alert_states.get(key)
            self._alert_states[key] = state
            if state is not None and state != prev_state:
                avg = pos.get("avg_price")
                pl_pct = (
                    round((price / avg - 1) * 100, 2)
                    if isinstance(avg, (int, float)) and avg > 0
                    else None
                )
                name = (
                    (kr_names if market == MARKET_KR else us_labels).get(ticker)
                    or ticker
                )
                self.hass.bus.async_fire(
                    EVENT_PRICE_ALERT,
                    {
                        "ticker": ticker,
                        "name": name,
                        "market": market,
                        "direction": state,
                        "current_price": float(price),
                        "target_price": target,
                        "avg_price": avg,
                        "pl_pct": pl_pct,
                    },
                )
        for stale_key in [k for k in self._alert_states if k not in active_keys]:
            self._alert_states.pop(stale_key, None)


class DisclosureCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """OpenDart disclosure polling for a watch-list of corp codes."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        corp_codes: list[str],
        categories: list[str] | None = None,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name="kr_finance_kit_disclosure",
            update_interval=timedelta(seconds=SCAN_INTERVAL_DISCLOSURE),
        )
        self._api_key = api_key
        self._corp_codes = list(corp_codes)
        self._categories = list(categories or [])
        self._failures = 0

    def update_corp_codes(self, codes: list[str]) -> None:
        self._corp_codes = list(codes)

    def update_categories(self, codes: list[str]) -> None:
        self._categories = list(codes or [])

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await opendart.fetch_recent_disclosures(
                self.hass, self._api_key, self._corp_codes, self._categories
            )
        except Exception as err:  # noqa: BLE001
            self._failures += 1
            if self._failures <= 3 and self.data is not None:
                LOGGER.warning(
                    "DisclosureCoordinator transient error (%d/3): %s",
                    self._failures,
                    err,
                )
                return self.data
            raise UpdateFailed(f"OpenDart fetch failed: {err}") from err
