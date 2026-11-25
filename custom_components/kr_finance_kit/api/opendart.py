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
import hashlib
from defusedxml import ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from .pacing import Backoff, ProviderBusy, gate, retry_delay
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
        if zf.getinfo(xml_name).file_size > 64 * 1024 * 1024:
            raise ValueError("OpenDart XML exceeds size limit")
        return zf.read(xml_name)


def _parse_archive(body: bytes) -> dict[str, tuple[str, str]]:
    return _parse_corp_code_xml(_unzip_corp_code(body))


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


def _check_http(response):
    if response.status in (403, 429) or response.status >= 500:
        raise Backoff(retry_delay(response.headers.get("Retry-After")))
    response.raise_for_status()


def _check_status(payload):
    status = payload.get("status")
    if status in ("012", "020", "800", "900"):
        raise Backoff(86400 if status == "020" else 900)


async def _json_request(session, params, ttl):
    async def fetch():
        async with session.get(OPENDART_LIST_URL, params=params, timeout=_TIMEOUT,
                               headers={"User-Agent": "Finance-Kit (Home Assistant integration)"},
                               allow_redirects=False) as response:
            _check_http(response)
            payload = await response.json(content_type=None)
            _check_status(payload)
            return payload

    key = tuple(sorted((k, hashlib.sha256(v.encode()).digest() if k == "crtfc_key" else v)
                       for k, v in params.items()))
    return await gate("dart").run(("json", key), ttl, fetch)


async def _load_corp_code_map(
    hass: "HomeAssistant", api_key: str
) -> dict[str, tuple[str, str]]:
    """Download (or reuse cached) corpCode.xml and return the stock→(corp_code, name) map."""
    global _corp_code_cache
    if _corp_code_cache is not None:
        return _corp_code_cache

    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    async def fetch():
        async with session.get(
            OPENDART_CORPCODE_URL, params={"crtfc_key": api_key},
            timeout=_TIMEOUT, allow_redirects=False,
            headers={"User-Agent": "Finance-Kit (Home Assistant integration)"},
        ) as response:
            _check_http(response)
            body = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                if len(body) + len(chunk) > 16 * 1024 * 1024:
                    raise ValueError("OpenDart archive exceeds size limit")
                body.extend(chunk)
        if body.lstrip().startswith(b"{"):
            import json
            _check_status(json.loads(body))
            return {}
        return await hass.async_add_executor_job(_parse_archive, body)
    try:
        mapping = await gate("dart").run(("directory", hashlib.sha256(api_key.encode()).digest()), 600, fetch)
    except (Backoff, ProviderBusy):
        raise
    except Exception as err:
        LOGGER.warning("OpenDart company directory unavailable (%s)", type(err).__name__)
        return {}

    LOGGER.info("OpenDart corpCode.xml loaded: %d listed-equity entries", len(mapping))
    if mapping:
        _corp_code_cache = mapping
    return mapping


async def fetch_recent_disclosures(
    hass: "HomeAssistant", api_key: str, corp_codes: list[str],
    categories: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch today's disclosures for the given corp_codes.

    ``categories`` filters by OpenDart's ``pblntf_ty`` parameter — the
    8-bucket scheme on the OpenDart list.json endpoint (A=정기공시 …
    J=공정위공시). When the list is empty / None we issue the request
    without the filter, which returns disclosures across all categories
    (the historical default).

    The API only accepts a single ``pblntf_ty`` value per request, so
    multi-category requests fan out into one call per category per
    corp_code. With 1-2 corp_codes and a small category subset this is
    still tiny traffic compared to the per-poll budget.
    """
    if not api_key or not corp_codes:
        return []
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    bgn, end = _today_range()
    session = async_get_clientsession(hass)
    results: list[dict[str, Any]] = []
    # Empty / None categories → single request per corp_code without filter.
    category_filters: list[str | None] = list(categories) if categories else [None]
    seen_rcept_no: set[str] = set()
    for code in corp_codes:
      for category in category_filters:
        params: dict[str, str] = {
            "crtfc_key": api_key,
            "corp_code": code,
            "bgn_de": bgn,
            "end_de": end,
            "page_count": "10",
        }
        if category:
            params["pblntf_ty"] = category
        try:
            payload = await _json_request(session, params, 900)
        except (Backoff, ProviderBusy):
            raise
        except Exception as err:  # noqa: BLE001
            LOGGER.debug("OpenDart fetch %s failed: %s", code, type(err).__name__)
            continue
        status = payload.get("status")
        if status not in ("000", "013"):  # 013 = no data is OK
            LOGGER.debug(
                "OpenDart returned an error for %s",
                code,
            )
            continue
        for item in payload.get("list", []) or []:
            # Same disclosure can be returned across overlapping category
            # filters (rare but possible). Dedupe by OpenDart's rcept_no
            # so the binary_sensor sees one entry per filing regardless of
            # how many categories were requested.
            rno = (item.get("rcept_no") or "").strip()
            if rno and rno in seen_rcept_no:
                continue
            if rno:
                seen_rcept_no.add(rno)
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
        payload = await _json_request(session, {"crtfc_key": api_key, "page_count": "1"}, 900)
    except (Backoff, ProviderBusy):
        raise
    except Exception as err:  # noqa: BLE001
        LOGGER.debug("OpenDart validate failed: %s", type(err).__name__)
        return False
    # 000 and 013 both confirm that the supplied credential works.
    return payload.get("status") in ("000", "013")
