"""Simple temporal problem engine: difference constraints with a positive-cycle proof.

Every edge ``src -> dst`` with weight ``w`` is the constraint ``t(dst) >= t(src) + w``.
A set of such constraints is satisfiable precisely when the graph has no positive
cycle, which is what makes the infeasibility certificate checkable by hand.
"""

from __future__ import annotations

from dataclasses import dataclass

_NEG_INF = -(10**12)


@dataclass(frozen=True)
class Edge:
    src: int
    dst: int
    weight: int
    label: str = ""


def longest_paths(node_count: int, edges: list[Edge] | tuple[Edge, ...], source: int = 0) -> tuple[int | None, ...] | None:
    """Longest path weight from ``source`` to every node, or ``None`` if a positive cycle exists."""
    dist: list[int | None] = [None] * node_count
    dist[source] = 0
    for _ in range(node_count):
        changed = False
        for edge in edges:
            base = dist[edge.src]
            if base is None:
                continue
            candidate = base + edge.weight
            current = dist[edge.dst]
            if current is None or candidate > current:
                dist[edge.dst] = candidate
                changed = True
        if not changed:
            return tuple(dist)
    return None


def latest_times(node_count: int, edges: list[Edge] | tuple[Edge, ...]) -> tuple[int | None, ...] | None:
    """Latest feasible value of every variable, or ``None`` if the system is infeasible.

    A path ``v -> Z`` with weight ``W`` proves ``t(v) <= t(Z) - W``, so the latest
    value is the negative of the longest path from ``Z`` in the reversed graph.
    """
    reversed_edges = tuple(Edge(e.dst, e.src, e.weight, e.label) for e in edges)
    dist = longest_paths(node_count, reversed_edges)
    if dist is None:
        return None
    return tuple(None if value is None else -value for value in dist)


def positive_cycle(node_count: int, edges: list[Edge] | tuple[Edge, ...]) -> tuple[Edge, ...]:
    """Return a positive cycle as an edge list, or ``()`` when there is none.

    Floyd-Warshall (max-plus) is used here rather than Bellman-Ford because the
    cycle itself is the product: it is returned in walking order and its weights
    sum to a positive number that the reader can re-add.
    """
    best = [[_NEG_INF] * node_count for _ in range(node_count)]
    nxt = [[-1] * node_count for _ in range(node_count)]
    lookup: dict[tuple[int, int], Edge] = {}
    for node in range(node_count):
        best[node][node] = 0
    for edge in edges:
        if edge.weight > best[edge.src][edge.dst]:
            best[edge.src][edge.dst] = edge.weight
            nxt[edge.src][edge.dst] = edge.dst
            lookup[(edge.src, edge.dst)] = edge

    for k in range(node_count):
        row_k = best[k]
        nxt_k = nxt[k]
        for i in range(node_count):
            via = best[i][k]
            if via == _NEG_INF:
                continue
            row_i = best[i]
            for j in range(node_count):
                if row_k[j] == _NEG_INF:
                    continue
                candidate = via + row_k[j]
                if candidate > row_i[j]:
                    row_i[j] = candidate
                    nxt[i][j] = nxt_k[j] if nxt[i][k] == -1 else nxt[i][k]

    for start in range(node_count):
        if best[start][start] <= 0:
            continue
        cycle: list[Edge] = []
        current = start
        for _ in range(node_count + 1):
            following = nxt[current][start]
            if following < 0:
                break
            edge = lookup.get((current, following))
            if edge is None:
                break
            cycle.append(edge)
            current = following
            if current == start:
                break
        if cycle and sum(edge.weight for edge in cycle) > 0:
            return tuple(cycle)
    return ()


def is_feasible(node_count: int, edges: list[Edge] | tuple[Edge, ...]) -> bool:
    return longest_paths(node_count, edges) is not None
