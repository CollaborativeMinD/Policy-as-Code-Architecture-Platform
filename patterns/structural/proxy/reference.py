"""RDP-S03 guard entry and returned bytes; catches source drift at use."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from .contracts import Capability


READ_MAX = 4096


class ReferenceProxy:
    def __init__(self, reader: Callable[[], bytes]) -> None:
        self._reader = reader

    def read(self, capability: Capability, now: int) -> bytes:
        if now < 0 or now >= capability.expires_at:
            raise ValueError("DENY_EXPIRED_LEASE")
        raw = self._reader()
        if len(raw) > READ_MAX:
            raise ValueError("DENY_RESOURCE_BUDGET")
        if hashlib.sha256(raw).hexdigest() != capability.source_digest:
            raise ValueError("DENY_SOURCE_DRIFT")
        return raw
