"""RDP-B06 deterministic immutable pagination; no backing-store access exposed."""

from __future__ import annotations

from hmt_rdp.common import digest
from .contracts import Cursor, Page, Record


FOUR_LIMIT = 4
SNAPSHOT_MAX = 32


class EvidenceIterator:
    def __init__(self, records: tuple[Record, ...]) -> None:
        if len(records) > SNAPSHOT_MAX or len({r.record_id for r in records}) != len(records):
            raise ValueError("DENY_SNAPSHOT_BOUND")
        self._records = tuple(sorted(records, key=lambda r: r.record_id))
        self.snapshot_digest = digest([r.model_dump() for r in self._records])

    def page(self, cursor: Cursor, size: int, now: int) -> Page:
        if type(size) is not int or not 1 <= size <= FOUR_LIMIT:
            raise ValueError("DENY_PAGE_BOUND")
        if now < 0 or now >= cursor.expires_at:
            raise ValueError("DENY_CURSOR_EXPIRED")
        if cursor.snapshot_digest != self.snapshot_digest or cursor.offset > len(self._records):
            raise ValueError("DENY_CURSOR_STALE")
        end = min(cursor.offset + size, len(self._records))
        selected = self._records[cursor.offset : end]
        next_cursor = (
            cursor.model_copy(update={"offset": end}) if end < len(self._records) else None
        )
        return Page(records=selected, next_cursor=next_cursor)
