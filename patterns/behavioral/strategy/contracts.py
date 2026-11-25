"""RDP-B01 / FF-RDP-ADMIT-01: deterministic policy-bounded algorithm choice."""

from __future__ import annotations

from typing import Annotated, Literal
from pydantic import Field
from hmt_rdp.common import Closed


class Request(Closed):
    algorithm: Literal["scan", "sort"]
    costs: tuple[Annotated[int, Field(ge=0, le=1000)], ...] = Field(min_length=1, max_length=16)


class Selection(Closed):
    index: int
    cost: int
    decision: Literal["PROPOSAL_ONLY"] = "PROPOSAL_ONLY"
