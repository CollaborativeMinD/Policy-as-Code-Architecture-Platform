"""PG-TX-001 and PG-POOL-001: fail closed on unowned transactions and limits."""

import math

from psycopg.pq import TransactionStatus

RETRYABLE_SQLSTATES = frozenset({"40001", "40P01"})


def owned_transaction(conn, attempts: int = 1) -> None:
    """An outer transaction is required; a savepoint cannot own commit/retry."""
    if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= 5:
        raise ValueError("ATTEMPTS_OUT_OF_RANGE")
    if not conn.autocommit or conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("IDLE_AUTOCOMMIT_CONNECTION_REQUIRED")


def pool_limits(size: int, timeout: float) -> None:
    """Reject ambiguous, unbounded, or non-finite resource limits."""
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 32:
        raise ValueError("POOL_SIZE_OUT_OF_RANGE")
    if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("TIMEOUT_OUT_OF_RANGE")
