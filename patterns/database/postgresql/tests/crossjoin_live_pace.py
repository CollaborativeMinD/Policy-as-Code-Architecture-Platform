"""Local capability guard plus independently checked database epoch authority."""

import pytest

from authority_samples import counts, register, request
from crossjoin_unit_pace import observation
from hmt_pg_patterns.pace import perform, step
from hmt_pg_patterns.pace_models import Mode, PaceState


def terminal_authority(live):
    authority = register(live.conn)
    state = step(PaceState(), observation(margin=0.0))
    state = step(state, observation(now=2.0))
    assert state.mode == Mode.TERMINAL
    assert authority.identity().epoch == 1
    with pytest.raises(PermissionError, match="PACE_OPERATION_DENIED:T:write"):
        perform(state, "write", lambda: authority.admit(request()))
    assert counts(live.conn) == (0, 0, 0)
    perform(PaceState(), "write", lambda: authority.admit(request()))
    assert counts(live.conn) == (1, 1, 1)
    return "local_terminal_guard_blocked_an_otherwise_valid_database_grant"


def guarded_recovery(live):
    authority = register(live.conn)
    ready = bool(live.conn.execute("SELECT 1").fetchone()) and live.redis.ping()
    assert ready
    state = PaceState(mode=Mode.EMERGENCY)
    for tick in range(1, 5):
        state = step(state, observation(now=float(tick), reconciled=False, uncertain_ack=True))
    with pytest.raises(PermissionError, match="PACE_OPERATION_DENIED:E:write"):
        perform(state, "write", lambda: authority.admit(request()))
    assert counts(live.conn) == (0, 0, 0)
    for tick in range(5, 9):
        state = step(state, observation(now=float(tick)))
    assert state.mode == Mode.PRIMARY
    perform(state, "write", lambda: authority.admit(request()))
    assert counts(live.conn) == (1, 1, 1)
    return "reconciled_dwell_and_samples_restored_local_capability"
