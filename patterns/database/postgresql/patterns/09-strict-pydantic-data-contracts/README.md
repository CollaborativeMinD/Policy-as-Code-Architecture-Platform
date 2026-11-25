# 09 — Strict PostgreSQL data contracts

**PG-PAT-009** · Contracts: `PG-CONTRACT-001`, `PG-SNAPSHOT-001`

Validate telemetry, query windows, and authority receipts at every persistence or parsing boundary.

## Contract and PostgreSQL purpose

`Metric` admits a positive PostgreSQL bigint id, `active` or `inactive` status, at most 64 telemetry keys, finite numeric values, and a timestamp with an explicit UTC offset. Telemetry keys use a bounded ASCII identifier grammar. Unknown fields are rejected. `QueryWindow` bounds page size and keyset position; `BatchSpec` separately describes a batch's retained rows and admitted total.

These are application DTOs, not schema migration substitutes. PostgreSQL enforces its own constraints for the stored row. The authority path additionally revalidates its JSON/byte header inside SQL so bypassing Python does not bypass effect admission.

## Reference use

```python
from datetime import UTC, datetime
from hmt_pg_patterns.models import Metric
from hmt_pg_patterns.queries import snapshot_metric

def validated_measurement(identifier: int, temperature: float) -> Metric:
    original = Metric(
        id=identifier,
        status="active",
        telemetry={"temperature": temperature},
        observed_at=datetime.now(UTC),
    )
    return snapshot_metric(original)
```

The snapshot helper validates again and detaches the telemetry dictionary. That distinction matters: `frozen=True` prevents assigning a new field, but it does not recursively freeze `Metric.telemetry`. A caller can still mutate that nested dictionary. Never use a `Metric` object as an immutable authorization snapshot.

## Authority and parsing boundaries

`ChunkRequest`, `Receipt`, `PeerIdentity`, and `CheckpointData` use strict, frozen contracts whose admitted fields are immutable bytes, UUIDs, integers, strings, and booleans. `immutable_checkpoint()` in pattern 14 converts the validated checkpoint to a Pyrsistent map. PostgreSQL remains the durable record of authority and sequence.

Validation at the write seam rejects malformed copies made with `model_construct()` or `model_copy(update=...)`. Validation at the read seam catches schema drift and unexpected driver representations. Failures remain visible instead of coercing unrecognized database content into a nominally successful response.

The resource contract covers admitted application values. Logging, external deserialization, and transport framing need their own bounds; the fixed worker supplies a separate finite request-frame contract.

## Implementation and verification

Implementation: [models.py](../../src/hmt_pg_patterns/models.py), [queries.py](../../src/hmt_pg_patterns/queries.py), [authority_types.py](../../src/hmt_pg_patterns/authority_types.py).

Executable checks: [test_models.py](../../tests/test_models.py), [test_query_contracts.py](../../tests/test_query_contracts.py), [test_authority_security.py](../../tests/test_authority_security.py), [test_checkpoints_cache.py](../../tests/test_checkpoints_cache.py).

**Resource contract:** Telemetry has at most 64 bounded keys and finite float values; aware timestamps; bounded bigint IDs and query sizes; chunk bytes 1–1,048,576.

Upstream or governing basis: [Pydantic strict mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/), [Pydantic model configuration](https://pydantic.dev/docs/validation/latest/api/pydantic/config/).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
