"""Exact integer ordering, immutable values, and disposable Redis truth tests."""

import json
from uuid import uuid4

import pytest
from pyrsistent import PMap
from redis.exceptions import ConnectionError as RedisConnectionError

from hmt_pg_patterns.authority_types import BIGINT, CheckpointData
from hmt_pg_patterns.checkpoints import CheckpointCache
from hmt_pg_patterns.checkpoints_snapshot import encode_checkpoint, immutable_checkpoint


def snapshot(**changes):
    """Build an independent typed checkpoint with a distinct cache namespace."""
    values = dict(
        db_role="hmt_test_peer",
        stream_id=uuid4(),
        epoch=1,
        sequence=0,
        end=7,
        digest=b"a" * 32,
        policy_digest=b"p" * 32,
    )
    values.update(changes)
    return CheckpointData.model_validate(values)


def test_snapshot_is_persistent_and_encoding_is_exact():
    value = snapshot(epoch=BIGINT, sequence=BIGINT, end=BIGINT)
    frozen = immutable_checkpoint(value)
    assert isinstance(frozen, PMap)
    changed = frozen.set("sequence", 0)
    assert frozen["sequence"] == BIGINT and changed["sequence"] == 0
    encoded = json.loads(encode_checkpoint(frozen))
    assert encoded["epoch"] == encoded["sequence"] == encoded["end"] == str(BIGINT)
    assert encoded["digest"] == (b"a" * 32).hex()
    assert immutable_checkpoint(dict(frozen)) == frozen
    with pytest.raises(ValueError, match="CHECKPOINT_CAPACITY"):
        encode_checkpoint(snapshot(db_role="x" * 9000))


def test_redis_ordering_above_float_precision(redis_client):
    cache = CheckpointCache(redis_client)
    first = snapshot(epoch=2**53, sequence=2**53)
    assert cache.offer(first) == "APPLIED"
    assert cache.offer(first) == "IDENTICAL"
    later = first.model_copy(update={"sequence": 2**53 + 1})
    assert cache.offer(later) == "APPLIED"
    assert cache.offer(first) == "STALE"
    conflict = later.model_copy(update={"digest": b"z" * 32})
    assert cache.offer(conflict) == "CONFLICT"
    new_epoch = first.model_copy(update={"epoch": 2**53 + 1, "sequence": 0})
    assert cache.offer(new_epoch) == "APPLIED"
    assert cache.offer(later) == "STALE"
    assert cache.read(new_epoch) == immutable_checkpoint(new_epoch)
    assert cache.read(later) is None
    assert 0 < redis_client.ttl(cache._key(immutable_checkpoint(first))) <= 300


@pytest.mark.parametrize(
    "prior",
    [
        "broken-json",
        "[]",
        '{"epoch":2,"sequence":"0"}',
        '{"epoch":"01","sequence":"0"}',
        '{"epoch":"9223372036854775808","sequence":"0"}',
        "x" * 8193,
    ],
)
def test_poisoned_projection_never_becomes_authority(redis_client, prior):
    cache = CheckpointCache(redis_client)
    value = snapshot()
    redis_client.set(cache._key(immutable_checkpoint(value)), prior)
    assert cache.offer(value) == "INVALID"
    assert cache.read(value) is None


def test_foreign_scope_and_loss_are_rejected(redis_client):
    cache = CheckpointCache(redis_client)
    value = snapshot()
    key = cache._key(immutable_checkpoint(value))
    foreign = value.model_copy(update={"db_role": "other"})
    redis_client.set(key, encode_checkpoint(foreign))
    assert cache.offer(value) == "INVALID"
    assert cache.read(value) is None
    redis_client.delete(key)
    assert cache.read(value) is None
    assert cache.offer(value) == "APPLIED"


def test_unavailable_and_unknown_driver_outcomes_fail_closed():
    class Client:
        """Fault adapter returns no trusted observation."""

        def eval(self, *_args):
            raise RedisConnectionError("synthetic outage")

    cache = CheckpointCache(Client())
    assert cache.offer(snapshot()) == "UNAVAILABLE"
    assert cache.read(snapshot()) is None
    cache.client.eval = lambda *_args: "UNRECOGNIZED"
    assert cache.offer(snapshot()) == "INVALID"
