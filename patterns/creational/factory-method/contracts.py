"""RDP-C03 fixed offline product family, no live providers."""

from __future__ import annotations

from typing import Literal
from pydantic import Field
from hmt_rdp.common import Closed


class Request(Closed):
    provider: Literal["echo", "uppercase"]
    text: str = Field(min_length=1, max_length=32)


class Product(Closed):
    text: str = Field(min_length=1, max_length=32)
    side_effect: Literal["NONE"] = "NONE"
