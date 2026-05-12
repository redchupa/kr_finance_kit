"""Unit tests for the corpCode.xml parser and stock→corp_code resolution.

We exercise the pure helpers (parse XML, unzip a zipped XML, lookup
via the cache seam) without standing up Home Assistant.
"""
from __future__ import annotations

import asyncio
import io
import zipfile
from pathlib import Path

import pytest

from custom_components.kr_finance_kit.api.opendart import (
    _clear_corp_code_cache,
    _parse_corp_code_xml,
    _set_corp_code_cache,
    _unzip_corp_code,
    resolve_corp_codes_by_stock,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def reset_cache():
    """Each test starts with a clean process-level cache."""
    _clear_corp_code_cache()
    yield
    _clear_corp_code_cache()


@pytest.fixture()
def sample_xml() -> bytes:
    return (FIXTURES / "corpcode_sample.xml").read_bytes()


def test_parse_corpcode_extracts_listed_entries(sample_xml):
    mapping = _parse_corp_code_xml(sample_xml)
    # Both listed equities resolve.
    assert mapping["005930"] == "00126380"
    assert mapping["000660"] == "00164779"


def test_parse_corpcode_skips_unlisted_entries(sample_xml):
    mapping = _parse_corp_code_xml(sample_xml)
    # The 비상장 entry has an empty stock_code — must be skipped, not stored
    # under "" or some other sentinel.
    assert "" not in mapping
    assert "00264529" not in mapping.values()


def test_unzip_corpcode_extracts_xml_member(sample_xml):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("CORPCODE.xml", sample_xml)
    extracted = _unzip_corp_code(buf.getvalue())
    assert extracted == sample_xml


def test_unzip_corpcode_picks_first_xml_when_multiple_members(sample_xml):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", b"ignore me")
        zf.writestr("CORPCODE.xml", sample_xml)
    assert _unzip_corp_code(buf.getvalue()) == sample_xml


def test_unzip_corpcode_raises_when_no_xml():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", b"no xml here")
    with pytest.raises(RuntimeError, match="no .xml member"):
        _unzip_corp_code(buf.getvalue())


def test_resolve_via_cached_mapping(sample_xml):
    """resolve_corp_codes_by_stock uses the in-memory cache when present."""
    _set_corp_code_cache(_parse_corp_code_xml(sample_xml))
    result = asyncio.run(
        resolve_corp_codes_by_stock(hass=None, api_key="dummy", stock_codes=["005930", "000660"])
    )
    assert result == {"005930": "00126380", "000660": "00164779"}


def test_resolve_skips_unknown_stock_codes(sample_xml):
    _set_corp_code_cache(_parse_corp_code_xml(sample_xml))
    result = asyncio.run(
        resolve_corp_codes_by_stock(hass=None, api_key="dummy", stock_codes=["005930", "999999"])
    )
    # Known: present. Unknown: absent (caller treats absence as "skip").
    assert result == {"005930": "00126380"}


def test_resolve_handles_whitespace_and_empty_inputs(sample_xml):
    _set_corp_code_cache(_parse_corp_code_xml(sample_xml))
    result = asyncio.run(
        resolve_corp_codes_by_stock(
            hass=None, api_key="dummy", stock_codes=["", "  ", " 005930 "]
        )
    )
    assert result == {"005930": "00126380"}


def test_resolve_returns_empty_when_no_api_key():
    result = asyncio.run(
        resolve_corp_codes_by_stock(hass=None, api_key="", stock_codes=["005930"])
    )
    assert result == {}


def test_resolve_returns_empty_when_no_stock_codes():
    result = asyncio.run(
        resolve_corp_codes_by_stock(hass=None, api_key="dummy", stock_codes=[])
    )
    assert result == {}
