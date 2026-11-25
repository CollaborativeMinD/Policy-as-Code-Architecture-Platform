"""Owned async source used to inject failures without background tasks."""

import asyncio

from hmt_pg_patterns.streaming_contracts import Policy

TINY = Policy(block_size_target=3, window_size=2, min_size=2, max_size=5, quantum_bytes=4)


class Source:
    def __init__(self, packets=(), failure=None, cleanup=None, delay=0):
        self.packets = iter(packets)
        self.failure, self.cleanup, self.delay = failure, cleanup, delay
        self.reads, self.closed = 0, False

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.reads += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        try:
            return next(self.packets)
        except StopIteration:
            if self.failure:
                raise self.failure
            raise StopAsyncIteration from None

    async def aclose(self):
        self.closed = True
        if self.cleanup == "slow":
            await asyncio.sleep(1)
        elif self.cleanup:
            raise self.cleanup


async def no_close_source():
    yield b"abc"
