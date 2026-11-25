"""Cooperative per-provider scheduling shared by all callers on HA's loop."""
import asyncio
from collections import OrderedDict, deque
from email.utils import parsedate_to_datetime
from random import uniform
from time import monotonic, time
from weakref import WeakKeyDictionary


class ProviderBusy(RuntimeError):
    """No outbound call was made. Try again on a later refresh."""


class Backoff(RuntimeError):
    def __init__(self, seconds=900):
        super().__init__("External service temporarily unavailable")
        self.seconds = seconds


def retry_delay(header, minimum=900):
    try:
        seconds = int(header)
    except (TypeError, ValueError):
        try:
            seconds = parsedate_to_datetime(header).timestamp() - time()
        except (TypeError, ValueError, OverflowError, AttributeError):
            seconds = 0
    return max(minimum, seconds)


class RequestGate:
    def __init__(self, gap=8, startup_spread=30):
        self.gap = gap
        self.lock = asyncio.Lock()
        self.next_call = monotonic() + uniform(0, startup_spread)
        self.resume = 0
        self.failures = 0
        self.cache = OrderedDict()
        self.pending = {}
        self.interactive_starts = deque()

    async def run(self, key, ttl, fetch):
        hit = self.cache.get(key)
        if hit and hit[0] > monotonic():
            return hit[1]
        if self.resume > monotonic():
            raise ProviderBusy("Provider cooldown")
        if key not in self.pending:
            optional = key[0] in ("history", "search")
            if optional and len(self.interactive_starts) >= 60 and self.interactive_starts[0] > monotonic() - 3600:
                raise ProviderBusy("Interactive lookup budget exhausted")
            if len(self.pending) >= (4 if optional else 8):
                raise ProviderBusy("Provider queue full")
            task = asyncio.create_task(self._fetch(key, ttl, fetch))
            self.pending[key] = task
            # The operation owns its slot until completion even if its caller
            # disconnects during an executor call.
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        return await asyncio.shield(self.pending[key])

    async def _fetch(self, key, ttl, fetch):
        try:
            async with self.lock:
                if self.resume > monotonic():
                    raise ProviderBusy("Provider cooldown")
                await asyncio.sleep(max(0, self.next_call - monotonic()))
                # Limit optional cache misses separately so charts and search
                # cannot consume every available slot on a busy dashboard.
                if key[0] in ("history", "search"):
                    now = monotonic()
                    while self.interactive_starts and self.interactive_starts[0] <= now - 3600:
                        self.interactive_starts.popleft()
                    if len(self.interactive_starts) >= 60:
                        raise ProviderBusy("Interactive lookup budget exhausted")
                    self.interactive_starts.append(now)
                try:
                    result = await fetch()
                except (TimeoutError, ConnectionError):
                    self.resume = monotonic() + 900
                    raise Backoff() from None
                except Backoff as err:
                    self.failures = min(self.failures + 1, 5)
                    self.resume = monotonic() + max(err.seconds, 900 * 2 ** (self.failures - 1))
                    raise
                finally:
                    self.next_call = monotonic() + self.gap + uniform(0, self.gap / 2)
                self.failures = 0
                self.cache[key] = (monotonic() + ttl, result)
                self.cache.move_to_end(key)
                if len(self.cache) > 512:
                    self.cache.popitem(last=False)
                return result
        finally:
            self.pending.pop(key, None)


_gates = WeakKeyDictionary()


def gate(provider):
    gates = _gates.setdefault(asyncio.get_running_loop(), {})
    if provider not in gates:
        gates[provider] = RequestGate(gap=6) if provider == "yahoo" else RequestGate()
    return gates[provider]
