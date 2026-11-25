"""PG-ASYNCPG-001: live PostgreSQL protocol and visible close fallback."""

import warnings

import pytest
from driver_samples import sample

from hmt_pg_patterns import asyncpg_driver as driver
from hmt_pg_patterns.asyncpg_pool import lease, pool
from hmt_pg_patterns.models import QueryWindow

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_asyncpg_bound_io_and_classified_close(pg_conn, db_config):
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        async with driver.connection(db_config, timeout=0.1) as conn:
            await driver.insert_metric(conn, sample())
            assert await driver.fetch_metrics(conn, QueryWindow()) == [sample()]
            assert await driver.fetch_metrics(conn, QueryWindow(after_id=1)) == []
    assert conn.is_closed()
    assert all("FORCED_TERMINATION" in str(item.message) for item in captured)


async def test_asyncpg_context_rolls_back_failed_transaction(pg_conn, db_config):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        async with driver.connection(db_config, timeout=0.1) as conn:
            with pytest.raises(RuntimeError, match="application"):
                async with conn.transaction():
                    await driver.insert_metric(conn, sample())
                    raise RuntimeError("application")
            assert await driver.fetch_metrics(conn, QueryWindow()) == []


async def test_asyncpg_original_query_exception_survives_teardown(pg_conn, db_config):
    with warnings.catch_warnings(record=True), pytest.raises(RuntimeError, match="query failure"):
        async with driver.connection(db_config, timeout=0.1):
            raise RuntimeError("query failure")


async def test_asyncpg_finite_pool_lease_and_close(pg_conn, db_config):
    with warnings.catch_warnings(record=True):
        async with pool(db_config, size=1, timeout=0.1) as instance:
            async with lease(instance, timeout=2) as conn:
                await driver.insert_metric(conn, sample())
                assert await driver.fetch_metrics(conn, QueryWindow()) == [sample()]
    assert instance.is_closing()


async def test_exhausted_pool_wait_is_bounded(db_config):
    with warnings.catch_warnings(record=True):
        async with pool(db_config, size=1, timeout=0.1) as instance:
            async with lease(instance, timeout=0.1):
                with pytest.raises(TimeoutError):
                    async with lease(instance, timeout=0.01):
                        pytest.fail("finite pool admitted a second concurrent lease")
    assert instance.is_closing()
