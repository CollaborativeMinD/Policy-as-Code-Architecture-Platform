"""PG-ASYNCPG-POOL-001: bounded pool lifecycle with explicit forced termination."""

import asyncio
import warnings
from contextlib import asynccontextmanager
from typing import Literal

import asyncpg

from .config import DbConfig
from .driver_contracts import pool_limits


async def close_pool(instance, timeout: float = 5.0) -> Literal["graceful", "forced"]:
    """Close by deadline, classifying forced termination when leases persist."""
    pool_limits(1, timeout)
    try:
        async with asyncio.timeout(timeout):
            await instance.close()
    except TimeoutError:
        instance.terminate()
        warnings.warn("ASYNCPG_POOL_FORCED_TERMINATION", RuntimeWarning, stacklevel=2)
        return "forced"
    return "graceful"


@asynccontextmanager
async def pool(config: DbConfig, size: int = 4, timeout: float = 5.0):
    """Own finite pool lifetime; acquire leases with an explicit timeout."""
    pool_limits(size, timeout)
    instance = await asyncpg.create_pool(
        **config.asyncpg_kwargs(),
        min_size=1,
        max_size=size,
        max_queries=10000,
        max_inactive_connection_lifetime=60,
    )
    try:
        yield instance
    except BaseException as primary:
        try:
            await close_pool(instance, timeout)
        except BaseException as cleanup:
            primary.add_note(f"Pool teardown failed: {type(cleanup).__name__}")
            raise primary from cleanup
        raise
    await close_pool(instance, timeout)


@asynccontextmanager
async def lease(instance, timeout: float = 5.0):
    """Acquire with a finite wait and release on normal, failed, or cancelled exit."""
    pool_limits(1, timeout)
    async with instance.acquire(timeout=timeout) as conn:
        yield conn
