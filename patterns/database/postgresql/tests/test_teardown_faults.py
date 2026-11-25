"""Deterministic lifecycle fault injection; no claim of real network coverage."""

import asyncio

import pytest

from hmt_pg_patterns.asyncpg_driver import close_connection
from hmt_pg_patterns.asyncpg_pool import close_pool

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class CloseProbe:
    def __init__(self, outcome):
        self.outcome, self.terminated = outcome, False

    async def close(self, **kwargs):
        if self.outcome == "hang":
            await asyncio.Event().wait()
        if self.outcome == "error":
            raise ValueError("cleanup witness")

    def terminate(self):
        self.terminated = True


@pytest.mark.parametrize("closer", [close_connection, close_pool])
async def test_close_deadline_forces_and_classifies_termination(closer):
    probe = CloseProbe("hang")
    with pytest.warns(RuntimeWarning, match="FORCED_TERMINATION"):
        assert await closer(probe, timeout=0.01) == "forced"
    assert probe.terminated


@pytest.mark.parametrize("closer", [close_connection, close_pool])
async def test_graceful_close_is_distinct_from_timeout(closer):
    probe = CloseProbe("ok")
    assert await closer(probe, timeout=0.1) == "graceful"
    assert not probe.terminated


@pytest.mark.parametrize("closer", [close_connection, close_pool])
async def test_unexpected_close_error_propagates(closer):
    with pytest.raises(ValueError, match="cleanup witness"):
        await closer(CloseProbe("error"), timeout=0.1)
