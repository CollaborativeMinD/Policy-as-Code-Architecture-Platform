# 02 — Psycopg synchronous bound SQL

**PG-PAT-002** · Contracts: `PG-QUERY-001`, `PG-TX-001`, `PG-CONTRACT-001`

Perform bounded PostgreSQL reads and validated writes with explicit connection and transaction ownership.

## Contract and PostgreSQL purpose

The query projects `id`, `status`, `telemetry`, and `observed_at` from `hmt_pg.metrics`. It binds values separately from SQL and applies `status = %s AND id > %s ORDER BY id LIMIT %s`. `id` supplies a unique keyset position; `(status, id)` has a supporting PostgreSQL index.

`insert_metric()` borrows its connection. The caller owns a transaction spanning multiple effects. `fetch_metrics()` returns validated `Metric` objects and materializes only the admitted page. Schema/table identifiers are fixed; the optional `qualified_table("metrics")` helper combines an allowlist with `sql.Identifier`.

## Reference use

```python
import psycopg
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import Metric, QueryWindow
from hmt_pg_patterns.sync_driver import fetch_metrics, insert_metric

def store_and_read(config: DbConfig, metric: Metric) -> list[Metric]:
    with psycopg.connect(**config.connect_kwargs(), autocommit=True) as conn:
        with conn.transaction():
            insert_metric(conn, metric)
            return fetch_metrics(conn, QueryWindow(limit=100))
```

A normal context exit commits before this function returns. An exception rolls back the complete owned transaction. Keep network publication outside a retryable database transaction; the outbox pattern supplies the explicit bridge when an external effect is needed.

## Optimization and security decisions

Keyset pagination avoids an exposed offset scan and makes the ordering contract visible. It does not guarantee an index scan for every table size or parameter distribution. Inspect the actual plan through pattern 17 and measure the deployed workload.

Bound data with `%s`; identifiers cannot be passed as value parameters. Do not introduce SQL interpolation to accommodate an unapproved table. A page boundary also does not freeze updates or deletions between requests. A consistent export needs an explicitly owned snapshot transaction and a separately bounded lifetime.

## Implementation and verification

Implementation: [sync_driver.py](../../src/hmt_pg_patterns/sync_driver.py), [queries.py](../../src/hmt_pg_patterns/queries.py).

Executable checks: [test_sync_driver.py](../../tests/test_sync_driver.py), [test_query_contracts.py](../../tests/test_query_contracts.py), [test_fixture_protocol_regressions.py](../../tests/test_fixture_protocol_regressions.py).

**Resource contract:** Each page contains 1–10,000 rows; status is a closed enum; id is a positive PostgreSQL bigint.

Upstream or governing basis: [Psycopg parameter binding](https://www.psycopg.org/psycopg3/docs/basic/params.html), [PostgreSQL LIMIT ordering](https://www.postgresql.org/docs/current/queries-limit.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
