# 16 — PACE capability and guarded recovery

**PG-PAT-016** · Contracts: `PG-PACE-001`, `PG-FENCE-001`

Select PostgreSQL service capabilities from trusted observations while keeping effect authority in the database.

## Contract and PostgreSQL purpose

The local controller maps trusted health and authority observations to an explicit capability set. It does not promote Redis or transport health into permission to change PostgreSQL state.

| Mode | Available operations | Triggered capability boundary |
| --- | --- | --- |
| Primary | read, write, relay | All declared services ready |
| Alternate | read, write, relay | Cache unavailable; durable PostgreSQL path retained |
| Contingency | read, write | Transport unavailable |
| Emergency | read_checkpoint, health | Database unavailable |
| Terminal | none | Invalid authority/epoch, nonpositive margin, stale sampling, or prior Terminal latch |

An available operation remains subject to its own dependency and authority checks. For example, a permitted relay can still return an uncertain cache outcome; its durable outbox work remains available for reconciliation.

## Reference use

```python
from hmt_pg_patterns.authority import Authority
from hmt_pg_patterns.pace import perform, step
from hmt_pg_patterns.pace_models import Observation, PaceState

def guarded_admission(state: PaceState, observation: Observation, conn, request):
    current = step(state, observation)
    receipt = perform(current, "write", lambda: Authority(conn).admit(request))
    return current, receipt
```

Initialize `last_at` and observation time in the same monotonic-clock domain. A large first sample gap is intentionally treated as stale; it must not be created accidentally by mixing wall time, monotonic time, and a zero default.

## Recovery and maintenance

Degradation follows the observed capability immediately. Recovery requires explicit reconciliation, no uncertain acknowledgment, a current epoch, adequate margin, low accumulated pressure, enough healthy samples, and sufficient dwell. Terminal remains latched within the lifecycle; a new authorized lifecycle is required for reset.

`perform()` checks the operation before invoking the callback, while `Authority.admit()` still repeats the authoritative PostgreSQL check. Neither a healthy observation nor a caller-created `PaceState` grants database rights.

Tests include deletion/restoration/control witnesses for recovery guards, temporal boundaries, pressure decay, Terminal latching, and continued PostgreSQL operation when Redis is unavailable. They validate the selected equations and guards; health-sensor calibration and mission thresholds must be supplied by the deployment.

## Implementation and verification

Implementation: [pace.py](../../src/hmt_pg_patterns/pace.py), [pace_models.py](../../src/hmt_pg_patterns/pace_models.py).

Executable checks: [test_pace.py](../../tests/test_pace.py), [test_worker_e2e.py](../../tests/test_worker_e2e.py).

**Resource contract:** Finite policy bounds, monotonic observations, maximum sample gap, recovery sample count, dwell interval, and pressure threshold.

Upstream or governing basis: [Branch executable policy](../../src/hmt_pg_patterns/pace.py).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
