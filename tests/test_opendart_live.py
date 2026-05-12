"""Optional live tests against the real OpenDart API.

Skipped unless the ``OPENDART_API_KEY`` env var is set. The key MUST come
from the environment — never check a real key into git. The default
``pytest tests/`` run from CI does NOT trigger these because the env var
isn't set there.

Run locally::

    OPENDART_API_KEY=xxx pytest tests/test_opendart_live.py -v

These reach the real ``list.json`` / ``company.json`` endpoints and
exercise the same response shape ``api/opendart.py`` uses inside HA, so
a green run gives high confidence the integration will work end-to-end.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import pytest

from custom_components.kr_finance_kit.api.opendart import (
    OPENDART_COMPANY_URL,
    OPENDART_CORPCODE_URL,
    OPENDART_LIST_URL,
    _normalize,
    _parse_corp_code_xml,
    _unzip_corp_code,
)

KEY = os.environ.get("OPENDART_API_KEY")
pytestmark = pytest.mark.skipif(
    not KEY,
    reason="OPENDART_API_KEY env var not set — skipping live OpenDart tests",
)


def _get(url: str, **params) -> dict:
    qs = urllib.parse.urlencode({**params, "crtfc_key": KEY})
    with urllib.request.urlopen(f"{url}?{qs}", timeout=15) as r:
        return json.loads(r.read())


def test_live_api_key_is_accepted():
    payload = _get(OPENDART_LIST_URL, page_count="1")
    # 000 = OK, 013 = no data for the query — both mean the key is valid.
    assert payload.get("status") in ("000", "013"), payload


def test_live_corp_code_xml_maps_known_stock_codes():
    """Download corpCode.xml ZIP, unzip, parse, and verify well-known mappings.

    This is what resolve_corp_codes_by_stock relies on under the hood.
    Mappings checked: Samsung Electronics (005930→00126380), SK Hynix
    (000660→00164779).
    """
    qs = urllib.parse.urlencode({"crtfc_key": KEY})
    with urllib.request.urlopen(f"{OPENDART_CORPCODE_URL}?{qs}", timeout=30) as r:
        zip_bytes = r.read()
    xml_bytes = _unzip_corp_code(zip_bytes)
    mapping = _parse_corp_code_xml(xml_bytes)
    assert mapping.get("005930") == "00126380", "Samsung Electronics mapping changed"
    assert mapping.get("000660") == "00164779", "SK Hynix mapping changed"
    # OpenDart lists ~3000 KRX equities; a sane lower bound guards against
    # the dump being silently truncated or empty.
    assert len(mapping) > 2000


def test_live_company_lookup_with_real_corp_code():
    """company.json should accept a true 8-digit corp_code (not a stock code)."""
    payload = _get(OPENDART_COMPANY_URL, corp_code="00126380")
    assert payload.get("status") == "000"
    assert payload.get("corp_code") == "00126380"
    assert "삼성" in (payload.get("corp_name") or "")


def test_live_recent_disclosures_normalize_round_trip():
    end = datetime.now().strftime("%Y%m%d")
    bgn = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    payload = _get(
        OPENDART_LIST_URL,
        corp_code="00126380",
        bgn_de=bgn,
        end_de=end,
        page_count="5",
    )
    assert payload.get("status") in ("000", "013")
    for item in payload.get("list") or []:
        normalized = _normalize(item)
        assert normalized["corp_code"] == "00126380"
        assert normalized["report_nm"]
        assert normalized["rcept_no"]
        # URL must be present when rcept_no is non-empty.
        assert normalized["url"]
        assert normalized["url"].endswith(f"rcpNo={item['rcept_no']}")
