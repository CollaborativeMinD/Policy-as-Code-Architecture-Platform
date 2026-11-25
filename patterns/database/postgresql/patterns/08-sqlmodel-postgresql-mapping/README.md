# 08 — SQLModel PostgreSQL mapping

**PG-PAT-008** · Contracts: `PG-CONTRACT-001`, `PG-QUERY-001`, `PG-TX-001`

Map a PostgreSQL table without treating an ORM constructor as strict input admission.

## Contract and PostgreSQL purpose

`MetricRow` maps `hmt_pg.metrics` with explicit `BigInteger`, `Text`, PostgreSQL `JSONB`, and timezone-aware `DateTime` columns. Its underlying `Metrics` class uses SQLModel's table-name convention; the `MetricRow` alias preserves the public API without overriding an inconsistent framework descriptor type. The application contract remains the strict `Metric` DTO. `snapshot_metric()` revalidates and detaches input before constructing the table instance.

Writes own `Session.begin()`. Reads use SQLModel expressions, `col()` for the mapped columns, deterministic ordering by id, and the same bounded keyset fields as raw SQL. Result rows are converted back through the strict DTO boundary.

## Reference use

```python
from hmt_pg_patterns import orm, orm_model
from hmt_pg_patterns.config import DbConfig
from hmt_pg_patterns.models import Metric, QueryWindow

def store_and_read(config: DbConfig, metric: Metric):
    engine = orm.create_pg_engine(config, size=4)
    try:
        orm_model.insert_metric(engine, metric)
        return orm_model.fetch_metrics(engine, QueryWindow(limit=100))
    finally:
        engine.dispose()
```

These helper calls own separate sessions and transactions. Construct a larger explicit session unit when multiple mapped effects must share one commit, preserving the DTO validation boundary.

## Maintainability and limits

The SQL migration remains authoritative for constraints, indexes, privileges, and ownership. This reference does not call `SQLModel.metadata.create_all()` to replace migration history. A table model can describe storage without enforcing all boundary validation during ordinary construction, so validation is deliberately separate.

The implementation provides a concrete synchronous mapping. The branch's asynchronous abstraction example is SQLAlchemy Core in pattern 07; no unimplemented async SQLModel behavior is claimed. Tests verify committed inserts, bounded reads, and strict rejection through the actual PostgreSQL path.

## Implementation and verification

Implementation: [orm_model.py](../../src/hmt_pg_patterns/orm_model.py), [models.py](../../src/hmt_pg_patterns/models.py).

Executable checks: [test_orm_drivers.py](../../tests/test_orm_drivers.py), [test_models.py](../../tests/test_models.py).

**Resource contract:** One bounded keyset page; finite engine pool inherited from pattern 07.

Upstream or governing basis: [SQLModel separate data and table models](https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/), [SQLModel validation semantics](https://sqlmodel.tiangolo.com/advanced/datetime/).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
