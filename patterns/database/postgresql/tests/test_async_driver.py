"""PG-ASYNC-001: async lifecycle, real rollback, and coroutine cancellation."""

import asyncio

import psycopg
import pytest
from driver_samples import sample

from hmt_pg_patterns import async_driver as driver
from hmt_pg_patterns.models import QueryWindow

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_async_parameter_read_and_write(pg_conn, pg_dsn):
    async with await psycopg.AsyncConnection.connect(pg_dsn, autocommit=True) as conn:
        await driver.insert_metric(conn, sample())
        assert (await driver.fetch_metrics(conn, QueryWindow())) == [sample()]
        assert await driver.fetch_metrics(conn, QueryWindow(after_id=1)) == []


async def test_async_retry_rolls_back_then_replays(pg_conn, pg_dsn):
    attempts = []

    async def operation(conn):
        attempts.append(1)
        await driver.insert_metric(conn, sample())
        if len(attempts) < 2:
            await conn.execute(
                "DO $$ BEGIN RAISE EXCEPTION 'retry witness' USING ERRCODE='40001'; END $$"
            )
        return 7

    async with await psycopg.AsyncConnection.connect(pg_dsn, autocommit=True) as conn:
        assert await driver.transaction_retry(conn, operation) == 7
        assert len(attempts) == 2
        assert len(await driver.fetch_metrics(conn, QueryWindow())) == 1


async def test_async_exhaustion_and_nonretry_error(pg_conn, pg_dsn):
    async def operation(conn):
        await driver.insert_metric(conn, sample())
        await conn.execute(
            "DO $$ BEGIN RAISE EXCEPTION 'retry witness' USING ERRCODE='40P01'; END $$"
        )

    async with await psycopg.AsyncConnection.connect(pg_dsn, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.DeadlockDetected):
            await driver.transaction_retry(conn, operation, attempts=1)
        assert await driver.fetch_metrics(conn, QueryWindow()) == []
        await driver.insert_metric(conn, sample())
        with pytest.raises(psycopg.errors.UniqueViolation):
            await driver.transaction_retry(conn, lambda c: driver.insert_metric(c, sample()))


async def test_coroutine_cancellation_rolls_back_staged_write(pg_conn, pg_dsn):
    staged, release = asyncio.Event(), asyncio.Event()

    async def operation(conn):
        await driver.insert_metric(conn, sample())
        staged.set()
        await release.wait()

    async with await psycopg.AsyncConnection.connect(pg_dsn, autocommit=True) as conn:
        task = asyncio.create_task(driver.transaction_retry(conn, operation))
        await asyncio.wait_for(staged.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await driver.fetch_metrics(conn, QueryWindow()) == []
        assert conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
