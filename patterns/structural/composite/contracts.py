"""RDP-S05 / FF-RDP-DAG-01 / RDP-EQ-06: bounded graph of common nodes."""

from __future__ import annotations

from pydantic import Field
from hmt_rdp.common import Closed


class Node(Closed):
    node_id: str = Field(pattern=r"^[a-z]{1,8}$")
    weight: int = Field(ge=0, le=10)
    children: tuple[str, ...] = Field(max_length=4)


class Graph(Closed):
    root: str
    nodes: tuple[Node, ...] = Field(min_length=1, max_length=16)
