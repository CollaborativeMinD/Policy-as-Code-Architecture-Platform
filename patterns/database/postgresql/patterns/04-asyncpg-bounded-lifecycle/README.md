# 04 — asyncpg with bounded teardown

**PG-PAT-004** · Contracts: `PG-QUERY-001`, `PG-CLOSE-001`, `PG-CONTRACT-001`

Use raw asyncio PostgreSQL access while making connection closure, failures, and forced termination observable.

## Contract and PostgreSQL purpose

This reference binds values with `$1`, `$2`, and subsequent PostgreSQL parameter positions. It decodes asyncpg's JSON text before strict `Metric` validation and encodes writes with nonfinite numbers rejected. TLS, connect timeout, command timeout, and PostgreSQL session settings come from `DbConfig`.

## Reference use

```python
from hmt_pg_patterns import asyncpg_driver
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import Metric, QueryWindow

async def store_and_read(config: DbConfig, metric: Metric) -> list[Metric]:
    async with asyncpg_driver.connection(config, timeout=5.0) as conn:
        async with conn.transaction():
            await asyncpg_driver.insert_metric(conn, metric)
            return await asyncpg_driver.fetch_metrics(conn, QueryWindow(limit=100))
```

Here `timeout` is the teardown budget; connection establishment and command budgets remain explicit in `config`. `close_connection()` returns `"graceful"` after a successful close. On a close timeout it terminates the transport, emits `ASYNCPG_CONNECTION_FORCED_TERMINATION`, and returns `"forced"`. Unexpected cleanup errors propagate.

The context manager preserves an original operation failure if cleanup also fails: the original exception remains the raised object, with the cleanup failure attached as its cause. A cleanup failure following an otherwise successful body is raised rather than discarded.

## Optimization and maintenance

asyncpg is a separate asyncio driver choice, not an automatic speed upgrade. Measure the actual query mix, encoding cost, network latency, and pool policy before selecting it. A connection is not a shared concurrent-query lane. Use pattern 06's finite `lease()` helper for pool checkout.

The repaired PGlite fixture still lacks the native Terminate handshake, so live fixture cleanup can exercise forced termination. Deterministic fault tests separately exercise graceful completion, stalled closure, unexpected cleanup errors, and primary-exception preservation. Native transport behavior is an additional qualification boundary.

## Implementation and verification

Implementation: [asyncpg_driver.py](../../src/hmt_pg_patterns/asyncpg_driver.py).

Executable checks: [test_asyncpg_driver.py](../../tests/test_asyncpg_driver.py), [test_teardown_faults.py](../../tests/test_teardown_faults.py), [test_asyncpg_lifecycle_faults.py](../../tests/test_asyncpg_lifecycle_faults.py).

**Resource contract:** Connect and command budgets come from DbConfig; teardown timeout is finite, positive, and at most 30 s.

Upstream or governing basis: [asyncpg API](https://magicstack.github.io/asyncpg/current/api/index.html), [asyncpg usage](https://magicstack.github.io/asyncpg/current/usage.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
