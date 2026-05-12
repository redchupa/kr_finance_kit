"""Shared DeviceInfo factories — every device carries the donation meta."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import (
    DOMAIN,
    DONATION_MANUFACTURER,
    DONATION_MODEL,
    DONATION_SW_VERSION,
)


def _device(suffix: str, label: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, suffix)},
        name=label,
        manufacturer=DONATION_MANUFACTURER,
        model=DONATION_MODEL,
        sw_version=DONATION_SW_VERSION,
        entry_type=DeviceEntryType.SERVICE,
    )


def market_device() -> DeviceInfo:
    return _device("market", "한국 시장 지표")


def ticker_device(market: str, ticker: str) -> DeviceInfo:
    return _device(f"ticker_{market.lower()}_{ticker}", f"{market} {ticker}")


def disclosure_device(corp_code: str) -> DeviceInfo:
    return _device(f"disclosure_{corp_code}", f"공시 {corp_code}")


def portfolio_device() -> DeviceInfo:
    return _device("portfolio", "보유 종목")
