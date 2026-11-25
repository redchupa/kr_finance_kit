"""Exercise provider traffic controls without making network requests."""
import asyncio
from time import monotonic

import pytest

from custom_components.kr_finance_kit.api.pacing import Backoff, ProviderBusy, RequestGate


def test_duplicate_clients_and_spacing():
    async def exercise():
        gate = RequestGate(gap=0.02, startup_spread=0)
        starts = []
        ends = []

        async def fetch():
            starts.append(monotonic())
            await asyncio.sleep(0)
            ends.append(monotonic())
            return 42

        results = await asyncio.gather(*(gate.run(("price", 1), 60, fetch) for _ in range(100)))
        assert results == [42] * 100
        assert await gate.run(("price", 1), 60, fetch) == 42
        await gate.run(("price", 2), 60, fetch)
        assert len(starts) == 2
        assert starts[1] - ends[0] >= 0.019

    asyncio.run(exercise())


def test_cancelled_client_and_queued_requests_respect_backoff():
    async def exercise():
        gate = RequestGate(gap=0, startup_spread=0)
        started, release = asyncio.Event(), asyncio.Event()

        async def throttled():
            started.set()
            await release.wait()
            raise Backoff(3600)

        async def unexpected():
            pytest.fail("Queued request reached the provider")

        first = asyncio.create_task(gate.run(("price", 1), 60, throttled))
        await started.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        joined = asyncio.create_task(gate.run(("price", 1), 60, unexpected))
        queued = asyncio.create_task(gate.run(("price", 2), 60, unexpected))
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(Backoff):
            await joined
        with pytest.raises(ProviderBusy):
            await queued
        assert gate.resume - monotonic() > 3599

    asyncio.run(exercise())


def test_interactive_budget_preserves_price_access():
    async def exercise():
        gate = RequestGate(gap=0, startup_spread=0)

        async def fetch():
            return 1

        for i in range(60):
            await gate.run(("history", i), 60, fetch)
        with pytest.raises(ProviderBusy):
            await gate.run(("search", "sample"), 60, fetch)
        assert await gate.run(("history", 0), 60, fetch) == 1
        assert await gate.run(("price", 0), 60, fetch) == 1

    asyncio.run(exercise())
