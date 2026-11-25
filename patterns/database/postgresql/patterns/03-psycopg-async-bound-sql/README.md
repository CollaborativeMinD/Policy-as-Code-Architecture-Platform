# 03 — Psycopg native asyncio SQL

**PG-PAT-003** · Contracts: `PG-QUERY-001`, `PG-TX-001`, `PG-CONTRACT-001`

Expose the same PostgreSQL value and transaction contract through awaited driver operations.

## Contract and PostgreSQL purpose

`async_driver` uses `psycopg.AsyncConnection`, awaits execute/fetch operations, and applies the same literal SQL and strict DTO contracts as the blocking reference. It does not wrap blocking calls in an async function. Give each independent concurrent unit its own leased connection.

## Reference use

```python
import psycopg
from hmt_pg_patterns import async_driver
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import Metric, QueryWindow

async def store_and_read(config: DbConfig, metric: Metric) -> list[Metric]:
    async with await psycopg.AsyncConnection.connect(
        **config.connect_kwargs(), autocommit=True
    ) as conn:
        async with conn.transaction():
            await async_driver.insert_metric(conn, metric)
            return await async_driver.fetch_metrics(conn, QueryWindow(limit=100))
```

The connection, transaction, and cursor scopes remain owned across exceptions. Async syntax allows other tasks to run while I/O is pending; it does not execute several statements concurrently on one connection. Sharing a connection also shares transaction state, so a peer task's rollback can affect the same unit of work.

## Delivery and cancellation

Propagate `CancelledError` through the transaction context. If cancellation or a broken transport obscures the commit response, retain the operation's stable identity and reconcile its database outcome. The generic transaction retry helper does not retry ambiguous connection failures. The peer/epoch stream writer uses stable request IDs for explicit origin replay.

For a long-lived service, use the explicitly opened async pool in pattern 06. Bound task admission outside the pool as well as database checkout. Tests exercise async execution and rollback; production network cancellation, independent backend contention, and shutdown under native I/O require the separate native profile.

## Implementation and verification

Implementation: [async_driver.py](../../src/hmt_pg_patterns/async_driver.py).

Executable checks: [test_async_driver.py](../../tests/test_async_driver.py), [test_pools.py](../../tests/test_pools.py).

**Resource contract:** The same QueryWindow and DbConfig bounds apply; one connection has one transaction owner.

Upstream or governing basis: [Psycopg asynchronous operations](https://www.psycopg.org/psycopg3/docs/advanced/async.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
