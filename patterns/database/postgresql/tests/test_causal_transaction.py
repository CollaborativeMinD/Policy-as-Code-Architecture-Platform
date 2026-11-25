"""PG-TX-001: caller batch atomicity and independent SQL statement atomicity."""

import psycopg
import pytest
from psycopg.types.json import Jsonb

from authority_samples import counts, register, request
from causal_samples import fail_outbox_insert

pytestmark = pytest.mark.causal


def test_deletion(pg_conn):
    """Removing the caller's batch transaction leaves an admitted prefix committed."""
    authority = register(pg_conn)
    first = request()
    receipt = authority.admit(first)
    bad = request(
        stream_id=first.stream_id, sequence=1, start=receipt.end + 1, previous_digest=receipt.digest
    )
    with pytest.raises(psycopg.Error, match="CHECKPOINT_CONFLICT"):
        authority.admit(bad)
    assert counts(pg_conn) == (1, 1, 1)
    assert authority.checkpoint(first.stream_id).digest == receipt.digest


def test_restoration(pg_conn):
    authority = register(pg_conn)
    first = request()
    with pytest.raises(psycopg.Error, match="CHECKPOINT_CONFLICT"):
        with pg_conn.transaction():
            receipt = authority.admit(first)
            authority.admit(
                request(
                    stream_id=first.stream_id,
                    sequence=1,
                    start=receipt.end + 1,
                    previous_digest=receipt.digest,
                )
            )
    assert counts(pg_conn) == (0, 0, 0)


def test_matched_control(pg_conn):
    authority = register(pg_conn)
    first = request()
    with pg_conn.transaction():
        receipt = authority.admit(first)
        authority.admit(
            request(
                stream_id=first.stream_id,
                sequence=1,
                start=receipt.end,
                previous_digest=receipt.digest,
            )
        )
    assert counts(pg_conn) == (2, 1, 2)
    assert authority.checkpoint(first.stream_id).sequence == 1


def test_alternate_path(pg_conn):
    """A single SQL admission remains atomic without a Python transaction wrapper."""
    register(pg_conn)
    first = request()
    with fail_outbox_insert(pg_conn):
        with pytest.raises(psycopg.Error, match="CAUSAL_OUTBOX_FAULT"):
            pg_conn.execute(
                "SELECT * FROM hmt_pg.admit_chunk(%s,%s)", (Jsonb(first.header()), first.data)
            ).fetchone()
    assert counts(pg_conn) == (0, 0, 0)
