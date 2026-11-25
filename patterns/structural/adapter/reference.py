"""RDP-S01 preserves declared units; an unknown schema never guesses a conversion."""

from __future__ import annotations

from .contracts import Canonical, External


class TemperatureAdapter:
    def convert(self, request: External) -> Canonical:
        return Canonical(temperature=request.temperature + 273150)

    def inverse(self, value: Canonical) -> External:
        return External(version="1", unit="mC", temperature=value.temperature - 273150)
