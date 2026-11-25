"""PG-PACE-001: distinct degraded contracts and hysteretic recovery."""

import pytest
from pydantic import ValidationError

from hmt_pg_patterns.pace import available_mode, step
from hmt_pg_patterns.pace_models import OPERATIONS, Mode, Observation, PacePolicy, PaceState


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


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({}, Mode.PRIMARY),
        ({"cache_ready": False}, Mode.ALTERNATE),
        ({"transport_ready": False}, Mode.CONTINGENCY),
        ({"database_ready": False}, Mode.EMERGENCY),
        ({"authority_valid": False}, Mode.TERMINAL),
        ({"epoch_current": False}, Mode.TERMINAL),
        ({"margin": 0.0}, Mode.TERMINAL),
    ],
)
def test_capability_contracts(changes, expected):
    assert available_mode(observation(**changes)) == expected
    state = step(PaceState(), observation(**changes))
    assert state.mode == expected
    assert ("write" in OPERATIONS[expected]) == (
        expected in {Mode.PRIMARY, Mode.ALTERNATE, Mode.CONTINGENCY}
    )


@pytest.mark.parametrize("guard", ["reconciled", "uncertain_ack", "margin"])
def test_causal_recovery_guard_deletion_restoration_controls(guard):
    initial = PaceState(mode=Mode.EMERGENCY)
    mutation = {"reconciled": False, "uncertain_ack": True, "margin": 0.1}
    blocked = initial
    matched = initial
    for tick in range(1, 5):
        blocked = step(blocked, observation(now=float(tick), **{guard: mutation[guard]}))
        matched = step(matched, observation(now=float(tick)))
    assert blocked.mode == Mode.EMERGENCY
    assert matched.mode == Mode.PRIMARY
    restored = blocked
    for tick in range(5, 30):
        restored = step(restored, observation(now=float(tick)))
    assert restored.mode == Mode.PRIMARY


def test_qualified_alternate_continues_without_redis():
    state = step(PaceState(), observation(cache_ready=False))
    assert state.mode == Mode.ALTERNATE
    assert "write" in OPERATIONS[state.mode]
    for tick in range(2, 6):
        state = step(state, observation(now=float(tick)))
    assert state.mode == Mode.PRIMARY


def test_temporal_boundaries_pressure_and_terminal_latch():
    state = step(PaceState(), observation(margin=0.1))
    assert state.pressure > 0
    with pytest.raises(ValueError, match="MONOTONIC"):
        step(state, observation(now=0.0))
    stale = step(state, observation(now=62.0))
    assert stale.mode == Mode.TERMINAL
    assert step(stale, observation(now=63.0)).mode == Mode.TERMINAL
    assert not OPERATIONS[Mode.TERMINAL]


def test_pace_rejects_nonfinite_and_invalid_policy():
    with pytest.raises(ValidationError):
        observation(margin=float("nan"))
    with pytest.raises(ValidationError):
        PacePolicy(recovery_samples=1)
