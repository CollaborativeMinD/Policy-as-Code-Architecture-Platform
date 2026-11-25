"""RDP-S01 exact integer unit conversion: milli-Celsius to milli-Kelvin."""

from __future__ import annotations

from typing import Literal
from pydantic import Field
from hmt_rdp.common import Closed


class External(Closed):
    version: Literal["1"]
    unit: Literal["mC"]
    temperature: int = Field(ge=-273150, le=1000000)


class Canonical(Closed):
    version: Literal["1"] = "1"
    unit: Literal["mK"] = "mK"
    temperature: int = Field(ge=0, le=1273150)
