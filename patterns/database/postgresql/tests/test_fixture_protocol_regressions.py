"""PG-FIXTURE-001: real COPY input and prepared plans survive separate clients."""

import psycopg
import pytest

pytestmark = pytest.mark.integration
COPY_SQL = "COPY hmt_pg.metrics (id,status,telemetry,observed_at) FROM STDIN"
ROW = '{}\tactive\t{{"temperature":42.25}}\t2026-01-02 03:04:00+00\n'


def test_two_open_clients_keep_their_prepared_plans(pg_dsn):
    with psycopg.connect(pg_dsn, autocommit=True) as first:
        with psycopg.connect(pg_dsn, autocommit=True) as second:
            assert first.execute("SELECT %s::integer + 100", (1,), prepare=True).fetchone() == (
                101,
            )
            assert second.execute("SELECT %s::integer + 200", (2,), prepare=True).fetchone() == (
                202,
            )
            assert first.execute("SELECT %s::integer + 100", (3,), prepare=True).fetchone() == (
                103,
            )
        assert first.execute("SELECT %s::integer + 100", (4,), prepare=True).fetchone() == (104,)
    with psycopg.connect(pg_dsn, autocommit=True) as fresh:
        assert fresh.execute("SELECT %s::integer + 300", (5,), prepare=True).fetchone() == (305,)


def test_copy_consumes_multiple_protocol_data_frames(pg_conn):
    with pg_conn.transaction(), pg_conn.cursor() as cursor, cursor.copy(COPY_SQL) as stream:
        for start in (1, 1001, 2001):
            stream.write("".join(ROW.format(item) for item in range(start, start + 1000)))
    assert pg_conn.execute("SELECT count(*) FROM hmt_pg.metrics").fetchone() == (3000,)


def test_copy_fail_message_rolls_back_and_connection_recovers(pg_conn):
    with pytest.raises(RuntimeError, match="producer failed"):
        with pg_conn.transaction(), pg_conn.cursor() as cursor, cursor.copy(COPY_SQL) as stream:
            stream.write(ROW.format(1))
            raise RuntimeError("producer failed")
    assert pg_conn.execute("SELECT count(*) FROM hmt_pg.metrics").fetchone() == (0,)
    assert pg_conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
