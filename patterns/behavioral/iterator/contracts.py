"""RDP-B06 / FF-RDP-TIME-01: bounded evidence snapshot cursor."""

from __future__ import annotations

from pydantic import Field
from hmt_rdp.common import Closed


class Record(Closed):
    record_id: str = Field(pattern=r"^[a-z]{1,8}$")
    value: int = Field(ge=0, le=100)


class Cursor(Closed):
    offset: int = Field(ge=0, le=32)
    snapshot_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: int = Field(ge=1)


class Page(Closed):
    records: tuple[Record, ...]
    next_cursor: Cursor | None
