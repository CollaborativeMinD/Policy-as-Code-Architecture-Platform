"""RDP-C01: explicitly owned singleton scope; dependency injection is simpler."""

from __future__ import annotations

from threading import RLock
from .contracts import Config


FOUR_LIMIT = 4


class ScopedSingleton:
    def __init__(self) -> None:
        self._values: dict[str, Config] = {}
        self._lock = RLock()
        self._closed = False

    def get(self, value: Config) -> Config:
        with self._lock:
            if self._closed:
                raise ValueError("DENY_CLOSED_SCOPE")
            previous = self._values.get(value.tenant)
            if previous is not None and previous != value:
                raise ValueError("DENY_CONFIGURATION_DRIFT")
            if previous is None and len(self._values) >= FOUR_LIMIT:
                raise ValueError("DENY_SCOPE_CAPACITY")
            if previous is None:
                self._values[value.tenant] = value
            return self._values[value.tenant]

    def close(self) -> None:
        with self._lock:
            self._values.clear()
            self._closed = True
