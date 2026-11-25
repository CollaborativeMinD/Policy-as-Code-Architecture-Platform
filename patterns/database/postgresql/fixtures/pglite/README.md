# Local PGlite protocol fixture repair

This test-only Linux/Node adapter lets the installed PostgreSQL WASM engine execute the branch's real COPY and prepared-statement tests. Production Python code does not import it. It is a deliberately scoped compatibility repair, not native PostgreSQL server qualification.

## Reproduce

Use Node 24.22.1 and Python 3.12 or 3.13. In a directory containing this kit:

```bash
npm ci --ignore-scripts
python apply_callback.py .
```

Then set `HMT_PGLITE_CLI` to the absolute path of `server.mjs` before running branch pytest. The branch service harness supplies the loopback address, disposable port, memory database, and finite connection count. A separately supplied native `HMT_TEST_DSN` takes precedence. The existing scratch install uses `python fixture_repair/apply_callback.py .` from its npm root because its `node_modules` directory is one level above this kit.

`package-lock.json` binds npm artifacts by their registry integrity values. The applicator accepts only PGlite 0.5.15, pglite-socket 0.2.18, and the exact upstream or already-patched source hash. Before a fresh edit it preserves the original upstream bytes under `upstream-snapshots/`. A mismatch fails closed. `callback.readable.patch` explains the source change; `apply_callback.py` applies its exact compiled equivalent. The inspected upstream bytes and full compiled diff are retained in the scratch evidence directory and are excluded from the new branch package.

## COPY defect and repair

The upstream synchronous WASM call emits PostgreSQL's actual `CopyInResponse`, then attempts to read data before Node can handle the next TCP event. Its ordinary read callback returns zero. PostgreSQL therefore reports `08006` (unexpected EOF), followed by `08P01` (lost protocol synchronization). The preserved libpq trace records this failure.

The single compiled callback hook activates only when this fixture supplies `_hmtFixtureReadMore`. After observing the actual PostgreSQL `CopyInResponse`, the fixture supplies a bounded reader for that same client's Linux socket descriptor. The reader first drains the handler's buffered bytes, then reads additional bytes from the socket. It admits at most 64 MiB over five seconds, uses bounded polling, and returns real EOF on disconnect or exhaustion. It is cleared after the protocol call.

PostgreSQL parses the original `CopyData`, `CopyDone`, and `CopyFail` messages, applies constraints, changes rows, and decides transaction outcomes. The fixture neither replaces COPY with INSERT nor manufactures successful backend responses. The synchronous input bridge blocks the Node event loop during COPY; this is acceptable only for this disposable, single-backend test fixture.

## Prepared-statement namespace defect and repair

Upstream logical socket clients share one PostgreSQL backend and therefore collide on driver-generated names such as `_pg3_0`. The adapter prefixes nonempty protocol statement names with the logical handler identity in Parse, Bind, Describe, and Close messages. SQL text, value bytes, and unnamed statements are unchanged. Portals are unchanged because SQL `DECLARE` owns server-cursor names. Tracked statements are closed when the owning handler disconnects.

This restores the tested named-plan behavior without disabling production automatic preparation. It does not create isolated backend sessions: GUCs, roles, advisory locks, unnamed-statement interleaving, and other session state still require native qualification.

## Evidence and limits

`tests/test_fixture_protocol_regressions.py` verifies two open clients with distinct prepared plans, continued plan use after peer close, 3,000 rows across multiple COPY writes, and producer CopyFail rollback with connection reuse. `tests/test_bulk_analytics.py` verifies ordinary COPY, duplicate rollback, empty input, pipeline transactions, and named server-cursor cleanup. `regression.xml` records the focused fixture run. The full branch admission evidence is authoritative for the release result.

This fixture does not qualify native authentication, TLS, multiple backend contention, cancellation requests, storage power-loss durability, replication, or Tailcat wire transport. The upstream ignored Terminate behavior remains; asyncpg cleanup can report forced termination, which is an explicit tested outcome. Never cite this fixture as proof of production network or failover behavior.
