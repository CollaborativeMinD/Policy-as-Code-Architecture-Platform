# 05 — Owned transactions and bounded retry

**PG-PAT-005** · Contracts: `PG-TX-001`, `PG-RETRY-001`

Retry a complete aborted PostgreSQL transaction under an explicit attempt budget and ownership contract.

## Contract and PostgreSQL purpose

Only SQLSTATE `40001` (serialization failure) and `40P01` (deadlock) admit another attempt. Each attempt opens and closes the complete transaction. Every other PostgreSQL error, transport error, cancellation, and application exception propagates. The final attempt propagates a remaining failure.

Requiring `autocommit=True` and `TransactionStatus.IDLE` prevents an outer transaction from silently converting this helper into savepoint-only retries. The callback must leave commit/rollback ownership with the helper and must contain only effects safe to repeat after a database-confirmed abort.

## Reference use

```python
import psycopg
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import Metric
from hmt_pg_patterns.sync_driver import insert_metric, transaction_retry

def store(config: DbConfig, metric: Metric) -> int:
    def operation(conn) -> int:
        insert_metric(conn, metric)
        return metric.id

    with psycopg.connect(**config.connect_kwargs(), autocommit=True) as conn:
        return transaction_retry(conn, operation, attempts=3)
```

The asyncio counterpart accepts an awaitable callback and awaits the entire attempt. A return value is released only after the transaction context successfully completes.

## Delivery, limits, and verification

PostgreSQL requires retrying all decision logic that belongs to the failed transaction. Repeating only the last SQL statement can use stale decisions. This narrow policy deliberately does not retry unique violations, even where an application-specific algorithm might classify one as transient.

An attempt bound limits repeated work; connection, lock, and statement deadlines bound database waits. It is not a general wall-clock bound for arbitrary callback code. There is no automatic external publication, unknown-outcome replay, backoff scheduler, or failover hidden inside this primitive.

Tests use real transaction rollback and controlled SQLSTATE failures to verify attempt semantics and the excluded paths. Such error injection proves retry classification; it does not prove native deadlock scheduling or multi-backend serializability behavior.

## Implementation and verification

Implementation: [driver_contracts.py](../../src/hmt_pg_patterns/driver_contracts.py), [sync_driver.py](../../src/hmt_pg_patterns/sync_driver.py), [async_driver.py](../../src/hmt_pg_patterns/async_driver.py).

Executable checks: [test_sync_driver.py](../../tests/test_sync_driver.py), [test_async_driver.py](../../tests/test_async_driver.py), [test_query_contracts.py](../../tests/test_query_contracts.py).

**Resource contract:** Attempts are strict integers from 1 through 5; default 3. Requires an idle autocommit connection.

Upstream or governing basis: [PostgreSQL serialization failure handling](https://www.postgresql.org/docs/current/mvcc-serialization-failure-handling.html), [Psycopg transaction contexts](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
