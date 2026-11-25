"""RDP-B03 / RDP-EQ-01: explicit PACE-T categorical order, epoch and hysteresis."""

from __future__ import annotations

from enum import StrEnum
from pydantic import Field
from hmt_rdp.common import Closed


class State(StrEnum):
    PRIMARY = "PRIMARY"
    ALTERNATE = "ALTERNATE"
    CONTINGENCY = "CONTINGENCY"
    EMERGENCY = "EMERGENCY"
    TERMINAL = "TERMINAL"


class Tick(Closed):
    state: State
    soft_failures: tuple[bool, ...] = Field(max_length=2)
    recovery_streak: int = Field(ge=0, le=4)
    pressure: bool
    hard_terminal: bool
    emergency: bool
    history_epoch: int = Field(ge=1, le=1)


class Transition(Closed):
    state: State
    soft_failures: tuple[bool, ...]
    recovery_streak: int
    reason: str
