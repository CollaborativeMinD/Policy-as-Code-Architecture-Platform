"""PG-BULK-001: separate atomic COPY and pipeline modes, bounded validated input."""

from collections.abc import Iterable

from psycopg import sql

from .driver_contracts import owned_transaction
from .models import Metric
from .queries import INSERT_SQL, bounded_metrics, metric_values, qualified_table


def copy_metrics(conn, metrics: Iterable[Metric]) -> int:
    """Typed row COPY; no CSV flags. Any row error rolls back the complete batch."""
    owned_transaction(conn)
    rows = bounded_metrics(metrics)
    statement = sql.SQL("COPY {} (id,status,telemetry,observed_at) FROM STDIN").format(
        qualified_table("metrics")
    )
    with conn.transaction(), conn.cursor() as cursor, cursor.copy(statement) as copy:
        for metric in rows:
            copy.write_row(metric_values(metric))
    return len(rows)


def pipeline_metrics(conn, metrics: Iterable[Metric]) -> int:
    """Reduce round trips where suitable; this does not make operations parallel."""
    owned_transaction(conn)
    rows = bounded_metrics(metrics)
    with conn.transaction(), conn.pipeline() as pipeline:
        for metric in rows:
            conn.execute(INSERT_SQL, metric_values(metric))
        pipeline.sync()
    return len(rows)
