"""RDP-B07 ordered independent guards; this lesson grants no sovereign authority."""

from __future__ import annotations

from .contracts import Context, Decision

ORDER = ("authenticate", "policy", "evidence", "receipt")
FIELDS = ("authenticated", "current_policy", "evidence_intact", "receipt_bound")


class GuardChain:
    def __init__(self, handlers: tuple[str, ...] = ORDER) -> None:
        if handlers != ORDER:
            raise ValueError("DENY_REQUIRED_GUARD_ORDER")
        self._handlers = handlers

    def check(self, context: Context) -> Decision:
        visited = []
        for name, field in zip(self._handlers, FIELDS, strict=True):
            visited.append(name)
            if not getattr(context, field):
                return Decision(
                    disposition="DENY", visited=tuple(visited), reason="DENY_" + name.upper()
                )
        return Decision(
            disposition="READ_ADMITTED", visited=tuple(visited), reason="GUARDS_COMPLETE"
        )
