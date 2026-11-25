# 13 — Peer and epoch authority with a fixed Tailcat worker

**PG-PAT-013** · Contracts: `PG-PEER-001`, `PG-FENCE-001`, `PG-CONTRACT-001`

Bind trusted transport identity to one fixed database LOGIN and recheck epoch authority in the transaction that changes PostgreSQL state.

## Contract and PostgreSQL purpose

PostgreSQL derives the caller from `session_user`. A protected authority row maps that LOGIN to a peer key, active epoch, and expiry. `authority_for()` locks the row and checks authority inside the same transaction as an effect. `admit_chunk()` verifies exact replay identity, predecessor digest, sequence, byte offset, policy digest, and payload before inserting an immutable effect, advancing the checkpoint, and recording the outbox intent.

The privileged functions have a fixed search path and qualified objects. Public access is revoked. A separate, non-login migration owner owns the functions; runtime roles receive only enumerated entry-point grants. The fixed worker also rejects administrative role flags after connection.

## Reference use

```python
from uuid import UUID
from hmt_pg_patterns.authority import Authority
from hmt_pg_patterns.streaming_contracts import Policy
from hmt_pg_patterns.streaming_writer import StreamWriter
from hmt_pg_patterns.transport import TailcatBinding, bind_tailcat_connection

def append_from_fixed_worker(conn, binding: TailcatBinding, stream_id: UUID, payload: bytes):
    identity = bind_tailcat_connection(conn, binding)
    policy = Policy(max_total_bytes=65536, max_packets=1)
    writer = StreamWriter(Authority(conn), stream_id, identity.epoch, policy)
    return writer.write([payload])
```

`conn` is a fixed, authenticated runtime LOGIN connection. `binding` comes from host-owned configuration; it is never constructed from the request. On an idle autocommit connection each chunk's transaction completes before the writer advances. If an outer transaction already exists, its owner still controls final commit and may roll back the observed receipt.

## Tailcat composition

Tailcat 0.7.0 supplies an authenticated child context through `TAILCAT_PEER_KEY`. Run a fixed Python command under `tailcat serve --allow=... exec -- ...`, using a pinned executable, a private worker configuration, and host-enforced process isolation. `worker.py` checks the trusted peer before reading bounded ingress; the fixed database session is checked before decoded payload processing. A request contains only a stream UUID and canonical base64 payload. It cannot select a DSN, peer, epoch, or chunk policy.

The environment is trustworthy only when the launcher and OS ownership boundary are trustworthy. A same-UID process that can replace the worker, configuration, or environment is outside that boundary. Port forwarding alone does not convey authenticated peer identity into PostgreSQL.

## Evidence and qualification boundary

Default tests execute the actual PostgreSQL authority functions, Redis projection, and worker service flow with an injected trusted launcher context and explicit test `SET SESSION AUTHORIZATION`. PGlite's shared backend does not turn a startup user name into an independently authenticated session. This is software composition evidence, not LOGIN authentication evidence.

`qualification/native_worker_test.py` checks the real fixed child against a native DSN; `qualification/tailcat_wire_test.py` adds actual transport. Tailcat startup in the managed environment encountered a Linux netlink `EPERM` restriction even with local DERP. No wire PASS is claimed. Preserve this distinction in any reuse or release decision.

## Implementation and verification

Implementation: [authority.py](../../src/hmt_pg_patterns/authority.py), [authority_async.py](../../src/hmt_pg_patterns/authority_async.py), [authority_types.py](../../src/hmt_pg_patterns/authority_types.py), [transport.py](../../src/hmt_pg_patterns/transport.py), [worker.py](../../src/hmt_pg_patterns/worker.py), [worker_config.py](../../src/hmt_pg_patterns/worker_config.py), [worker_io.py](../../src/hmt_pg_patterns/worker_io.py), [worker_service.py](../../src/hmt_pg_patterns/worker_service.py), [02_authority.sql](../../sql/02_authority.sql), [03_checkpoints.sql](../../sql/03_checkpoints.sql).

Executable checks: [test_authority_atomic.py](../../tests/test_authority_atomic.py), [test_authority_security.py](../../tests/test_authority_security.py), [test_transport_binding.py](../../tests/test_transport_binding.py), [test_worker_contracts.py](../../tests/test_worker_contracts.py), [test_worker_e2e.py](../../tests/test_worker_e2e.py).

**Resource contract:** One fixed peer/LOGIN mapping; private configuration at most 16 KiB; worker payload at most 64 KiB; frame at most 128 KiB; hard process deadline at most 30 s.

Upstream or governing basis: [Tailcat pinned CLI source](https://github.com/tailscale/tailcat/blob/v0.7.0/cmd/tailcat/tailcat.go), [PostgreSQL function security](https://www.postgresql.org/docs/current/sql-createfunction.html).

[Pattern index](../../Index.md) · [Branch overview](../../README.md)
