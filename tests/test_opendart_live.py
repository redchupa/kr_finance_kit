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
    OPENDART_LIST_URL,
    _normalize,
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


def test_live_resolve_samsung_stock_code():
    payload = _get(OPENDART_COMPANY_URL, corp_code="005930")
    assert payload.get("status") == "000"
    # Samsung Electronics' canonical OpenDart corp_code.
    assert payload.get("corp_code") == "00126380"
    assert "삼성" in (payload.get("corp_name") or "")


def test_live_resolve_invalid_stock_code_returns_non_ok():
    payload = _get(OPENDART_COMPANY_URL, corp_code="999999")
    # We intentionally check non-000 (any error code is fine — resolver
    # treats anything other than 000 as "skip this entry").
    assert payload.get("status") != "000"


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
