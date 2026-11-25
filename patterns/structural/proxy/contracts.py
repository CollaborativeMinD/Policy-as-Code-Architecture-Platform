"""RDP-S03 explicit capability, source pin, and clock; no ambient authority."""

from __future__ import annotations

from typing import Literal
from pydantic import Field
from hmt_rdp.common import Closed


class Capability(Closed):
    subject: Literal["reviewer"]
    audience: Literal["pattern-reference"]
    scope: Literal["read"]
    resource: Literal["reference.py"]
    policy_epoch: int = Field(ge=1, le=1)
    expires_at: int = Field(ge=1)
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
