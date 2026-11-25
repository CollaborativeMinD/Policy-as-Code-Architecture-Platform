# 06 — Finite connection pools

**PG-PAT-006** · Contracts: `PG-POOL-001`, `PG-CLOSE-001`, `PG-CONFIG-001`

Make PostgreSQL connection capacity, checkout wait, readiness, and shutdown explicit at one ownership layer.

## Contract and PostgreSQL purpose

The Psycopg contexts create pools with `open=False`, open them explicitly, wait for initial readiness, and close them in `finally`. They use autocommit connections so each operation can own its transaction visibly. Capacity, pending waiters, and checkout wait are finite.

## Reference use

```python
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import QueryWindow
from hmt_pg_patterns.pools import sync_pool
from hmt_pg_patterns.sync_driver import fetch_metrics

def read_with_pool(config: DbConfig):
    with sync_pool(config, size=4, timeout=5.0) as pool:
        with pool.connection() as conn:
            return fetch_metrics(conn, QueryWindow(limit=100))
```

For a service, keep the outer pool context at application lifespan rather than recreating it for every request. Every independent transaction borrows its own connection. `async_pool()` has the corresponding awaited startup and close lifecycle.

```python
from hmt_pg_patterns import asyncpg_driver
from hmt_pg_patterns.asyncpg_pool import lease, pool
from hmt_pg_patterns.models import QueryWindow

async def read_with_asyncpg(config):
    async with pool(config, size=4, timeout=5.0) as instance:
        async with lease(instance, timeout=2.0) as conn:
            return await asyncpg_driver.fetch_metrics(conn, QueryWindow(limit=100))
```

Always use a finite asyncpg checkout timeout. The close helper classifies a deadline-triggered `terminate()` fallback with `ASYNCPG_POOL_FORCED_TERMINATION`. Capacity bounds active connections; it does not independently bound all tasks waiting elsewhere in the application.

## Layer and maintenance decisions

SQLAlchemy owns its own bounded pool in pattern 07. Do not wrap that engine inside these driver pools. Size capacity from the database's connection budget across every worker process and replica. No default size here is a workload sizing result.

Tests assert fixed capacity, lifecycle closure, exception cleanup, and timeout when a size-one asyncpg pool is already leased. Native pooler interoperability, network partitions, and connection storms remain deployment qualification tasks.

## Implementation and verification

Implementation: [pools.py](../../src/hmt_pg_patterns/pools.py), [asyncpg_pool.py](../../src/hmt_pg_patterns/asyncpg_pool.py), [driver_contracts.py](../../src/hmt_pg_patterns/driver_contracts.py).

Executable checks: [test_pools.py](../../tests/test_pools.py), [test_asyncpg_driver.py](../../tests/test_asyncpg_driver.py), [test_teardown_faults.py](../../tests/test_teardown_faults.py).

**Resource contract:** Capacity 1–32; checkout/close budgets finite and at most 30 s; Psycopg pending waiters capped at twice capacity.

Upstream or governing basis: [Psycopg connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html), [asyncpg pool API](https://magicstack.github.io/asyncpg/current/api/index.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
