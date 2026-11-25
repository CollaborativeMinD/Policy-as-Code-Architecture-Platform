"""PG-PACE-001: degradation preserves declared capability; recovery is guarded."""

from collections.abc import Callable
from typing import TypeVar

from .pace_models import OPERATIONS, Mode, Observation, PacePolicy, PaceState

T = TypeVar("T")

RANK = {mode: index for index, mode in enumerate(Mode)}


def available_mode(obs: Observation) -> Mode:
    """Select the capability supported by the current bounded observation."""
    if not obs.authority_valid or not obs.epoch_current or obs.margin <= 0:
        return Mode.TERMINAL
    if not obs.database_ready:
        return Mode.EMERGENCY
    if not obs.transport_ready:
        return Mode.CONTINGENCY
    if not obs.cache_ready:
        return Mode.ALTERNATE
    return Mode.PRIMARY


def recovery_state(old: PaceState, obs: Observation, policy: PacePolicy, pressure: float):
    """Require reconciliation, pressure margin, samples, and dwell for recovery."""
    ready = (
        obs.reconciled
        and not obs.uncertain_ack
        and obs.epoch_current
        and obs.margin >= policy.recovery_margin
        and pressure <= policy.pressure_limit
    )
    count = min(old.healthy_samples + 1, policy.recovery_samples) if ready else 0
    since = old.healthy_since if ready and old.healthy_since is not None else obs.now
    admitted = count >= policy.recovery_samples and obs.now - since >= policy.dwell_seconds
    return count, since if ready else None, admitted


def step(old: PaceState, obs: Observation, policy: PacePolicy = PacePolicy()) -> PaceState:
    """Advance an immutable state; Terminal can only be reset by a new lifecycle."""
    old = PaceState.model_validate(old.model_dump())
    obs = Observation.model_validate(obs.model_dump())
    policy = PacePolicy.model_validate(policy.model_dump())
    if obs.now < old.last_at:
        raise ValueError("MONOTONIC_CLOCK_REGRESSION")
    elapsed = obs.now - old.last_at
    target = available_mode(obs)
    if old.mode == Mode.TERMINAL or elapsed > policy.max_sample_gap:
        target = Mode.TERMINAL
    pressure = old.pressure * policy.pressure_decay**elapsed
    pressure += max(0.0, policy.recovery_margin - obs.margin) * elapsed
    count, since, recover = recovery_state(old, obs, policy, pressure)
    recovering = RANK[target] < RANK[old.mode]
    mode = old.mode if recovering and not recover else target
    reason = "RECOVERY_PENDING" if recovering and not recover else "CAPABILITY_EVALUATED"
    if mode == Mode.TERMINAL:
        reason = "TERMINAL_LATCHED"
    return PaceState(
        mode=mode,
        pressure=pressure,
        healthy_samples=count,
        healthy_since=since,
        last_at=obs.now,
        reason=reason,
    )


def require_operation(state: PaceState, operation: str) -> None:
    """Enforce local capability at use; the operation must still check DB authority."""
    current = PaceState.model_validate(state.model_dump())
    if operation not in OPERATIONS[current.mode]:
        raise PermissionError(f"PACE_OPERATION_DENIED:{current.mode}:{operation}")


def perform(state: PaceState, operation: str, action: Callable[[], T]) -> T:
    """Invoke an operation only after the local capability guard succeeds."""
    require_operation(state, operation)
    return action()
