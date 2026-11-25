"""RDP-B04 no external actuation; durable SQLite transaction owns fixture custody."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from hmt_rdp.sqlite_store import transaction
from hmt_rdp.common import digest
from .contracts import Operation, Receipt


class CommandStore:
    def __init__(self, path: Path) -> None:
        if path.is_symlink():
            raise ValueError("DENY_STORE_LINK")
        self.path = path
        with transaction(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS effects (id TEXT PRIMARY KEY, hash TEXT, value INT)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, receipt TEXT)")

    def execute(self, operation: Operation, fault: str = "none") -> Receipt:
        request_hash = digest(operation.model_dump(mode="json"))
        receipt = Receipt(
            operation_id=operation.operation_id,
            request_hash=request_hash,
            value=operation.value,
            disposition="PROPOSAL_ONLY",
        )
        if operation.mode == "PROPOSAL_ONLY":
            return receipt
        with transaction(self.path, timeout=1) as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT hash FROM effects WHERE id=?", (operation.operation_id,)
            ).fetchone()
            if previous is not None:
                return self.replay(db, receipt, previous[0])
            db.execute(
                "INSERT INTO effects VALUES (?,?,?)",
                (operation.operation_id, request_hash, operation.value),
            )
            if fault == "after_effect":
                raise RuntimeError("INJECTED_BEFORE_COMMIT")
            committed = receipt.model_copy(update={"disposition": "COMMITTED"})
            db.execute(
                "INSERT INTO outbox VALUES (?,?)",
                (operation.operation_id, committed.model_dump_json()),
            )
            return committed

    @staticmethod
    def replay(db: sqlite3.Connection, receipt: Receipt, previous_hash: str) -> Receipt:
        if previous_hash != receipt.request_hash:
            raise ValueError("DENY_DUPLICATE_CONFLICT")
        row = db.execute(
            "SELECT receipt FROM outbox WHERE id=?", (receipt.operation_id,)
        ).fetchone()
        if row is None:
            raise ValueError("HOLD_OUTBOX_INCONSISTENT")
        stored = Receipt.model_validate_json(row[0])
        if stored != receipt.model_copy(update={"disposition": "COMMITTED"}):
            raise ValueError("HOLD_OUTBOX_DRIFT")
        return stored

    def counts(self) -> tuple[int, int]:
        with transaction(self.path) as db:
            return (
                db.execute("SELECT COUNT(*) FROM effects").fetchone()[0],
                db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0],
            )
