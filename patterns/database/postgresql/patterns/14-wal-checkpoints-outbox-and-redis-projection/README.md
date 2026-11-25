# 14 — WAL, immutable checkpoints, outbox, and Redis projection

**PG-PAT-014** · Contracts: `PG-FENCE-001`, `PG-SNAPSHOT-001`, `PG-OUTBOX-001`, `PG-CHECKPOINT-001`, `PG-OPS-001`

Keep authority and replay custody in PostgreSQL while treating Redis as a recoverable projection and Pyrsistent as immutable in-memory state.

## Contract and PostgreSQL purpose

One PostgreSQL transaction records the chunk effect, advances its stream head, and appends the checkpoint outbox intent. PostgreSQL's WAL protects that transaction according to the actual server and storage configuration. The application checkpoint is a logical stream position and digest; this package does not consume physical WAL records, expose a replication slot, or use an LSN as a substitute for the application contract.

`CheckpointData` contains immutable scalar values. `immutable_checkpoint()` validates it and returns a Pyrsistent map. Structural sharing provides stable in-memory versions. Durable custody remains in PostgreSQL.

## Reference use

```python
from hmt_pg_patterns.checkpoints import CheckpointCache
from hmt_pg_patterns.outbox import recover, reconcile, relay_checkpoint

def project_once(conn, redis_client):
    cache = CheckpointCache(redis_client)
    outcome = relay_checkpoint(conn, cache)
    for event in recover(conn, limit=10):
        reconcile(conn, cache, event)
    return outcome
```

`conn` must be idle and autocommit so the claim commits before external Redis I/O. The Redis client is host-owned, uses finite connection/read deadlines, and in production has TLS plus an ACL identity. The fixed worker validates these configuration requirements.

## Outbox and recovery state

Claiming changes `PENDING` to `DISPATCHING` with a stored claim token. Publication is followed by readback against the authoritative checkpoint. The durable outcome is `ACKED` only when the observation supports it; otherwise it remains `UNKNOWN`. Worker responses likewise report `projection: "ACKED"` or `"UNKNOWN"` after explicit readback.

`recover()` enumerates uncertain claims without sending anything. `reconcile()` reads back and records an observed outcome. `rebuild_checkpoint()` explicitly republishes a disposable projection after fresh same-epoch authority admission. Lost acknowledgments therefore produce a recoverable state instead of an assumed success or blind effect replay.

## Redis ordering and limits

Canonical checkpoint encoding preserves PostgreSQL bigint values as decimal strings because Redis Lua numbers cannot represent every bigint exactly. The Lua compare-and-set rejects conflicting, stale, or malformed projections. Reads require a fresh PostgreSQL checkpoint and exact cached-byte agreement. Poisoned or missing Redis content never grants authority.

The transaction and Redis operation cannot form one atomic commit. A projection write can occur after an authority snapshot and race a later revocation; it still cannot authorize a new PostgreSQL effect. Effects always repeat epoch admission in PostgreSQL.

The production worker checks `fsync`, `full_page_writes`, and synchronous commit prerequisites. A passing settings check is neither a power-loss experiment nor proof of remote replication durability. Native recovery, storage, and failover remain separate qualification work.

## Implementation and verification

Implementation: [checkpoints.py](../../src/hmt_pg_patterns/checkpoints.py), [checkpoints_lua.py](../../src/hmt_pg_patterns/checkpoints_lua.py), [checkpoints_snapshot.py](../../src/hmt_pg_patterns/checkpoints_snapshot.py), [outbox.py](../../src/hmt_pg_patterns/outbox.py), [worker_projection.py](../../src/hmt_pg_patterns/worker_projection.py), [diagnostics.py](../../src/hmt_pg_patterns/diagnostics.py), [02_authority.sql](../../sql/02_authority.sql), [03_checkpoints.sql](../../sql/03_checkpoints.sql).

Executable checks: [test_checkpoints_cache.py](../../tests/test_checkpoints_cache.py), [test_outbox_recovery.py](../../tests/test_outbox_recovery.py), [test_authority_atomic.py](../../tests/test_authority_atomic.py), [test_worker_e2e.py](../../tests/test_worker_e2e.py), [test_diagnostics.py](../../tests/test_diagnostics.py).

**Resource contract:** Checkpoint encoding at most 8 KiB; cache TTL 300 s; recovery pages 1–100 events; finite worker projection budget at most 514.

Upstream or governing basis: [Pyrsistent upstream](https://github.com/tobgu/pyrsistent), [PostgreSQL WAL reliability](https://www.postgresql.org/docs/current/wal-reliability.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
