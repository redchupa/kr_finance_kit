"""OpenDart disclosure fetcher.

We hit only the free ``list.json`` endpoint. The API key is loaded from
the config entry and never appears in source, fixtures, or logs. HTTP is
done via Home Assistant's shared aiohttp client session so we benefit
from the framework's connection pooling and shutdown handling.

``fetch_recent_disclosures`` returns the recent disclosures (last day) for
the requested corp_codes; the binary_sensor layer decides what counts as
"new".

HA-specific imports (``HomeAssistant``, ``async_get_clientsession``) live
inside function bodies so pure parsing helpers (``_normalize``,
``_parse_rcept_dt``) can be imported and unit-tested without Home
Assistant installed.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..const import LOGGER, TZ_KST

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

OPENDART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
OPENDART_COMPANY_URL = "https://opendart.fss.or.kr/api/company.json"
_TIMEOUT = 15


def _today_range() -> tuple[str, str]:
    """Yesterday → today (KST) as YYYYMMDD — OpenDart's date format."""
    today = datetime.now(TZ_KST).date()
    return (today - timedelta(days=1)).strftime("%Y%m%d"), today.strftime("%Y%m%d")


def _parse_rcept_dt(raw: str) -> datetime | None:
    if not raw or len(raw) != 8:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d").replace(tzinfo=TZ_KST)
    except ValueError:
        return None


def _normalize(item: dict[str, Any]) -> dict[str, Any]:
    rcept_no = item.get("rcept_no", "")
    return {
        "corp_code": item.get("corp_code"),
        "corp_name": item.get("corp_name"),
        "report_nm": item.get("report_nm"),
        "rcept_no": rcept_no,
        "rcept_dt": item.get("rcept_dt"),
        "rcept_dt_parsed": _parse_rcept_dt(item.get("rcept_dt", "")),
        "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}" if rcept_no else None,
    }


async def fetch_recent_disclosures(
    hass: "HomeAssistant", api_key: str, corp_codes: list[str]
) -> list[dict[str, Any]]:
    if not api_key or not corp_codes:
        return []
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    bgn, end = _today_range()
    session = async_get_clientsession(hass)
    results: list[dict[str, Any]] = []
    for code in corp_codes:
        try:
            async with session.get(
                OPENDART_LIST_URL,
                params={
                    "crtfc_key": api_key,
                    "corp_code": code,
                    "bgn_de": bgn,
                    "end_de": end,
                    "page_count": "10",
                },
                timeout=_TIMEOUT,
            ) as r:
                payload = await r.json(content_type=None)
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("OpenDart fetch %s failed: %s", code, err)
            continue
        status = payload.get("status")
        if status not in ("000", "013"):  # 013 = no data is OK
            LOGGER.debug(
                "OpenDart non-OK status for %s: %s (%s)",
                code,
                status,
                payload.get("message"),
            )
            continue
        for item in payload.get("list", []) or []:
            results.append(_normalize(item))
    return results


async def resolve_corp_codes_by_stock(
    hass: "HomeAssistant", api_key: str, stock_codes: list[str]
) -> dict[str, str]:
    """Resolve KR stock_codes (e.g. ``005930``) to OpenDart corp_codes.

    OpenDart's ``company.json`` accepts a corp_code natively but also
    permits looking up by ``stock_code`` for listed companies, which is
    what users naturally type. Codes we can't resolve are dropped from
    the result map (the caller treats absence as "skip").

    The single corp-code XML dump is heavy (~1MB, all listed companies);
    this per-stock lookup costs one small request per code and we only
    do it during Config Flow setup, not in the runtime hot path.
    """
    if not api_key or not stock_codes:
        return {}
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    out: dict[str, str] = {}
    for stock in stock_codes:
        sc = stock.strip()
        if not sc:
            continue
        try:
            async with session.get(
                OPENDART_COMPANY_URL,
                params={"crtfc_key": api_key, "corp_code": sc},
                timeout=_TIMEOUT,
            ) as r:
                payload = await r.json(content_type=None)
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("OpenDart resolve %s failed: %s", sc, err)
            continue
        # ``company.json`` returns the company record directly. status 000 == OK.
        if payload.get("status") == "000" and payload.get("corp_code"):
            out[sc] = payload["corp_code"]
        elif payload.get("status") != "000":
            LOGGER.debug(
                "OpenDart resolve %s non-OK: %s (%s)",
                sc,
                payload.get("status"),
                payload.get("message"),
            )
    return out


async def validate_api_key(hass: "HomeAssistant", api_key: str) -> bool:
    """Probe the OpenDart API with a 1-row request — used by Config Flow."""
    if not api_key:
        return False
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    try:
        async with session.get(
            OPENDART_LIST_URL,
            params={"crtfc_key": api_key, "page_count": "1"},
            timeout=_TIMEOUT,
        ) as r:
            payload = await r.json(content_type=None)
    except Exception as err:  # noqa: BLE001
        LOGGER.debug("OpenDart validate failed: %s", err)
        return False
    # 000 = OK, 013 = no data (still valid key), 020 = invalid/no permission.
    return payload.get("status") in ("000", "013")
