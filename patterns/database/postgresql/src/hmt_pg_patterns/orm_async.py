"""PG-ORM-ASYNC-001: one SQLAlchemy connection/session per concurrent task."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import DbConfig
from .models import Metric, QueryWindow
from .orm import INSERT, SELECT, engine_options
from .queries import snapshot_metric, window_values


def create_pg_engine(config: DbConfig, size: int = 4) -> AsyncEngine:
    """Explicit postgresql+psycopg selects Psycopg3's native asynchronous dialect."""
    url, options = engine_options(config, size)
    return create_async_engine(url, **options)


async def insert_metric(engine: AsyncEngine, metric: Metric) -> None:
    """Validate and commit one insert within an owned async transaction."""
    params = snapshot_metric(metric).model_dump()
    async with engine.begin() as conn:
        await conn.execute(INSERT, params)


async def fetch_metrics(engine: AsyncEngine, window: QueryWindow) -> list[Metric]:
    """Read a bounded page, validate it, and release the async connection."""
    status, after_id, limit = window_values(window)
    async with engine.connect() as conn:
        rows = await conn.execute(SELECT, {"status": status, "after_id": after_id, "limit": limit})
        return [Metric.model_validate(dict(row)) for row in rows.mappings()]
