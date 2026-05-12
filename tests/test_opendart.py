"""Tests for OpenDart payload normalization (offline, fixture-driven)."""
from __future__ import annotations

import json
from datetime import datetime

from custom_components.kr_finance_kit.api.opendart import _normalize, _parse_rcept_dt
from custom_components.kr_finance_kit.const import TZ_KST


def test_parse_rcept_dt_valid():
    dt = _parse_rcept_dt("20260101")
    assert dt == datetime(2026, 1, 1, tzinfo=TZ_KST)


def test_parse_rcept_dt_invalid():
    assert _parse_rcept_dt("") is None
    assert _parse_rcept_dt("bad") is None


def test_normalize_opendart_item(opendart_sample):
    payload = json.loads(opendart_sample)
    first = _normalize(payload["list"][0])
    assert first["corp_code"] == "00000001"
    assert first["corp_name"] == "예시전자"
    assert first["report_nm"].startswith("[기재정정]")
    assert first["rcept_no"] == "20260101000001"
    assert first["url"].endswith("rcpNo=20260101000001")
    assert first["rcept_dt_parsed"].year == 2026


def test_normalize_handles_missing_rcept_no():
    out = _normalize({"corp_code": "X", "corp_name": "Y", "report_nm": "Z"})
    assert out["url"] is None
    assert out["rcept_dt_parsed"] is None
