"""Binary sensors — one per watched corp_code, ON when a new disclosure arrives."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TZ_KST
from .coordinator import DisclosureCoordinator
from .device import disclosure_device

# A disclosure is considered "new" if it landed within this window.
_FRESH_WINDOW = timedelta(hours=24)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]
    disclosure: DisclosureCoordinator | None = store.get("disclosure")
    if disclosure is None:
        return

    corp_codes = entry.data.get("disclosure_corp_codes", []) or []
    entities = [DisclosureBinarySensor(disclosure, code) for code in corp_codes]
    if entities:
        async_add_entities(entities)


class DisclosureBinarySensor(CoordinatorEntity[DisclosureCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:file-document-alert"

    def __init__(self, coordinator: DisclosureCoordinator, corp_code: str) -> None:
        super().__init__(coordinator)
        self._corp_code = corp_code
        self._attr_unique_id = f"{DOMAIN}_disclosure_{corp_code}"
        self._attr_name = "신규 공시"
        self._attr_device_info = disclosure_device(corp_code)

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
