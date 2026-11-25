"""RDP-S02 read-only subsystem reports preserve failures."""

from __future__ import annotations

from typing import Literal
from pydantic import Field
from hmt_rdp.common import Closed


class Reading(Closed):
    subsystem: Literal["catalog", "evidence"]
    count: int = Field(ge=0, le=32)


class Report(Closed):
    status: Literal["PASS", "HOLD"]
    readings: tuple[Reading, ...]
    reason: str
    consequential_effects: Literal[0] = 0
