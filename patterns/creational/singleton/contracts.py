"""RDP-C01 closed, tenant-scoped configuration; no process-global authority."""

from __future__ import annotations

from pydantic import Field
from hmt_rdp.common import Closed


class Config(Closed):
    tenant: str = Field(pattern=r"^[a-z]{1,16}$")
    limit: int = Field(ge=1, le=8)
