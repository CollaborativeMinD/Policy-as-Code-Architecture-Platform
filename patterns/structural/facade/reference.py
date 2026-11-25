"""RDP-S02 two typed read ports; unavailable ports propagate HOLD."""

from __future__ import annotations

from collections.abc import Callable
from .contracts import Reading, Report


class AuditFacade:
    def __init__(self, catalog: Callable[[], Reading], evidence: Callable[[], Reading]) -> None:
        self._ports = (catalog, evidence)

    def inspect(self) -> Report:
        values = []
        for expected, port in zip(("catalog", "evidence"), self._ports, strict=True):
            try:
                value = port()
            except (TimeoutError, RuntimeError):
                return Report(status="HOLD", readings=tuple(values), reason="HOLD_SUBSYSTEM")
            if value.subsystem != expected:
                return Report(status="HOLD", readings=tuple(values), reason="HOLD_PORT_IDENTITY")
            values.append(value)
        return Report(status="PASS", readings=tuple(values), reason="READ_ONLY_COMPLETE")
