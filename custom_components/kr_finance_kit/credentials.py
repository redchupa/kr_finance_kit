"""Encrypt OpenDart credentials before they enter HA config-entry storage."""
from __future__ import annotations

import asyncio

from cryptography.fernet import Fernet
from homeassistant.helpers.storage import Store

from .const import CONF_OPENDART_API_KEY, DOMAIN

_PREFIX = "fernet:v1:"
_STORE_KEY = f"{DOMAIN}.credential_key"


async def _cipher(hass, *, create):
    state = hass.data.setdefault(_STORE_KEY, {})
    async with state.setdefault("lock", asyncio.Lock()):
        if "cipher" not in state:
            store = Store(hass, 1, _STORE_KEY, private=True, atomic_writes=True)
            doc = await store.async_load()
            if doc is None:
                if not create:
                    raise ValueError("Restore the Finance Kit credential key from backup")
                doc = {"key": Fernet.generate_key().decode("ascii")}
                await store.async_save(doc)
            state["cipher"] = Fernet(doc["key"].encode("ascii"))
        return state["cipher"]


async def seal(hass, value):
    if not value:
        return ""
    cipher = await _cipher(hass, create=True)
    return _PREFIX + cipher.encrypt(value.encode()).decode("ascii")


async def unseal(hass, value):
    if not value or not value.startswith(_PREFIX):
        return value or ""
    cipher = await _cipher(hass, create=False)
    return cipher.decrypt(value[len(_PREFIX):].encode("ascii")).decode()


async def migrate_key(hass, entry):
    changes = {}
    for field in ("data", "options"):
        values = getattr(entry, field)
        value = values.get(CONF_OPENDART_API_KEY)
        if value and not value.startswith(_PREFIX):
            changes[field] = {**values, CONF_OPENDART_API_KEY: await seal(hass, value)}
    if changes:
        hass.config_entries.async_update_entry(entry, **changes)
