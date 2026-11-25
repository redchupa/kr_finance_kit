"""entity_id migration: rename to fi_* once, never revert a user rename."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

import custom_components.kr_finance_kit as integ  # noqa: E402

D, P = "kr_finance_kit", "fi"


def plan(entities, handled=(), first_run=False):
    return integ._plan_entity_id_migrations(list(entities), set(handled), first_run, D, P)


def test_new_entity_with_name_slug_is_renamed_once():
    ents = [("sensor", "sensor.ethereum_krw", "kr_finance_kit_other_ETH-KRW")]
    renames, handled = plan(ents)
    assert renames == [("sensor.ethereum_krw", "sensor.fi_other_eth_krw")]
    assert handled == {"kr_finance_kit_other_ETH-KRW"}


def test_user_rename_is_not_reverted_once_handled():
    ents = [("sensor", "sensor.my_samsung", "kr_finance_kit_kr_005930")]
    renames, handled = plan(ents, handled={"kr_finance_kit_kr_005930"})
    assert renames == []
    assert handled == {"kr_finance_kit_kr_005930"}


def test_first_run_after_upgrade_records_without_renaming():
    ents = [
        ("sensor", "sensor.my_samsung", "kr_finance_kit_kr_005930"),
        ("sensor", "sensor.fi_kospi", "kr_finance_kit_index_kospi"),
    ]
    renames, handled = plan(ents, first_run=True)
    assert renames == []
    assert handled == {"kr_finance_kit_kr_005930", "kr_finance_kit_index_kospi"}


def test_already_correct_entity_is_just_recorded():
    renames, handled = plan([("binary_sensor", "binary_sensor.fi_disclosure_00126380",
                              "kr_finance_kit_disclosure_00126380")])
    assert renames == []
    assert handled == {"kr_finance_kit_disclosure_00126380"}


def test_handled_set_pruned_to_registry():
    renames, handled = plan([], handled={"kr_finance_kit_kr_000660"})
    assert renames == [] and handled == set()


def test_foreign_unique_ids_ignored():
    renames, handled = plan([("sensor", "sensor.x", "other_domain_x")])
    assert renames == [] and handled == set()


# ---------------------------------------------------------------- async wrapper

class FakeRegistry:
    def __init__(self, entities):
        self.entities = {e.entity_id: e for e in entities}
        self.updates = []

    def async_get(self, entity_id):
        return self.entities.get(entity_id)

    def async_update_entity(self, entity_id, new_entity_id):
        self.updates.append((entity_id, new_entity_id))
        ent = self.entities.pop(entity_id)
        ent.entity_id = new_entity_id
        self.entities[new_entity_id] = ent


def _ent(entity_id, unique_id):
    return SimpleNamespace(entity_id=entity_id, unique_id=unique_id, platform=D,
                           domain=entity_id.split(".")[0])


def _run(monkeypatch, registry, stored):
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers import storage

    saved = {}

    class FakeStore:
        def __init__(self, hass, version, key):
            pass

        async def async_load(self):
            return stored

        async def async_save(self, data):
            saved["data"] = data

    monkeypatch.setattr(storage, "Store", FakeStore)
    monkeypatch.setattr(er, "async_get", lambda hass: registry)
    asyncio.run(integ._migrate_legacy_entity_ids(SimpleNamespace()))
    return saved.get("data")


def test_wrapper_upgrade_keeps_user_rename(monkeypatch):
    reg = FakeRegistry([_ent("sensor.my_samsung", "kr_finance_kit_kr_005930")])
    saved = _run(monkeypatch, reg, stored=None)  # first run after upgrade
    assert reg.updates == []
    assert saved == {"handled": ["kr_finance_kit_kr_005930"]}


def test_wrapper_renames_new_entity_and_saves(monkeypatch):
    reg = FakeRegistry([
        _ent("sensor.fi_kr_005930", "kr_finance_kit_kr_005930"),
        _ent("sensor.microsoft", "kr_finance_kit_us_MSFT"),
    ])
    saved = _run(monkeypatch, reg, stored={"handled": ["kr_finance_kit_kr_005930"]})
    assert reg.updates == [("sensor.microsoft", "sensor.fi_us_msft")]
    assert saved == {"handled": ["kr_finance_kit_kr_005930", "kr_finance_kit_us_MSFT"]}


def test_wrapper_collision_guard(monkeypatch):
    reg = FakeRegistry([
        _ent("sensor.microsoft", "kr_finance_kit_us_MSFT"),
        SimpleNamespace(entity_id="sensor.fi_us_msft", unique_id="someone_else", platform="other", domain="sensor"),
    ])
    _run(monkeypatch, reg, stored={"handled": []})
    assert reg.updates == []


def test_wrapper_no_save_when_unchanged(monkeypatch):
    reg = FakeRegistry([_ent("sensor.fi_kr_005930", "kr_finance_kit_kr_005930")])
    saved = _run(monkeypatch, reg, stored={"handled": ["kr_finance_kit_kr_005930"]})
    assert saved is None


# ---------------------------------------------------------------- disclosure sensors

def test_disclosure_sensors_use_options_corp_codes():
    """KR tickers added after install (options/panel) get binary_sensors too."""
    from custom_components.kr_finance_kit import binary_sensor

    disclosure = SimpleNamespace(data=[], last_update_success=True)
    market = SimpleNamespace(positions=[])
    entry = SimpleNamespace(
        entry_id="e1",
        data={"disclosure_corp_codes": ["00126380"]},
        options={"disclosure_corp_codes": ["00126380", "00164779"],
                 "disclosure_corp_names": {"00164779": "SK하이닉스"}},
    )
    hass = SimpleNamespace(data={D: {"e1": {"disclosure": disclosure, "market": market}}})
    added = []
    asyncio.run(binary_sensor.async_setup_entry(hass, entry, lambda ents: added.extend(ents)))
    assert sorted(e.unique_id for e in added) == [
        "kr_finance_kit_disclosure_00126380", "kr_finance_kit_disclosure_00164779"]
