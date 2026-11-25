"""RDP-C02 immutable staged builder; direct Config is the simpler alternative."""

from __future__ import annotations

from dataclasses import dataclass, replace
from .contracts import Config


@dataclass(frozen=True, slots=True)
class Builder:
    owner: str
    limit: int | None = None

    def with_limit(self, limit: int) -> "Builder":
        if self.limit is not None:
            raise ValueError("DENY_STEP_REPETITION")
        Config(owner=self.owner, limit=limit, enabled=True)
        return replace(self, limit=limit)

    def finish(self, enabled: bool = True) -> Config:
        if self.limit is None:
            raise ValueError("DENY_INCOMPLETE_BUILDER")
        return Config(owner=self.owner, limit=self.limit, enabled=enabled)
