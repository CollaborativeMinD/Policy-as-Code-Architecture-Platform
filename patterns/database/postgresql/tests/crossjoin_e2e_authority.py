"""Full reference delivery under mutation, stale authority, replay, and reordering."""

import psycopg
import pytest

from authority_samples import counts
from crossjoin_e2e_flow import PAYLOAD, prepare
from crossjoin_live_authority import UnavailableCache
from hmt_pg_patterns.checkpoints import CheckpointCache
from hmt_pg_patterns.outbox import rebuild_checkpoint, recover, relay_checkpoint


def immutable_snapshot(live):
    flow = prepare(live)
    caller = bytearray(PAYLOAD)
    snapshot = flow.write([caller])
    caller[:] = b"corrupted after consumption"
    changed = snapshot.set("end", snapshot["end"] + 1)
    assert changed["end"] != snapshot["end"]
    with pytest.raises(TypeError):
        snapshot["end"] = 0
    return flow.complete(snapshot, PAYLOAD)


def epoch_fence(live):
    flow = prepare(live)
    snapshot = flow.write([PAYLOAD])
    cache = CheckpointCache(live.redis)
    assert cache.offer(snapshot) == "APPLIED"
    before = counts(live.conn)
    live.conn.execute("UPDATE hmt_pg.peer_authority SET epoch=2")
    assert cache.read(flow.authority.checkpoint(flow.stream_id)) == snapshot
    with pytest.raises(psycopg.Error, match="AUTHORITY_DENIED"):
        flow.write([PAYLOAD])
    assert counts(live.conn) == before
    return "cached_checkpoint_did_not_restore_revoked_epoch"


def outbox_replay(live):
    flow = prepare(live)
    payload = b"one"
    snapshot = flow.write([payload])
    assert relay_checkpoint(live.conn, UnavailableCache()) == "UNKNOWN"
    pending = recover(live.conn)
    assert len(pending) == 1 and counts(live.conn) == (1, 1, 1)
    assert rebuild_checkpoint(live.conn, CheckpointCache(live.redis), pending[0]) == "ACKED"
    assert flow.write([payload]) == snapshot
    assert counts(live.conn) == (1, 1, 1)
    return flow.complete(snapshot, payload)


def checkpoint_order(live):
    flow = prepare(live)
    snapshot = flow.write([PAYLOAD])
    assert CheckpointCache(live.redis).offer(snapshot) == "APPLIED"
    before = counts(live.conn)
    # Older outbox rows arrive after the newest projection; they may only acknowledge it.
    result = flow.complete(snapshot, PAYLOAD)
    replay = flow.write([PAYLOAD[index : index + 3] for index in range(0, len(PAYLOAD), 3)])
    assert replay == snapshot and counts(live.conn) == before
    return result
