"""RDP-B02 bounded ordered event delivery; subscribers have read-only contracts."""

from __future__ import annotations

from typing import Literal
from pydantic import Field
from hmt_rdp.common import Closed


class Event(Closed):
    event_id: str = Field(pattern=r"^[a-z0-9-]{1,24}$")
    sequence: int = Field(ge=1, le=4)
    payload: str = Field(max_length=32)


class Delivery(Closed):
    status: Literal["DELIVERED", "DUPLICATE"]
    outputs: tuple[str, ...]
    failures: tuple[int, ...]
