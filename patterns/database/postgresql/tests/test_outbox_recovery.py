"""Crash-before-send, acknowledgement loss, cache loss, and epoch boundaries."""

from uuid import uuid4

import psycopg
import pytest

from authority_samples import register, request
from hmt_pg_patterns.checkpoints import CheckpointCache
from hmt_pg_patterns.checkpoints_snapshot import immutable_checkpoint
from hmt_pg_patterns.outbox import (
    claim,
    finish,
    rebuild_checkpoint,
    reconcile,
    recover,
    relay_checkpoint,
)


def test_crash_before_first_send_is_explicitly_rebuildable(pg_conn, redis_client):
    authority = register(pg_conn)
    authority.admit(request())
    cache = CheckpointCache(redis_client)
    event = claim(pg_conn)
    assert event is not None and recover(pg_conn) == [event]
    assert cache.read(event.checkpoint) is None
    assert reconcile(pg_conn, cache, event) == "UNKNOWN"
    assert recover(pg_conn) == [event]
    assert rebuild_checkpoint(pg_conn, cache, event) == "ACKED"
    assert recover(pg_conn) == []
    assert cache.read(event.checkpoint) is not None
    assert relay_checkpoint(pg_conn, cache) is None


def test_send_then_lost_ack_records_observation_after_revocation(pg_conn, redis_client):
    authority = register(pg_conn)
    authority.admit(request())
    cache = CheckpointCache(redis_client)
    event = claim(pg_conn)
    assert cache.offer(event.checkpoint) == "APPLIED"
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2, active=false")
    assert reconcile(pg_conn, cache, event) == "ACKED"
    assert recover(pg_conn) == []


def test_cache_loss_rebuild_requires_current_same_epoch_authority(pg_conn, redis_client):
    authority = register(pg_conn)
    authority.admit(request())
    cache = CheckpointCache(redis_client)
    event = claim(pg_conn)
    assert cache.offer(event.checkpoint) == "APPLIED"
    redis_client.delete(cache._key(immutable_checkpoint(event.checkpoint)))
    assert rebuild_checkpoint(pg_conn, cache, event) == "ACKED"
    authority.admit(request())
    next_event = claim(pg_conn)
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2, active=false")
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        rebuild_checkpoint(pg_conn, cache, next_event)
    assert cache.read(next_event.checkpoint) is None
    assert recover(pg_conn) == [next_event]
    pg_conn.execute("UPDATE hmt_pg.peer_authority SET epoch=3, active=true")
    with pytest.raises(ValueError, match="CHECKPOINT_EPOCH_REVOKED"):
        rebuild_checkpoint(pg_conn, cache, next_event)
    assert cache.read(next_event.checkpoint) is None


def test_normal_relay_and_forged_claim_scope(pg_conn, redis_client):
    authority = register(pg_conn)
    authority.admit(request())
    cache = CheckpointCache(redis_client)
    assert relay_checkpoint(pg_conn, cache) == "ACKED"
    authority.admit(request())
    event = claim(pg_conn)
    forged = event.model_copy(
        update={
            "checkpoint": event.checkpoint.model_copy(
                update={"stream_id": uuid4(), "db_role": "attacker"}
            )
        }
    )
    assert rebuild_checkpoint(pg_conn, cache, forged) == "ACKED"
    assert cache.read(event.checkpoint) is not None
    assert cache.read(forged.checkpoint) is None
    with pytest.raises(ValueError, match="OUTBOX_CLAIM_CONFLICT"):
        reconcile(pg_conn, cache, event)


def test_unavailable_send_and_readback_remain_unknown(pg_conn):
    authority = register(pg_conn)
    authority.admit(request())

    class Unavailable:
        """Return a classified outage without creating a fabricated receipt."""

        def offer(self, _snapshot):
            return "UNAVAILABLE"

        def read(self, _snapshot):
            return None

    assert relay_checkpoint(pg_conn, Unavailable()) == "UNKNOWN"
    assert len(recover(pg_conn)) == 1


def test_claim_token_state_and_transaction_guards(pg_conn):
    authority = register(pg_conn)
    assert claim(pg_conn) is None
    authority.admit(request())
    event = claim(pg_conn)
    bad = event.model_copy(update={"claim_id": uuid4()})
    with pytest.raises(ValueError, match="OUTBOX_CLAIM_CONFLICT"):
        finish(pg_conn, bad, "ACKED")
    with pytest.raises(psycopg.Error, match="INVALID_OUTCOME"):
        finish(pg_conn, event, "PENDING")
    for invalid in (True, 0, 101, "1"):
        with pytest.raises(ValueError, match="INVALID_RECOVERY_LIMIT"):
            recover(pg_conn, invalid)
    with pg_conn.transaction():
        with pytest.raises(ValueError, match="OUTBOX_REQUIRES_IDLE_AUTOCOMMIT"):
            claim(pg_conn)
