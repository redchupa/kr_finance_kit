"""Frontend-serialize guard for the config_flow schema.

HA's add-integration dialog turns the voluptuous schema returned by
``async_show_form`` into JSON via ``voluptuous_serialize.convert``,
passing ``homeassistant.helpers.config_validation.custom_serializer``
to handle HA-specific types (selectors, ConfigType, etc.).

The previous test suite exercised module import and business logic
but never went through this serialization step. v0.1.44 shipped a
schema that used ``vol.All(vol.Coerce(...), vol.Range(...))`` and
``vol.All(cv.ensure_list, [vol.In(...)])`` — both nodes
``voluptuous_serialize`` cannot decode even with the HA custom
serializer — and the integration's add dialog started returning
500 Internal Server Error on every load. v0.1.48 replaced those
two fields with ``NumberSelector`` and ``SelectSelector(multiple=True)``
respectively.

This test runs the same serialization path the frontend uses. If a
future schema change reintroduces a non-serializable node, this test
fails locally before the change ships.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import voluptuous_serialize

# Make custom_components/kr_finance_kit importable
_ROOT = Path(__file__).resolve().parent.parent / "custom_components"
sys.path.insert(0, str(_ROOT))


@pytest.fixture(scope="module")
def schema():
    from homeassistant.helpers import config_validation as cv

    from kr_finance_kit import config_flow

    return config_flow._FORM_SCHEMA, cv.custom_serializer


def test_form_schema_is_frontend_serializable(schema):
    """The flow schema must survive voluptuous_serialize.convert with HA's
    custom_serializer — exactly the path the add-integration dialog uses.
    A failure here would surface in the UI as
    ``500 Internal Server Error Server got itself in trouble``.
    """
    form_schema, custom_serializer = schema
    result = voluptuous_serialize.convert(form_schema, custom_serializer=custom_serializer)
    assert isinstance(result, list)
    assert len(result) > 0


def test_form_schema_each_field_has_a_type_or_selector(schema):
    """A serialized field must carry either a primitive ``type`` or a
    ``selector`` block; otherwise the HA frontend has no widget to
    render and the dialog silently breaks.
    """
    form_schema, custom_serializer = schema
    result = voluptuous_serialize.convert(form_schema, custom_serializer=custom_serializer)
    for entry in result:
        assert "name" in entry, f"field missing name: {entry}"
        assert "type" in entry or "selector" in entry, (
            f"field {entry.get('name')} has neither type nor selector — "
            f"frontend cannot render: {entry}"
        )
