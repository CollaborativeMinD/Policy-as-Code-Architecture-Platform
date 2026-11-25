"""PG-ANALYTICS-001: bounded PostgreSQL server-cursor batches into Polars."""

import json
from collections.abc import Iterator
from datetime import UTC
from uuid import uuid4

import polars as pl
from psycopg.rows import dict_row

from .driver_contracts import owned_transaction
from .models import BatchSpec, Metric, QueryWindow
from .queries import SELECT_SQL, window_values

SCHEMA = pl.Schema(
    {
        "id": pl.Int64(),
        "status": pl.String(),
        "telemetry_json": pl.String(),
        "observed_at": pl.Datetime("us", "UTC"),
    }
)


def _frame(rows: list[dict]) -> pl.DataFrame:
    output = []
    for row in rows:
        metric = Metric.model_validate(row)
        output.append(
            {
                "id": metric.id,
                "status": metric.status,
                "telemetry_json": json.dumps(metric.telemetry, allow_nan=False, sort_keys=True),
                "observed_at": metric.observed_at.astimezone(UTC),
            }
        )
    return pl.DataFrame(output, schema=SCHEMA)


def metric_frames(conn, window: QueryWindow, batch_size: int = 1000) -> Iterator[pl.DataFrame]:
    """Own transaction+cursor until exhausted; use contextlib.closing on early exit.

    JSON is an explicit bounded string column, avoiding schema growth across keys.
    A named cursor bounds driver buffering; iter_batches alone would not prove this.
    """
    owned_transaction(conn)
    params = window_values(window)
    batch = BatchSpec(batch_size=batch_size, max_rows=params[2])
    with conn.transaction():
        with conn.cursor(name=f"metrics_{uuid4().hex}", row_factory=dict_row) as cursor:
            cursor.itersize = batch.batch_size
            cursor.execute(SELECT_SQL, params)
            page_count = (batch.max_rows + batch.batch_size - 1) // batch.batch_size
            for _ in range(page_count):
                rows = cursor.fetchmany(batch.batch_size)
                if not rows:
                    break
                yield _frame(rows)
