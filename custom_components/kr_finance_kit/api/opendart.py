"""OpenDart disclosure fetcher.

We hit only the free ``list.json`` endpoint for disclosures and
``corpCode.xml`` for the one-time stock→corp_code mapping. The API key is
loaded from the config entry and never appears in source, fixtures, or
logs. HTTP runs through Home Assistant's shared aiohttp client session so
we benefit from the framework's connection pooling and shutdown handling.

``fetch_recent_disclosures`` returns the recent disclosures for the
requested corp_codes; the binary_sensor layer decides what counts as
"new".

``resolve_corp_codes_by_stock`` downloads OpenDart's authoritative
``corpCode.xml`` dump (zipped, ~1MB, all listed companies) and builds an
in-memory ``stock_code → corp_code`` index. The mapping is cached for
the lifetime of the process — Config Flow calls it once at setup and
afterwards the stored corp_codes drive the polling. We do **not** try
``company.json?corp_code=<stock_code>`` — that endpoint silently returns
``corp_code=null`` for stock codes (it only accepts true 8-digit corp
codes), which would leave the disclosure feature broken without any
visible error.

HA-specific imports (``HomeAssistant``, ``async_get_clientsession``) live
inside function bodies so pure parsing helpers (``_normalize``,
``_parse_rcept_dt``, ``_parse_corp_code_xml``) can be imported and
unit-tested without Home Assistant installed.
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..const import LOGGER, TZ_KST

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

OPENDART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
OPENDART_COMPANY_URL = "https://opendart.fss.or.kr/api/company.json"
OPENDART_CORPCODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
_TIMEOUT = 30  # corpCode.xml is ~1MB so allow more headroom than the small endpoints


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


def _parse_corp_code_xml(xml_bytes: bytes) -> dict[str, tuple[str, str]]:
    """Build a ``stock_code → (corp_code, corp_name)`` map from CORPCODE.xml.

    The XML schema is::

        <result>
          <list>
            <corp_code>00126380</corp_code>
            <corp_name>삼성전자</corp_name>
            <stock_code>005930</stock_code>
            <modify_date>20240417</modify_date>
          </list>
          <list>...</list>
        </result>

    Entries without a stock_code (non-listed companies, ETFs sometimes
    missing it) are skipped — we only need listed-equity mappings. We
    capture ``corp_name`` alongside ``corp_code`` because it doubles as
    the friendly label for our price sensors ("삼성전자" instead of
    "005930").
    """
    out: dict[str, tuple[str, str]] = {}
    root = ET.fromstring(xml_bytes)
    for entry in root.findall("list"):
        stock = (entry.findtext("stock_code") or "").strip()
        corp = (entry.findtext("corp_code") or "").strip()
        name = (entry.findtext("corp_name") or "").strip()
        if stock and corp:
            out[stock] = (corp, name)
    return out


def _unzip_corp_code(zip_bytes: bytes) -> bytes:
    """Extract the single ``CORPCODE.xml`` member from the downloaded ZIP."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        # OpenDart always ships exactly one member named CORPCODE.xml, but be
        # defensive against future schema tweaks by picking the first .xml.
        xml_name = next((n for n in zf.namelist() if n.lower().endswith(".xml")), None)
        if xml_name is None:
            raise RuntimeError("CORPCODE archive has no .xml member")
        return zf.read(xml_name)


# Process-level cache: the mapping is several megabytes of strings but
# rarely changes (OpenDart updates corp_codes a few times a year). Caching
# avoids re-downloading on every Options-flow save.
_corp_code_cache: dict[str, tuple[str, str]] | None = None


def _set_corp_code_cache(mapping: dict[str, tuple[str, str]]) -> None:
    """Test seam — let unit tests prime the cache without network."""
    global _corp_code_cache
    _corp_code_cache = mapping


def _clear_corp_code_cache() -> None:
    global _corp_code_cache
    _corp_code_cache = None


async def _load_corp_code_map(
    hass: "HomeAssistant", api_key: str
) -> dict[str, tuple[str, str]]:
    """Download (or reuse cached) corpCode.xml and return the stock→(corp_code, name) map."""
    global _corp_code_cache
    if _corp_code_cache is not None:
        return _corp_code_cache

    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    async with session.get(
        OPENDART_CORPCODE_URL,
        params={"crtfc_key": api_key},
        timeout=_TIMEOUT,
    ) as r:
        body = await r.read()

    # OpenDart returns either:
    #  - on error: a small JSON body with {"status": "...", "message": "..."}
    #  - on success: a ZIP archive containing CORPCODE.xml
    # We disambiguate by attempting a JSON decode first.
    try:
        import json

        as_json = json.loads(body)
        if isinstance(as_json, dict) and as_json.get("status"):
            LOGGER.warning(
                "OpenDart corpCode.xml fetch failed: %s (%s)",
                as_json.get("status"),
                as_json.get("message"),
            )
            return {}
    except (ValueError, UnicodeDecodeError):
        pass  # Expected — body is a binary ZIP.

    try:
        xml_bytes = _unzip_corp_code(body)
        mapping = _parse_corp_code_xml(xml_bytes)
    except Exception as err:  # noqa: BLE001
        LOGGER.warning("Failed to parse OpenDart corpCode.xml: %s", err)
        return {}

    LOGGER.info("OpenDart corpCode.xml loaded: %d listed-equity entries", len(mapping))
    _corp_code_cache = mapping
    return mapping


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
    """Resolve KR 6-digit stock codes (e.g. ``005930``) to OpenDart corp_codes.

    Uses the authoritative ``corpCode.xml`` dump (downloaded once per
    process, then cached). Codes we can't resolve are simply absent from
    the result — the caller treats absence as "skip this stock".
    """
    if not api_key or not stock_codes:
        return {}
    mapping = await _load_corp_code_map(hass, api_key)
    out: dict[str, str] = {}
    for stock in stock_codes:
        sc = stock.strip()
        if not sc:
            continue
        entry = mapping.get(sc)
        if entry:
            out[sc] = entry[0]
        else:
            LOGGER.debug("stock_code %s has no listed-equity mapping in corpCode.xml", sc)
    return out


async def resolve_kr_ticker_names(
    hass: "HomeAssistant", api_key: str, stock_codes: list[str]
) -> dict[str, str]:
    """Resolve KR 6-digit stock codes to their Korean company names.

    Same data source as ``resolve_corp_codes_by_stock`` (corpCode.xml),
    just a different projection. Used by Config Flow to label price
    sensors with friendly names like "삼성전자" instead of "005930".
    Unmapped codes are omitted; caller falls back to the bare code.
    """
    if not api_key or not stock_codes:
        return {}
    mapping = await _load_corp_code_map(hass, api_key)
    out: dict[str, str] = {}
    for stock in stock_codes:
        sc = stock.strip()
        if not sc:
            continue
        entry = mapping.get(sc)
        if entry and entry[1]:
            out[sc] = entry[1]
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
