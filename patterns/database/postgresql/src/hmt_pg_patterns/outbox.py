"""PG-OUTBOX-01: committed claim before Redis I/O; unknown outcomes require readback."""

from uuid import UUID

from psycopg.pq import TransactionStatus

from .authority import Authority
from .authority_types import CheckpointData, FrozenContract, checkpoint
from .checkpoints_snapshot import immutable_checkpoint


class OutboxEvent(FrozenContract):
    """A committed database claim and its typed checkpoint observation."""

    event_id: UUID
    claim_id: UUID
    checkpoint: CheckpointData


def _idle(connection):
    if not connection.autocommit or connection.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("OUTBOX_REQUIRES_IDLE_AUTOCOMMIT")


def _event(row):
    if row is None:
        return None
    value = checkpoint(row[2:])
    if value is None:
        raise ValueError("OUTBOX_CHECKPOINT_MISSING")
    return OutboxEvent(event_id=row[0], claim_id=row[1], checkpoint=value)


def claim(connection):
    """Commit one current-epoch intent before attempting external cache I/O."""
    _idle(connection)
    with connection.transaction():
        row = connection.execute("SELECT * FROM hmt_pg.claim_checkpoint()").fetchone()
    return _event(row)


def recover(connection, limit=100):
    """Enumerate uncertain claims after restart. This performs no external write."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("INVALID_RECOVERY_LIMIT")
    _idle(connection)
    with connection.transaction():
        rows = connection.execute(
            "SELECT * FROM hmt_pg.recover_checkpoints(%s)", (limit,)
        ).fetchall()
    return [_event(row) for row in rows]


def finish(connection, event, state):
    """Record an observed result only for the session's exact stored claim token."""
    _idle(connection)
    with connection.transaction():
        row = connection.execute(
            "SELECT hmt_pg.finish_checkpoint(%s,%s,%s)", (event.event_id, event.claim_id, state)
        ).fetchone()
    if not row[0]:
        raise ValueError("OUTBOX_CLAIM_CONFLICT")


def _current(connection, event):
    """Derive scope from the stored claim, never the caller's checkpoint object."""
    _idle(connection)
    with connection.transaction():
        row = connection.execute(
            "SELECT * FROM hmt_pg.checkpoint_for_claim(%s,%s)", (event.event_id, event.claim_id)
        ).fetchone()
    if row is None:
        raise ValueError("OUTBOX_CLAIM_CONFLICT")
    value = checkpoint(row)
    if value is None:
        raise ValueError("OUTBOX_CHECKPOINT_MISSING")
    return value


def _publish(connection, cache, event, snapshot):
    try:
        outcome = cache.offer(snapshot)
        verified = cache.read(_current(connection, event)) is not None
        state = "ACKED" if outcome in {"APPLIED", "IDENTICAL", "STALE"} and verified else "UNKNOWN"
    except Exception as original:
        try:
            finish(connection, event, "UNKNOWN")
        except Exception as recovery:
            raise ExceptionGroup("OUTBOX_UNCERTAIN", [original, recovery]) from recovery
        raise
    finish(connection, event, state)
    return state


def relay_checkpoint(connection, cache):
    """Claim and project once; uncertain delivery requires explicit reconciliation."""
    event = claim(connection)
    if event is None:
        return None
    return _publish(connection, cache, event, immutable_checkpoint(event.checkpoint))


def rebuild_checkpoint(connection, cache, event):
    """Explicit replay of a disposable projection, after renewed database admission.

    Redis CAS makes this replay idempotent. The cache grants no effect authority;
    revocation may race after the checked database snapshot and before Redis I/O.
    """
    scope = _current(connection, event)
    with connection.transaction():
        identity = Authority(connection).identity()
        current = Authority(connection).checkpoint(scope.stream_id)
        if current is None or current.epoch != identity.epoch:
            raise ValueError("CHECKPOINT_EPOCH_REVOKED")
    return _publish(connection, cache, event, immutable_checkpoint(current))


def reconcile(connection, cache, event):
    """Read back only; permit recording observed outcomes after epoch revocation."""
    current = _current(connection, event)
    state = "ACKED" if cache.read(current) is not None else "UNKNOWN"
    finish(connection, event, state)
    return state
