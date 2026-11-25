"""PG-SYNC-001: borrowed connections, bounded reads, explicit transaction retries."""

from collections.abc import Callable

import psycopg
from psycopg.rows import dict_row

from .driver_contracts import RETRYABLE_SQLSTATES, owned_transaction
from .models import Metric, QueryWindow
from .queries import INSERT_SQL, SELECT_SQL, metric_values, window_values


def fetch_metrics(conn: psycopg.Connection, window: QueryWindow) -> list[Metric]:
    """Keyset page over immutable unique IDs; separate pages are not a snapshot."""
    params = window_values(window)
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(SELECT_SQL, params)
        return [Metric.model_validate(row) for row in cursor.fetchall()]


def insert_metric(conn: psycopg.Connection, metric: Metric) -> None:
    """Caller controls the transaction; all values use PostgreSQL binding."""
    params = metric_values(metric)
    conn.execute(INSERT_SQL, params)


def transaction_retry[T](
    conn: psycopg.Connection, operation: Callable[[psycopg.Connection], T], attempts: int = 3
) -> T:
    """Retry the entire DB-only operation on serialization/deadlock rejection.

    Connection loss or uncertain commit is never retried. The callback must not
    perform external effects and must not commit, rollback, or change autocommit.
    """
    owned_transaction(conn, attempts)
    for _ in range(attempts - 1):
        try:
            return _transaction_once(conn, operation)
        except psycopg.Error as error:
            if error.sqlstate not in RETRYABLE_SQLSTATES:
                raise
    return _transaction_once(conn, operation)


def _transaction_once[T](
    conn: psycopg.Connection, operation: Callable[[psycopg.Connection], T]
) -> T:
    with conn.transaction():
        return operation(conn)
