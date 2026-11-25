"""PG-POOL-001: finite capacity, explicit readiness, one pool owner per layer."""

from contextlib import asynccontextmanager, contextmanager

from psycopg_pool import AsyncConnectionPool, ConnectionPool

from .config import DbConfig
from .driver_contracts import pool_limits


def _options(config: DbConfig, size: int, timeout: float) -> dict:
    pool_limits(size, timeout)
    return {
        "kwargs": dict(config.connect_kwargs(), autocommit=True),
        "min_size": 1,
        "max_size": size,
        "max_waiting": size * 2,
        "timeout": timeout,
        "open": False,
    }


@contextmanager
def sync_pool(config: DbConfig, size: int = 4, timeout: float = 5.0):
    """Acquire one connection per independent unit of work."""
    pool = ConnectionPool(**_options(config, size, timeout))
    try:
        pool.open(wait=True, timeout=timeout)
        yield pool
    finally:
        pool.close(timeout=timeout)


@asynccontextmanager
async def async_pool(config: DbConfig, size: int = 4, timeout: float = 5.0):
    """Own async pool readiness and closure, with finite connection admission."""
    pool = AsyncConnectionPool(**_options(config, size, timeout))
    try:
        await pool.open(wait=True, timeout=timeout)
        yield pool
    finally:
        await pool.close(timeout=timeout)
