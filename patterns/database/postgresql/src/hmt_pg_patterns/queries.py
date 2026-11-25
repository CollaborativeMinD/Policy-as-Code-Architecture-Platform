"""PG-QUERY-001: schema-qualified SQL, values bound, identifiers allowlisted."""

from collections.abc import Iterable
from itertools import islice

from psycopg import sql
from psycopg.types.json import Jsonb

from .models import Metric, QueryWindow

SELECT_SQL = (
    "SELECT id,status,telemetry,observed_at FROM hmt_pg.metrics "
    "WHERE status=%s AND id>%s ORDER BY id LIMIT %s"
)
INSERT_SQL = "INSERT INTO hmt_pg.metrics(id,status,telemetry,observed_at) VALUES (%s,%s,%s,%s)"
ASYNCPG_SELECT = (
    "SELECT id,status,telemetry,observed_at FROM hmt_pg.metrics "
    "WHERE status=$1 AND id>$2 ORDER BY id LIMIT $3"
)
ASYNCPG_INSERT = (
    "INSERT INTO hmt_pg.metrics(id,status,telemetry,observed_at) VALUES ($1,$2,$3::jsonb,$4)"
)


def qualified_table(name: str) -> sql.Identifier:
    """Resolve an admitted table; column/table names are never value parameters."""
    if name != "metrics":
        raise ValueError("TABLE_NOT_ADMITTED")
    return sql.Identifier("hmt_pg", name)


def snapshot_metric(metric: Metric) -> Metric:
    """Revalidate constructed models and copy nested telemetry before any I/O."""
    return Metric.model_validate(dict(metric))


def metric_values(metric: Metric) -> tuple:
    """Detach and adapt the validated values in their explicit column order."""
    item = snapshot_metric(metric)
    return item.id, item.status, Jsonb(item.telemetry), item.observed_at


def window_values(window: QueryWindow) -> tuple[str, int, int]:
    """Revalidate the bounded page contract before creating query parameters."""
    item = QueryWindow.model_validate(dict(window))
    return item.status, item.after_id, item.limit


def bounded_metrics(metrics: Iterable[Metric]) -> list[Metric]:
    """Bound even an infinite iterable; every DTO is validated before DB effects."""
    result: list[Metric] = []
    for item in islice(metrics, 10001):
        if len(result) == 10000:
            raise ValueError("BATCH_ROW_LIMIT")
        result.append(snapshot_metric(item))
    return result
