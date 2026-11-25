"""RDP-S04 scanner -> semantic view -> watchdog -> read-only target."""

from __future__ import annotations

from typing import Literal
from hmt_rdp.common import Closed


class Call(Closed):
    authorized: bool
    semantic_label: Literal["READ"]
    source_intact: bool
    stages: tuple[str, ...] = ()


class Result(Closed):
    stages: tuple[str, ...]
    result: Literal["reference-read"]
