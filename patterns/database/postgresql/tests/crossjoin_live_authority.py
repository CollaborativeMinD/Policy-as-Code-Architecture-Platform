"""Live atomic effects, immutable snapshots, outbox recovery, and Redis ordering."""

from dataclasses import dataclass
import psycopg
import pytest

from authority_samples import counts, register, request
from hmt_pg_patterns.checkpoints import CheckpointCache
from hmt_pg_patterns.checkpoints_snapshot import immutable_checkpoint
from hmt_pg_patterns.outbox import rebuild_checkpoint, recover, relay_checkpoint


@dataclass(frozen=True)
class Live:
    conn: object
    config: object
    redis: object


class UnavailableCache:
    def offer(self, value):
        return "UNAVAILABLE"

    def read(self, value):
        return None


def immutable_snapshot(live):
    authority = register(live.conn)
    value = request()
    authority.admit(value)
    current = authority.checkpoint(value.stream_id)
    caller = current.model_dump()
    snapshot = immutable_checkpoint(caller)
    caller["end"] += 100
    assert snapshot["end"] == current.end
    cache = CheckpointCache(live.redis)
    assert cache.offer(snapshot) == "APPLIED"
    assert cache.read(authority.checkpoint(value.stream_id)) == snapshot
    return "detached_and_database_bound"


def epoch_fence(live):
    authority = register(live.conn)
    old = request()
    live.conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2")
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        authority.admit(old)
    assert counts(live.conn) == (0, 0, 0)
    fresh = request(epoch=2)
    assert not authority.admit(fresh).replayed
    assert counts(live.conn) == (1, 1, 1)
    return "epoch_drift_denied_and_fresh_control_passed"


def outbox_replay(live):
    authority = register(live.conn)
    value = request()
    authority.admit(value)
    assert relay_checkpoint(live.conn, UnavailableCache()) == "UNKNOWN"
    events = recover(live.conn)
    assert len(events) == 1 and counts(live.conn) == (1, 1, 1)
    cache = CheckpointCache(live.redis)
    assert rebuild_checkpoint(live.conn, cache, events[0]) == "ACKED"
    assert authority.admit(value).replayed
    assert counts(live.conn) == (1, 1, 1)
    assert not recover(live.conn)
    assert cache.read(authority.checkpoint(value.stream_id)) is not None
    return "unknown_projection_rebuilt_without_repeating_effect"


def checkpoint_order(live):
    authority = register(live.conn)
    first = request()
    accepted = authority.admit(first)
    earlier = authority.checkpoint(first.stream_id)
    second = request(
        b"next",
        stream_id=first.stream_id,
        sequence=1,
        start=accepted.end,
        previous_digest=accepted.digest,
    )
    authority.admit(second)
    current = authority.checkpoint(first.stream_id)
    cache = CheckpointCache(live.redis)
    assert cache.offer(current) == "APPLIED"
    assert cache.offer(earlier) == "STALE"
    assert cache.read(current) is not None and cache.read(earlier) is None
    assert authority.admit(first).replayed
    assert authority.checkpoint(first.stream_id) == current
    return "durable_head_did_not_regress"
