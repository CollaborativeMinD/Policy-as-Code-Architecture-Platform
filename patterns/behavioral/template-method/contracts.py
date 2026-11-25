"""RDP-B05 frozen parse/validate/emit lesson; no authority-bearing hook fields."""

from __future__ import annotations

from typing import Literal
from pydantic import Field
from hmt_rdp.common import Closed


class Request(Closed):
    text: str = Field(min_length=1, max_length=32)


class Result(Closed):
    value: str = Field(min_length=1, max_length=32)
    steps: tuple[Literal["parse", "validate", "emit"], ...]
    authority: Literal["NONE"] = "NONE"
