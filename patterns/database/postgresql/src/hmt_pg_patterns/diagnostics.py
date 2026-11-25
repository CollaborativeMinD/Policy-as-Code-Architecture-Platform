"""PG-OPS-001: read-only plans and explicit PostgreSQL WAL settings."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .models import QueryWindow
from .queries import SELECT_SQL, window_values


class WalSettings(BaseModel):
    """Observed configuration is a prerequisite, not a power-loss durability proof."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    fsync: Literal["on", "off"]
    full_page_writes: Literal["on", "off"]
    synchronous_commit: Literal["on", "off", "local", "remote_write", "remote_apply"]
    wal_level: Literal["minimal", "replica", "logical"]

    def require_local_durable_commit(self) -> None:
        """Reject observed configurations that cannot support local durable commit."""
        WalSettings.model_validate(self.model_dump())
        if self.fsync != "on" or self.full_page_writes != "on":
            raise ValueError("WAL_PROTECTION_DISABLED")
        if self.synchronous_commit == "off":
            raise ValueError("ASYNC_COMMIT_NOT_ADMITTED")


def wal_settings(conn) -> WalSettings:
    """Read settings through fixed expressions; never issue CHECKPOINT in the hot path."""
    row = conn.execute(
        "SELECT current_setting('fsync'), current_setting('full_page_writes'), "
        "current_setting('synchronous_commit'), current_setting('wal_level')"
    ).fetchone()
    if row is None:
        raise RuntimeError("WAL_SETTINGS_UNAVAILABLE")
    return WalSettings.model_validate(dict(zip(WalSettings.model_fields, row, strict=True)))


def explain_page(conn, window: QueryWindow) -> dict:
    """EXPLAIN without ANALYZE observes the plan without executing a data operation."""
    row = conn.execute("EXPLAIN (FORMAT JSON) " + SELECT_SQL, window_values(window)).fetchone()
    if row is None:
        raise RuntimeError("PLAN_UNAVAILABLE")
    return row[0][0]
