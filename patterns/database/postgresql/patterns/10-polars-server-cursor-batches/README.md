# 10 — Polars through a PostgreSQL server cursor

**PG-PAT-010** · Contracts: `PG-CONTRACT-001`, `PG-QUERY-001`, `PG-TX-001`

Convert bounded server-fetched rows into stable-schema Polars batches without implicit full-result buffering.

## Contract and PostgreSQL purpose

`metric_frames()` requires an idle autocommit connection, opens one transaction and a uniquely named server cursor, and fetches a finite number of bounded batches. Every row passes through `Metric` before DataFrame construction.

Output columns are fixed: `id: Int64`, `status: String`, `telemetry_json: String`, and `observed_at: Datetime(us, UTC)`. JSON telemetry is explicitly encoded into a string column so differing keys do not grow or alter the DataFrame schema between batches.

## Reference use

```python
from contextlib import closing
import psycopg
from hmt_pg_patterns.analytics import metric_frames
from hmt_pg_patterns.models import QueryWindow

def first_batch(config):
    with psycopg.connect(**config.connect_kwargs(), autocommit=True) as conn:
        with closing(metric_frames(conn, QueryWindow(limit=500), batch_size=100)) as frames:
            return next(frames, None)
```

`closing()` is required when a caller may stop before exhaustion. It releases the PostgreSQL cursor and transaction immediately on exit. For a complete export, process each frame and release it before requesting the next; accumulating every frame in a list defeats the retained-batch memory objective.

## Optimization and maintenance

Asking a DataFrame API for batches does not alone prove that its database driver streams results. This implementation makes the server cursor explicit. Its batch loop is also bounded by the admitted row count, with an early break on empty fetch.

The cursor retains server resources and a transaction while the consumer works. Keep processing time finite, use the configured idle-transaction deadline, and inspect plans for large sorts or unsuitable indexes. A single result cursor and a sequence of independent keyset pages have different snapshot semantics; do not silently substitute one for the other.

Tests assert exact batch sizes, stable dtypes, empty-result behavior, and `pg_cursors` cleanup after early termination. They do not establish a universal memory figure or throughput claim for arbitrary database values and query plans.

## Implementation and verification

Implementation: [analytics.py](../../src/hmt_pg_patterns/analytics.py), [models.py](../../src/hmt_pg_patterns/models.py).

Executable checks: [test_bulk_analytics.py](../../tests/test_bulk_analytics.py), [test_fixture_protocol_regressions.py](../../tests/test_fixture_protocol_regressions.py).

**Resource contract:** Batch size 1–4,096; total rows at most QueryWindow.limit (1–10,000); finite fetch loop; bounded DTO fields.

Upstream or governing basis: [Polars database batch caveats](https://docs.pola.rs/api/python/stable/reference/api/polars.read_database.html), [Psycopg server cursors](https://www.psycopg.org/psycopg3/docs/advanced/cursors.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
