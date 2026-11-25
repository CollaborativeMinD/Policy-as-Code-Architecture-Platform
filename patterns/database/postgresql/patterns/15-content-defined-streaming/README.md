# 15 — Content-defined streaming into PostgreSQL

**PG-PAT-015** · Contracts: `PG-CDC-001`, `PG-CONTRACT-001`, `PG-FENCE-001`, `PG-CHECKPOINT-001`

Preserve byte content and deterministic boundaries across packetizations, then persist ordered chunks through the same database authority contract.

## Contract and PostgreSQL purpose

`Scanner` owns an immutable snapshot of each admitted packet and emits contiguous immutable `Chunk` records. The rolling polynomial is `H' = (256*H + incoming - outgoing*256**W) mod (2**61 - 1)`. The window continues across chunk cuts. After the minimum size, a matching content remainder cuts the chunk; the maximum size forces a cut. A content match takes precedence when both conditions hold.

Identical bytes and policy produce identical chunk boundaries regardless of input packetization. The final nonempty tail is emitted once. Partially consuming and closing a feed aborts the scanner so callers cannot continue from an ambiguous state.

## Reference use

```python
from uuid import UUID
from hmt_pg_patterns.authority import Authority
from hmt_pg_patterns.streaming_contracts import Policy
from hmt_pg_patterns.streaming_writer import StreamWriter

def persist_source(conn, stream_id: UUID, packets):
    authority = Authority(conn)
    identity = authority.identity()
    policy = Policy(max_total_bytes=1048576, max_packets=1024)
    writer = StreamWriter(authority, stream_id, identity.epoch, policy)
    return writer.write(packets)
```

The asyncio composition uses `AsyncAuthority`, `AsyncStreamWriter`, and an async packet iterator. `stream_chunks()` also supports a standalone bounded sink: it awaits each sink result before consuming the next emitted chunk, creates no background queue, and never retries a sink call implicitly.

## Replay and delivery

Each chunk request binds its sequence, byte offset, predecessor digest, policy digest, payload, and a stable UUID derived from the stream identity, epoch, index, and content hash. PostgreSQL decides whether it is a new effect, an exact replay, or a conflict.

A failed run requires a fresh writer and replay from byte zero with the same source and policy. The rolling window is not reconstructed from the checkpoint tip alone. A committed prefix is reused idempotently; changed bytes, policy, sequence, or stale authority are rejected. An outer transaction, when present, still owns final commit.

## Bounded execution and evidence

Choose mission-sized limits explicitly. Defaults are finite but are not workload calibration. Async execution checks total and packet bounds, yields at a finite quantum, propagates cancellation, and records classified cleanup failure without hiding an earlier failure. Source and sink implementations must cooperate with cancellation; an owned process deadline is required for blocking native I/O. The fixed worker supplies that outer bound.

Tests compare the recurrence with an independently recomputed polynomial, historical source vectors, changed packetization, mutable-input snapshots, boundary discontinuities, backpressure, failure cleanup, and live PostgreSQL replay. The configured target modulus is not a promised average chunk size or compression ratio.

## Implementation and verification

Implementation: [streaming.py](../../src/hmt_pg_patterns/streaming.py), [streaming_contracts.py](../../src/hmt_pg_patterns/streaming_contracts.py), [streaming_scan.py](../../src/hmt_pg_patterns/streaming_scan.py), [streaming_runtime.py](../../src/hmt_pg_patterns/streaming_runtime.py), [streaming_state.py](../../src/hmt_pg_patterns/streaming_state.py), [streaming_writer.py](../../src/hmt_pg_patterns/streaming_writer.py), [streaming_async_writer.py](../../src/hmt_pg_patterns/streaming_async_writer.py).

Executable checks: [test_streaming_scanner.py](../../tests/test_streaming_scanner.py), [test_streaming_parity.py](../../tests/test_streaming_parity.py), [test_streaming_pipeline.py](../../tests/test_streaming_pipeline.py), [test_streaming_boundaries.py](../../tests/test_streaming_boundaries.py), [test_streaming_writer.py](../../tests/test_streaming_writer.py).

**Resource contract:** Policy bounds packet bytes, total bytes, packet count, window, chunk size, and async quantum; each sink is awaited before the next chunk is delivered.

Upstream or governing basis: [Branch source lineage](../../references/primitive_lineage.json).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
