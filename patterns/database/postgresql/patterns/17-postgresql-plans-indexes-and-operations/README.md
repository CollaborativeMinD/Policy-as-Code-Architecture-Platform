# 17 — PostgreSQL plans, indexes, and WAL observations

**PG-PAT-017** · Contracts: `PG-OPS-001`, `PG-QUERY-001`

Inspect the actual PostgreSQL query plan and durability prerequisites without issuing mutating maintenance operations in the hot path.

## Contract and PostgreSQL purpose

`explain_page()` prefixes the fixed, parameter-bound keyset query with `EXPLAIN (FORMAT JSON)`. It intentionally omits `ANALYZE`, so the helper observes a plan without executing the data query. It accepts no arbitrary SQL string.

`wal_settings()` reads `fsync`, `full_page_writes`, `synchronous_commit`, and `wal_level`. `require_local_durable_commit()` rejects disabled fsync/full-page protection or asynchronous commit. The production worker invokes this gate before storing chunks. No application hot path issues SQL `CHECKPOINT`.

## Reference use

```python
import psycopg
from hmt_pg_patterns.diagnostics import explain_page, wal_settings
from hmt_pg_patterns.models import QueryWindow

def inspect_postgresql(config):
    with psycopg.connect(**config.connect_kwargs(), autocommit=True) as conn:
        settings = wal_settings(conn)
        settings.require_local_durable_commit()
        plan = explain_page(conn, QueryWindow(limit=100))
        return settings, plan
```

On the disposable SQL fixture the durability gate may reject the observed settings; do not weaken it to make a test backend look production-ready. Configuration observation and qualification of actual storage behavior are separate evidence.

## Optimization and maintainability

The metrics migration defines the primary key and `(status, id)` index matching the keyset predicate and order. PostgreSQL may choose a sequential scan for a small table or a different data distribution. Tests verify that the index exists and a plan is observable; they do not require an index scan as a universal success condition.

Use representative data, planner statistics, and actual workload timings when changing indexes or batch sizes. Record query shape, data distribution, server/client versions, network conditions, and transaction policy with any performance claim. The branch supplies no fastest-driver ranking.

Vacuum/analyze scheduling, backups, restoration drills, replica policy, and storage power-loss tests belong to deployment operations. These references expose the PostgreSQL observations needed to assess a deployment; they do not silently configure those services or certify them from a local SQL run.

## Implementation and verification

Implementation: [diagnostics.py](../../src/hmt_pg_patterns/diagnostics.py), [01_metrics.sql](../../sql/01_metrics.sql).

Executable checks: [test_diagnostics.py](../../tests/test_diagnostics.py).

**Resource contract:** Only the fixed bounded keyset query is explainable; diagnostic settings use fixed expressions and inherited statement deadlines.

Upstream or governing basis: [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html), [PostgreSQL WAL reliability](https://www.postgresql.org/docs/current/wal-reliability.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
