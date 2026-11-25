"""PACE observations never substitute for database grants or local execution guards."""

import pytest

from hmt_pg_patterns.pace import perform, step
from hmt_pg_patterns.pace_models import Mode, Observation, PaceState


def observation(**changes):
    values = dict(
        now=1.0,
        margin=0.8,
        database_ready=True,
        cache_ready=True,
        transport_ready=True,
        authority_valid=True,
        epoch_current=True,
        reconciled=True,
        uncertain_ack=False,
    )
    values.update(changes)
    return Observation(**values)


def terminal_authority():
    state = step(PaceState(), observation(authority_valid=False))
    state = step(state, observation(now=2.0))
    assert state.mode == Mode.TERMINAL
    calls = []
    with pytest.raises(PermissionError) as denied:
        perform(state, "write", lambda: calls.append("forbidden"))
    assert not calls
    return str(denied.value)


def guarded_recovery():
    state = PaceState(mode=Mode.EMERGENCY)
    for tick in range(1, 5):
        state = step(state, observation(now=float(tick), reconciled=False, uncertain_ack=True))
    assert state.mode == Mode.EMERGENCY
    calls = []
    with pytest.raises(PermissionError) as denied:
        perform(state, "write", lambda: calls.append("forbidden"))
    assert not calls
    for tick in range(5, 9):
        state = step(state, observation(now=float(tick)))
    assert state.mode == Mode.PRIMARY
    perform(state, "write", lambda: calls.append("admitted"))
    assert calls == ["admitted"]
    return str(denied.value)
