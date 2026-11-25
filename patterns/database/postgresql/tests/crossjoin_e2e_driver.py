"""Driver failure mechanisms composed with committed reads and complete delivery."""

import asyncio
from contextlib import closing
import warnings
import psycopg
from pydantic import ValidationError
import pytest

from authority_samples import counts
from crossjoin_e2e_flow import PAYLOAD, prepare
from driver_samples import sample
from hmt_pg_patterns import asyncpg_driver
from hmt_pg_patterns.analytics import metric_frames
from hmt_pg_patterns.bulk import copy_metrics
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.queries import qualified_table
from hmt_pg_patterns.sync_driver import fetch_metrics, transaction_retry


def tls_profile(live):
    flow = prepare(live)
    changes = live.config.model_dump() | {"profile": "production", "user": "runtime"}
    with pytest.raises(ValidationError, match="PRODUCTION_REQUIRES_TLS"):
        DbConfig.model_validate(changes)
    assert counts(live.conn) == (0, 0, 0)
    return flow.complete(flow.write([PAYLOAD]), PAYLOAD)


def bound_values(live):
    flow = prepare(live)
    payload = b"'; DROP TABLE hmt_pg.chunk_effect; --\x00\xff"
    with pytest.raises(ValueError, match="TABLE_NOT_ADMITTED"):
        qualified_table(payload.decode("latin1"))
    return flow.complete(flow.write([payload]), payload)


def rollback(live):
    flow = prepare(live)
    with pytest.raises(RuntimeError, match="rollback_after_fenced_write"):
        with live.conn.transaction():
            flow.write([PAYLOAD])
            assert counts(live.conn)[0] > 0
            raise RuntimeError("rollback_after_fenced_write")
    assert counts(live.conn) == (0, 0, 0)
    return flow.complete(flow.write([PAYLOAD]), PAYLOAD)


def retry_budget(live):
    flow = prepare(live)
    attempts = []

    def rejected(connection):
        attempts.append(len(attempts))
        flow.write([PAYLOAD])
        connection.execute("DO $$ BEGIN RAISE EXCEPTION USING ERRCODE='40001'; END $$")

    with pytest.raises(psycopg.errors.SerializationFailure):
        transaction_retry(live.conn, rejected, attempts=3)
    assert attempts == [0, 1, 2] and counts(live.conn) == (0, 0, 0)
    return flow.complete(flow.write([PAYLOAD]), PAYLOAD)


async def committed_then_closed(config):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        async with asyncpg_driver.connection(config, timeout=0.05) as connection:
            async with connection.transaction():
                await asyncpg_driver.insert_metric(connection, sample())
        assert connection.is_closed()


def bounded_close(live):
    asyncio.run(committed_then_closed(live.config))
    assert fetch_metrics(live.conn, QueryWindow()) == [sample()]
    return "committed_data_survived_classified_close"


def contract_rejection(live):
    invalid = sample(2).model_copy(update={"telemetry": {"bad-key": 1.0}})
    with pytest.raises(ValidationError, match="TELEMETRY_KEY_INVALID"):
        copy_metrics(live.conn, [sample(), invalid])
    assert fetch_metrics(live.conn, QueryWindow()) == []
    assert copy_metrics(live.conn, [sample(), sample(2)]) == 2
    with closing(metric_frames(live.conn, QueryWindow(limit=2), 1)) as frames:
        assert [frame["id"].to_list() for frame in frames] == [[1], [2]]
    return "strict_dto_copy_cursor_polars_contract"
