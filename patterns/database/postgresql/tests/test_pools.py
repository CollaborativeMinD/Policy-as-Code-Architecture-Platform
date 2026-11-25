"""PG-POOL-001: explicit readiness, connection lease, release, and owner close."""

import pytest
from driver_samples import sample

from hmt_pg_patterns import async_driver, sync_driver
from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.pools import async_pool, sync_pool

pytestmark = pytest.mark.integration


def test_sync_pool_has_finite_capacity_and_closes(pg_conn, db_config):
    with sync_pool(db_config, size=1) as pool:
        assert pool.max_size == 1
        with pool.connection() as conn:
            sync_driver.insert_metric(conn, sample())
        with pool.connection() as conn:
            assert sync_driver.fetch_metrics(conn, QueryWindow()) == [sample()]
    assert pool.closed


@pytest.mark.asyncio
async def test_async_pool_explicit_open_and_close(pg_conn, db_config):
    async with async_pool(db_config, size=1) as pool:
        assert pool.max_size == 1
        async with pool.connection() as conn:
            await async_driver.insert_metric(conn, sample())
        async with pool.connection() as conn:
            assert await async_driver.fetch_metrics(conn, QueryWindow()) == [sample()]
    assert pool.closed


def test_sync_pool_still_closes_on_application_error(db_config):
    with pytest.raises(RuntimeError, match="application"):
        with sync_pool(db_config, size=1) as pool:
            raise RuntimeError("application")
    assert pool.closed
