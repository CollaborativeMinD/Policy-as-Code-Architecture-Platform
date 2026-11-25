"""RDP-B01 stable tie ordering and identical semantics across admitted strategies."""

from __future__ import annotations

from typing import Protocol
from .contracts import Request, Selection


COST_MAX = 1000


class Selector(Protocol):
    def select(self, costs: tuple[int, ...]) -> tuple[int, int]: ...


class Scan:
    def select(self, costs: tuple[int, ...]) -> tuple[int, int]:
        index = min(range(len(costs)), key=lambda i: (costs[i], i))
        return index, costs[index]


class Sort:
    def select(self, costs: tuple[int, ...]) -> tuple[int, int]:
        cost, index = sorted((cost, i) for i, cost in enumerate(costs))[0]
        return index, cost


def select(request: Request) -> Selection:
    if any(type(cost) is not int or not 0 <= cost <= COST_MAX for cost in request.costs):
        raise ValueError("DENY_COST_BOUND")
    strategies: dict[str, Selector] = {"scan": Scan(), "sort": Sort()}
    index, cost = strategies[request.algorithm].select(request.costs)
    return Selection(index=index, cost=cost)
