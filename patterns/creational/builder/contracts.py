"""RDP-C02 completed configuration cannot exist partially."""

from __future__ import annotations

from pydantic import Field
from hmt_rdp.common import Closed


class Config(Closed):
    owner: str = Field(pattern=r"^[a-z]{1,16}$")
    limit: int = Field(ge=1, le=8)
    enabled: bool
