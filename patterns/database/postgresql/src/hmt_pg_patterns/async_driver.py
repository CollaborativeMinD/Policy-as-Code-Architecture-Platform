"""PG-ASYNC-001: native asyncio; cancellation propagates through transaction exit."""

from collections.abc import Awaitable, Callable

import psycopg
from psycopg.rows import dict_row

from .driver_contracts import RETRYABLE_SQLSTATES, owned_transaction
from .models import Metric, QueryWindow
from .queries import INSERT_SQL, SELECT_SQL, metric_values, window_values


async def fetch_metrics(conn: psycopg.AsyncConnection, window: QueryWindow) -> list[Metric]:
    """Read one bounded keyset page and validate every returned row."""
    params = window_values(window)
    async with conn.cursor(row_factory=dict_row) as cursor:
        await cursor.execute(SELECT_SQL, params)
        return [Metric.model_validate(row) for row in await cursor.fetchall()]


async def insert_metric(conn: psycopg.AsyncConnection, metric: Metric) -> None:
    """Bind a detached DTO; the caller owns the transaction."""
    await conn.execute(INSERT_SQL, metric_values(metric))


async def transaction_retry[T](
    conn: psycopg.AsyncConnection,
    operation: Callable[[psycopg.AsyncConnection], Awaitable[T]],
    attempts: int = 3,
) -> T:
    """Retry only 40001/40P01, never cancellation, transport loss, or uncertain commit.

    A callback contains DB effects only; it must not manage the outer transaction.
    Cancellation does not prove the backend did not complete an operation.
    """
    owned_transaction(conn, attempts)
    for _ in range(attempts - 1):
        try:
            return await _transaction_once(conn, operation)
        except psycopg.Error as error:
            if error.sqlstate not in RETRYABLE_SQLSTATES:
                raise
    return await _transaction_once(conn, operation)


async def _transaction_once[T](
    conn: psycopg.AsyncConnection, operation: Callable[[psycopg.AsyncConnection], Awaitable[T]]
) -> T:
    async with conn.transaction():
        return await operation(conn)
