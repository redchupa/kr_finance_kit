"""LLM tool registration for KR Finance Kit.

A single ``llm.API`` is registered per config entry, exposing one tool —
``finance_query`` — that dispatches on a ``query_type`` argument. The
actual dispatch logic lives in ``llm_dispatch.dispatch_query`` so it can
be unit-tested without Home Assistant in the import path.
"""
from __future__ import annotations

from typing import Any, Callable

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .const import (
    DOMAIN,
    FX_USDKRW,
    INDEX_KOSDAQ,
    INDEX_KOSPI,
    LOGGER,
    MARKET_KR,
    MARKET_US,
)
from .llm_dispatch import QUERY_TYPES, dispatch_query

_API_PROMPT = (
    "한국 금융 데이터(코스피·코스닥 지수, USD/KRW 환율, 한국·미국 종목 시세, "
    "보유 종목 평가손익, OpenDart 공시, 변동률 상위 종목, 시장 요약)를 조회할 수 있습니다."
)


def _api_id(entry_id: str) -> str:
    return f"{DOMAIN}__{entry_id}"


class FinanceQueryTool(llm.Tool):
    name = "finance_query"
    description = (
        "Query Korean finance data. query_type values: "
        + ", ".join(QUERY_TYPES)
        + ". 'top_movers' takes optional 'limit'. 'disclosure_for_ticker' takes 'ticker'."
    )
    parameters = vol.Schema(
        {
            vol.Required("query_type"): vol.In(QUERY_TYPES),
            vol.Optional("ticker"): str,
            vol.Optional("market"): vol.In([MARKET_KR, MARKET_US]),
            vol.Optional("symbol"): vol.In([INDEX_KOSPI, INDEX_KOSDAQ, FX_USDKRW]),
            vol.Optional("limit"): vol.All(int, vol.Range(min=1, max=20)),
        }
    )

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__()
        self.hass = hass
        self.entry_id = entry_id

    @property
    def _store(self) -> dict[str, Any]:
        return self.hass.data.get(DOMAIN, {}).get(self.entry_id, {})

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> dict[str, Any]:
        market = self._store.get("market")
        disclosure = self._store.get("disclosure")
        return dispatch_query(
            tool_input.tool_args,
            market.data if market is not None else None,
            disclosure.data if disclosure is not None else None,
        )


class _FinanceAPI(llm.API):
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__(hass=hass, id=_api_id(entry_id), name="KR Finance Kit")
        self._entry_id = entry_id

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        return llm.APIInstance(
            api=self,
            api_prompt=_API_PROMPT,
            llm_context=llm_context,
            tools=[FinanceQueryTool(self.hass, self._entry_id)],
        )


async def async_setup_llm_api(
    hass: HomeAssistant, entry: ConfigEntry
) -> Callable[[], None] | None:
    api = _FinanceAPI(hass, entry.entry_id)
    unreg = llm.async_register_api(hass, api)
    LOGGER.info("Registered KR Finance Kit LLM API for entry %s", entry.entry_id)
    return unreg


def async_cleanup_llm_api(unregister: Callable[[], None] | None) -> None:
    if unregister is None:
        return
    try:
        unregister()
    except Exception as e:  # pragma: no cover
        LOGGER.debug("Error unregistering LLM API: %s", e)
