"""PG-SYNC-001 / PG-TX-001: real SQL, parameter isolation, and rollback witnesses."""

import psycopg
import pytest
from driver_samples import sample

from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.sync_driver import fetch_metrics, insert_metric, transaction_retry

pytestmark = pytest.mark.integration


def test_keyset_page_is_bounded_and_deterministic(pg_conn):
    for identifier in range(1, 6):
        insert_metric(pg_conn, sample(identifier))
    insert_metric(pg_conn, sample(6, "inactive"))
    first = fetch_metrics(pg_conn, QueryWindow(limit=2))
    second = fetch_metrics(pg_conn, QueryWindow(after_id=first[-1].id, limit=2))
    assert [row.id for row in first + second] == [1, 2, 3, 4]
    assert fetch_metrics(pg_conn, QueryWindow(after_id=6)) == []
    assert fetch_metrics(pg_conn, QueryWindow(status="inactive"))[0].id == 6


def test_exception_rolls_back_complete_transaction(pg_conn):
    with pytest.raises(RuntimeError, match="rollback"):
        with pg_conn.transaction():
            insert_metric(pg_conn, sample())
            raise RuntimeError("rollback")
    assert fetch_metrics(pg_conn, QueryWindow()) == []


@pytest.mark.parametrize("code", ["40001", "40P01"])
def test_retry_reexecutes_whole_transaction_only_on_admitted_sqlstate(pg_conn, code):
    attempts = []

    def operation(conn):
        attempts.append(len(attempts))
        insert_metric(conn, sample())
        if len(attempts) < 3:
            conn.execute(
                "DO $$ BEGIN RAISE EXCEPTION 'retry witness' USING ERRCODE='" + code + "'; END $$"
            )
        return "committed"

    assert transaction_retry(pg_conn, operation) == "committed"
    assert len(attempts) == 3
    assert len(fetch_metrics(pg_conn, QueryWindow())) == 1


def test_retry_exhaustion_rolls_back(pg_conn):
    def operation(conn):
        insert_metric(conn, sample())
        conn.execute("DO $$ BEGIN RAISE EXCEPTION 'retry witness' USING ERRCODE='40001'; END $$")

    with pytest.raises(psycopg.errors.SerializationFailure):
        transaction_retry(pg_conn, operation, attempts=2)
    assert fetch_metrics(pg_conn, QueryWindow()) == []


def test_uniqueness_and_uncertain_transport_never_retry(pg_conn):
    insert_metric(pg_conn, sample())
    calls = []

    def conflict(conn):
        calls.append(1)
        insert_metric(conn, sample())

    with pytest.raises(psycopg.errors.UniqueViolation):
        transaction_retry(pg_conn, conflict)
    assert len(calls) == 1

    def transport(conn):
        calls.append(1)
        raise psycopg.OperationalError("synthetic uncertain transport")

    with pytest.raises(psycopg.OperationalError):
        transaction_retry(pg_conn, transport)
    assert len(calls) == 2


def test_savepoint_cannot_substitute_for_retry_owner(pg_conn):
    with pg_conn.transaction(), pytest.raises(ValueError, match="IDLE_AUTOCOMMIT"):
        transaction_retry(pg_conn, lambda _: None)
    pg_conn.autocommit = False
    with pytest.raises(ValueError, match="IDLE_AUTOCOMMIT"):
        transaction_retry(pg_conn, lambda _: None)
