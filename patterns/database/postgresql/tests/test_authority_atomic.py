"""PG-AUTH: transaction, chain, replay, and independent digest checks."""

import hashlib
import struct
from uuid import uuid4

import psycopg
import pytest

from authority_samples import counts, register, request


def test_atomic_digest_replay_and_exact_bytes(pg_conn):
    authority = register(pg_conn)
    value = request(b"\x00\xffcanonical bytes")
    result = authority.admit(value)
    role = authority.identity().db_role.encode()
    preimage = b"hmt-pg-chunk-v1" + struct.pack(">i", len(role)) + role + value.stream_id.bytes
    preimage += struct.pack(">qqq", value.epoch, value.sequence, value.start)
    preimage += value.policy_digest + value.previous_digest + value.data
    assert result.digest == hashlib.sha256(preimage).digest()
    assert not result.replayed and result.end == len(value.data)
    assert authority.admit(value).replayed
    assert counts(pg_conn) == (1, 1, 1)
    assert authority.checkpoint(value.stream_id).digest == result.digest
    assert authority.checkpoint(uuid4()) is None


def test_outer_rollback_removes_effect_head_and_intent(pg_conn):
    authority = register(pg_conn)
    with pytest.raises(RuntimeError, match="rollback"):
        with pg_conn.transaction():
            authority.admit(request())
            assert counts(pg_conn) == (1, 1, 1)
            raise RuntimeError("rollback")
    assert counts(pg_conn) == (0, 0, 0)


@pytest.mark.parametrize(
    "field,value",
    [
        ("data", b"other"),
        ("policy_digest", b"x" * 32),
        ("previous_digest", b"y" * 32),
        ("start", 1),
    ],
)
def test_idempotency_conflict_keeps_single_effect(pg_conn, field, value):
    authority = register(pg_conn)
    original = request()
    authority.admit(original)
    with pytest.raises(psycopg.Error, match="IDEMPOTENCY_CONFLICT"):
        authority.admit(original.model_copy(update={field: value}))
    assert counts(pg_conn) == (1, 1, 1)


@pytest.mark.parametrize("change", [{"sequence": 1}, {"start": 1}, {"previous_digest": b"x" * 32}])
def test_chain_rejects_gap_or_forgery_before_any_effect(pg_conn, change):
    authority = register(pg_conn)
    with pytest.raises(psycopg.Error, match="CHECKPOINT_CONFLICT"):
        authority.admit(request(**change))
    assert counts(pg_conn) == (0, 0, 0)


def test_contiguous_append_and_immutable_history(pg_conn):
    authority = register(pg_conn)
    first = request()
    previous = authority.admit(first)
    second = request(
        b"next",
        stream_id=first.stream_id,
        sequence=1,
        start=previous.end,
        previous_digest=previous.digest,
    )
    assert authority.admit(second).end == previous.end + 4
    for statement in (
        "UPDATE hmt_pg.chunk_effect SET payload='oops'",
        "DELETE FROM hmt_pg.chunk_effect",
    ):
        with pytest.raises(psycopg.Error, match="IMMUTABLE_EFFECT"):
            pg_conn.execute(statement)
    assert counts(pg_conn) == (2, 1, 2)
