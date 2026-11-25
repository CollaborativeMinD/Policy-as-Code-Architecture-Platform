"""CDC limits, local capability guards, and durability prerequisites at the effect boundary."""

import pytest

from authority_samples import counts
from crossjoin_e2e_flow import PAYLOAD, prepare
from crossjoin_live_stream import ClosingSource
from crossjoin_unit_pace import observation
from crossjoin_unit_stream import chunk_policy
from hmt_pg_patterns.diagnostics import wal_settings
from hmt_pg_patterns.pace import perform, step
from hmt_pg_patterns.pace_models import Mode, PaceState
from hmt_pg_patterns.streaming_contracts import StreamError


def packet_invariance(live):
    flow = prepare(live)
    snapshot = flow.write([PAYLOAD[index : index + 11] for index in range(0, len(PAYLOAD), 11)])
    before = counts(live.conn)
    assert flow.write([PAYLOAD]) == snapshot and counts(live.conn) == before
    return flow.complete(snapshot, PAYLOAD)


def stream_limits(live):
    flow = prepare(live, chunk_policy(max_total_bytes=16))
    source = ClosingSource()
    with pytest.raises(StreamError, match="STREAM_CAPACITY"):
        flow.write(source)
    assert source.closed and counts(live.conn) == (0, 0, 0)
    return "bounded_end_to_end_failure_without_partial_effect"


def terminal_authority(live):
    flow = prepare(live)
    state = step(PaceState(), observation(margin=0.0))
    state = step(state, observation(now=2.0))
    with pytest.raises(PermissionError, match="PACE_OPERATION_DENIED:T:write"):
        perform(state, "write", lambda: flow.write([PAYLOAD]))
    assert counts(live.conn) == (0, 0, 0)
    assert flow.authority.identity().epoch == 1
    return flow.complete(flow.write([PAYLOAD]), PAYLOAD)


def guarded_recovery(live):
    flow = prepare(live)
    assert live.redis.ping() and live.conn.execute("SELECT 1").fetchone() == (1,)
    state = PaceState(mode=Mode.EMERGENCY)
    for tick in range(1, 5):
        state = step(state, observation(now=float(tick), reconciled=False, uncertain_ack=True))
    with pytest.raises(PermissionError, match="PACE_OPERATION_DENIED:E:write"):
        perform(state, "write", lambda: flow.write([PAYLOAD]))
    assert counts(live.conn) == (0, 0, 0)
    for tick in range(5, 9):
        state = step(state, observation(now=float(tick)))
    assert state.mode == Mode.PRIMARY
    snapshot = perform(state, "write", lambda: flow.write([PAYLOAD]))
    return flow.complete(snapshot, PAYLOAD)


def wal_prerequisites(live):
    flow = prepare(live)
    observed = wal_settings(live.conn)
    unsafe = observed.model_copy(update={"fsync": "off"})

    def commit_requiring_durability():
        unsafe.require_local_durable_commit()
        return flow.write([PAYLOAD])

    with pytest.raises(ValueError, match="WAL_PROTECTION_DISABLED"):
        commit_requiring_durability()
    assert counts(live.conn) == (0, 0, 0)
    return "unsafe_durable_commit_request_denied_without_storage_claim"
