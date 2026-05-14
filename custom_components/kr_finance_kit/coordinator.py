"""DataUpdateCoordinators for KR Finance Kit.

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

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import opendart, yfinance_wrap
from .const import (
    CONF_INCLUDE_DETAILED_ATTRS,
    CONF_INCLUDE_FX,
    CONF_INCLUDE_INDICES,
    CONF_INCLUDE_US_INDICES,
    CONF_KR_TICKERS,
    CONF_OTHER_TICKERS,
    CONF_POSITIONS,
    CONF_US_TICKERS,
    FX_USDKRW,
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
        self._failures = 0

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
    def positions(self) -> list[dict[str, Any]]:
        return list(self._config.get(CONF_POSITIONS, []))

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
        include_fx = bool(cfg.get(CONF_INCLUDE_FX, True))
        kr_open = is_kr_market_open()
        us_open = is_us_market_open()

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
            indices_task = (
                yfinance_wrap.fetch_indices(wanted_indices) if wanted_indices else None
            )
            fx_task = yfinance_wrap.fetch_fx() if include_fx else None

            indices = await indices_task if indices_task else {}
            fx = await fx_task if fx_task else {}

            prev = self.data or {}
            kr_quotes = await yfinance_wrap.fetch_quotes(self.kr_tickers, MARKET_KR) \
                if (kr_open or not prev.get("kr_quotes")) \
                else prev.get("kr_quotes", {})
            us_quotes = await yfinance_wrap.fetch_quotes(self.us_tickers, MARKET_US) \
                if (us_open or not prev.get("us_quotes")) \
                else prev.get("us_quotes", {})
            # `other_tickers` covers crypto, FX, futures — assets that
            # trade 24/7 or 24/5, so we ignore market_hours and always
            # fetch. Empty list is a free no-op.
            other_quotes = await yfinance_wrap.fetch_quotes(
                self.other_tickers, MARKET_OTHER
            ) if self.other_tickers else {}

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
        return {
            "indices": indices,
            "fx": fx,
            "kr_quotes": kr_quotes,
            "us_quotes": us_quotes,
            "other_quotes": other_quotes,
            "info": info,
            "positions": self.positions,
            "kr_market_open": kr_open,
            "us_market_open": us_open,
        }


class DisclosureCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """OpenDart disclosure polling for a watch-list of corp codes."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        corp_codes: list[str],
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            name="kr_finance_kit_disclosure",
            update_interval=timedelta(seconds=SCAN_INTERVAL_DISCLOSURE),
        )
        self._api_key = api_key
        self._corp_codes = list(corp_codes)
        self._failures = 0

    def update_corp_codes(self, codes: list[str]) -> None:
        self._corp_codes = list(codes)

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await opendart.fetch_recent_disclosures(
                self.hass, self._api_key, self._corp_codes
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
