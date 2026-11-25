"""RDP-B04 / RDP-EQ-04: confined fixture command, atomic effect and receipt."""

from __future__ import annotations

from typing import Literal
from pydantic import Field
from hmt_rdp.common import Closed


class Operation(Closed):
    operation_id: str = Field(pattern=r"^[a-z0-9-]{1,32}$")
    value: int = Field(ge=1, le=8)
    mode: Literal["PROPOSAL_ONLY", "COMMIT_CONFINED_TEST"]
    authority: Literal["fixture:effect"]


class Receipt(Closed):
    operation_id: str
    request_hash: str
    value: int
    disposition: Literal["PROPOSAL_ONLY", "COMMITTED"]
