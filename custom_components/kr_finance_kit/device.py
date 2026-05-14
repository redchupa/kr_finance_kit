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


# Device names are intentionally in English. HACS users come from many
# locales, and device-name i18n in HA registry is per-install (user can
# rename in the UI). Entity friendly names are translated via
# translations/<lang>.json + _attr_translation_key.
def market_device() -> DeviceInfo:
    return _device("market", "KR Indices")


def us_market_device() -> DeviceInfo:
    return _device("us_market", "US Indices")


def global_market_device() -> DeviceInfo:
    return _device("global_market", "Global Indices")


def ticker_device(market: str, ticker: str, label: str | None = None) -> DeviceInfo:
    # When we have a friendly label (e.g. "삼성전자" or "Apple"), surface it.
    # That label comes from the user's own input (kr_ticker_names /
    # us_ticker_labels) and OpenDart corp resolution — so it stays in
    # whatever language the user typed.
    device_label = label or f"{market} {ticker}"
    return _device(f"ticker_{market.lower()}_{ticker}", device_label)


def disclosure_device(corp_code: str, label: str | None = None) -> DeviceInfo:
    # When OpenDart resolved a corp_name for this corp_code, use it
    # ("삼성전자 New disclosure"); otherwise fall back to the corp_code.
    device_label = label or f"Disclosure {corp_code}"
    return _device(f"disclosure_{corp_code}", device_label)


def portfolio_device() -> DeviceInfo:
    return _device("portfolio", "Portfolio")
