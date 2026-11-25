"""RDP-S05 aggregates each reachable node once; rejects cycles and dangling children."""

from __future__ import annotations

import networkx as nx
from .contracts import Graph, Node


FOUR_LIMIT = 4


class Composite:
    def aggregate(self, value: Graph) -> int:
        nodes = {n.node_id: n for n in value.nodes}
        if len(nodes) != len(value.nodes) or value.root not in nodes:
            raise ValueError("DENY_NODE_IDENTITY")
        graph = self.graph(value, nodes)
        if not nx.is_directed_acyclic_graph(graph):
            raise ValueError("DENY_CYCLE")
        if nx.dag_longest_path_length(graph) > FOUR_LIMIT:
            raise ValueError("DENY_DEPTH")
        reachable = {value.root, *nx.descendants(graph, value.root)}
        return sum(nodes[node].weight for node in reachable)

    @staticmethod
    def graph(value: Graph, nodes: dict[str, Node]) -> nx.DiGraph[str]:
        graph: nx.DiGraph[str] = nx.DiGraph()
        graph.add_nodes_from(nodes)
        for node in value.nodes:
            if len(set(node.children)) != len(node.children):
                raise ValueError("DENY_DUPLICATE_EDGE")
            for child in node.children:
                if child not in nodes:
                    raise ValueError("DENY_CHILD_FAILURE")
                graph.add_edge(node.node_id, child)
        return graph
