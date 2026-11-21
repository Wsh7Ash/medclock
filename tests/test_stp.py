from __future__ import annotations

from medclock.stp import Edge, is_feasible, latest_times, longest_paths, positive_cycle


def test_longest_paths_follows_edges() -> None:
    edges = [Edge(0, 1, 10), Edge(0, 2, 5), Edge(2, 1, 3), Edge(1, 0, -20), Edge(2, 0, -30)]
    distances = longest_paths(3, edges)
    assert distances == (0, 10, 5)


def test_unreachable_nodes_stay_none() -> None:
    distances = longest_paths(3, [Edge(0, 1, 4)])
    assert distances == (0, 4, None)


def test_zero_weight_cycle_is_not_a_contradiction() -> None:
    edges = [Edge(0, 1, 10), Edge(1, 0, -10)]
    distances = longest_paths(2, edges)
    assert distances == (0, 10)
    assert positive_cycle(2, edges) == ()


def test_positive_cycle_is_detected_and_returns_to_its_start() -> None:
    edges = [Edge(0, 1, 100), Edge(1, 2, 60), Edge(2, 0, -140), Edge(0, 3, 0)]
    assert longest_paths(4, edges) is None
    cycle = positive_cycle(4, edges)
    assert cycle
    assert sum(edge.weight for edge in cycle) == 20
    steps = list(cycle)
    for index, edge in enumerate(steps):
        following = steps[(index + 1) % len(steps)]
        assert edge.dst == following.src


def test_latest_times_respect_upper_bounds() -> None:
    edges = [Edge(0, 1, 10), Edge(1, 0, -20), Edge(0, 2, 10), Edge(2, 0, -20), Edge(2, 1, 5)]
    latest = latest_times(3, edges)
    assert latest == (0, 20, 15)
    assert is_feasible(3, edges)


def test_latest_times_none_when_infeasible() -> None:
    edges = [Edge(0, 1, 420), Edge(1, 0, -540), Edge(0, 2, 420), Edge(2, 1, 240), Edge(2, 0, -540)]
    assert latest_times(3, edges) is None


def test_edge_equality_is_structural() -> None:
    assert Edge(1, 2, 30, "x") == Edge(1, 2, 30, "x")
    assert Edge(1, 2, 30, "x") != Edge(1, 2, 30, "y")
    assert len({Edge(1, 2, 30), Edge(1, 2, 30)}) == 1


def test_certificate_weights_match_the_constraints() -> None:
    edges = [Edge(0, 1, 420), Edge(1, 2, 240), Edge(2, 0, -540)]
    cycle = positive_cycle(3, edges)
    assert len(cycle) == 3
    assert sum(edge.weight for edge in cycle) == 120
