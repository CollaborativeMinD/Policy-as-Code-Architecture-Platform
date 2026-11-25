"""PG-ASYNCPG-001: native PostgreSQL bindings and classified bounded teardown."""

import asyncio
import json
import warnings
from contextlib import asynccontextmanager
from typing import Literal

import asyncpg

from .config import DbConfig
from .driver_contracts import pool_limits
from .models import Metric, QueryWindow
from .queries import ASYNCPG_INSERT, ASYNCPG_SELECT, snapshot_metric, window_values


async def fetch_metrics(conn: asyncpg.Connection, window: QueryWindow) -> list[Metric]:
    """Bind a finite page and parse the driver default text JSON codec."""
    records = await conn.fetch(ASYNCPG_SELECT, *window_values(window))
    result = []
    for row in records:
        data = dict(row)
        data["telemetry"] = json.loads(data["telemetry"])
        result.append(Metric.model_validate(data))
    return result


async def insert_metric(conn: asyncpg.Connection, metric: Metric) -> None:
    """Bind one detached DTO; the caller controls transaction ownership."""
    item = snapshot_metric(metric)
    payload = json.dumps(item.telemetry, allow_nan=False, separators=(",", ":"))
    await conn.execute(ASYNCPG_INSERT, item.id, item.status, payload, item.observed_at)


async def close_connection(conn, timeout: float = 5.0) -> Literal["graceful", "forced"]:
    """A close timeout terminates transport and is observable, never success-shaped."""
    pool_limits(1, timeout)
    try:
        async with asyncio.timeout(timeout):
            await conn.close(timeout=timeout)
    except TimeoutError:
        conn.terminate()
        warnings.warn("ASYNCPG_CONNECTION_FORCED_TERMINATION", RuntimeWarning, stacklevel=2)
        return "forced"
    return "graceful"


@asynccontextmanager
async def connection(config: DbConfig, timeout: float = 5.0):
    """Own connection lifetime while preserving the primary failure on teardown."""
    pool_limits(1, timeout)
    conn = await asyncpg.connect(**config.asyncpg_kwargs())
    try:
        yield conn
    except BaseException as primary:
        try:
            await close_connection(conn, timeout)
        except BaseException as cleanup:
            primary.add_note(f"Connection teardown failed: {type(cleanup).__name__}")
            raise primary from cleanup
        raise
    await close_connection(conn, timeout)
