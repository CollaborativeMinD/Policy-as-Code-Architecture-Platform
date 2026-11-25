"""RDP-B07 / RDP-EQ-02: mandatory auth/policy/evidence/receipt gates."""

from __future__ import annotations

from typing import Literal
from hmt_rdp.common import Closed


class Context(Closed):
    authenticated: bool
    current_policy: bool
    evidence_intact: bool
    receipt_bound: bool


class Decision(Closed):
    disposition: Literal["READ_ADMITTED", "DENY"]
    visited: tuple[str, ...]
    reason: str
    consequential_effects: Literal[0] = 0
