"""PG-CHECKPOINT-001: projection availability never supplies effect authority."""

import pytest

from authority_samples import counts, register, request
from hmt_pg_patterns.checkpoints import CheckpointCache
from hmt_pg_patterns.checkpoints_snapshot import immutable_checkpoint
from hmt_pg_patterns.outbox import claim, rebuild_checkpoint
from hmt_pg_patterns.pace import perform, step
from hmt_pg_patterns.pace_models import Mode, PaceState
from test_pace import observation

pytestmark = pytest.mark.causal


def test_deletion(pg_conn, redis_client):
    authority = register(pg_conn)
    first = request()
    effect = authority.admit(first)
    point = authority.checkpoint(first.stream_id)
    cache = CheckpointCache(redis_client)
    assert cache.offer(point) == "APPLIED"
    redis_client.delete(cache._key(immutable_checkpoint(point)))
    assert cache.read(point) is None
    next_request = request(
        stream_id=first.stream_id, sequence=1, start=effect.end, previous_digest=effect.digest
    )
    assert authority.admit(next_request).sequence == 1
    assert counts(pg_conn) == (2, 1, 2)


def test_restoration(pg_conn, redis_client):
    authority = register(pg_conn)
    first = request()
    authority.admit(first)
    cache = CheckpointCache(redis_client)
    event = claim(pg_conn)
    assert cache.read(event.checkpoint) is None
    before = counts(pg_conn)
    assert rebuild_checkpoint(pg_conn, cache, event) == "ACKED"
    assert cache.read(authority.checkpoint(first.stream_id)) is not None
    assert counts(pg_conn) == before == (1, 1, 1)


def test_matched_control(pg_conn, redis_client):
    authority = register(pg_conn)
    first = request()
    authority.admit(first)
    point = authority.checkpoint(first.stream_id)
    cache = CheckpointCache(redis_client)
    assert cache.offer(point) == "APPLIED"
    foreign = point.model_copy(update={"stream_id": request().stream_id})
    redis_client.set(cache._key(immutable_checkpoint(foreign)), "unrelated fault")
    assert cache.read(point) == immutable_checkpoint(point)
    assert counts(pg_conn) == (1, 1, 1)


def test_alternate_path(pg_conn, redis_client):
    authority = register(pg_conn)
    state = step(PaceState(), observation(cache_ready=False))
    assert state.mode == Mode.ALTERNATE
    first = request()
    effect = perform(state, "write", lambda: authority.admit(first))
    point = authority.checkpoint(first.stream_id)
    assert CheckpointCache(redis_client).read(point) is None
    assert point.digest == effect.digest and point.end == len(first.data)
