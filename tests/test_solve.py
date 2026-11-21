from __future__ import annotations

import pytest

from medclock.constraints import System, build_system
from medclock.model import load
from medclock.solve import Relaxation, solve, validate_schedule
from medclock.stp import Edge, is_feasible
from conftest import FIXTURES, med, regimen


@pytest.fixture(scope="module")
def morning():
    return load(FIXTURES / "morning.json")


@pytest.fixture(scope="module")
def pinch():
    return load(FIXTURES / "pinch.json")


def test_morning_is_feasible(morning) -> None:
    solution = solve(morning)
    assert solution.feasible
    assert solution.violations == []
    assert set(solution.times) == {dose.label for dose in morning.doses}


def test_morning_schedule_respects_every_rule(morning) -> None:
    solution = solve(morning)
    assert validate_schedule(morning, solution.times) == []


def test_earliest_times_are_within_windows(morning) -> None:
    solution = solve(morning)
    for dose in morning.doses:
        assert dose.start <= solution.earliest[dose.label] <= dose.end


def test_gap_pins_iron_after_levothyroxine(morning) -> None:
    solution = solve(morning)
    assert solution.times["levothyroxine#1"] == 390
    assert solution.times["iron#1"] == 630


def test_preferred_time_is_met_when_there_is_slack(morning) -> None:
    solution = solve(morning)
    assert solution.times["metformin#2"] == 1170
    assert solution.preferences_met == 1


def test_unreachable_preference_stays_at_the_nearest_feasible_time(morning) -> None:
    solution = solve(morning)
    assert solution.times["iron#1"] == 630
    assert solution.slack["iron#1"] == 30


def test_slack_is_latest_minus_chosen(morning) -> None:
    solution = solve(morning)
    for label, minutes in solution.times.items():
        assert solution.slack[label] == solution.latest[label] - minutes
        assert solution.slack[label] >= 0


def test_latest_schedule_is_also_valid(morning) -> None:
    solution = solve(morning)
    assert validate_schedule(morning, solution.latest) == []
    assert solution.earliest != solution.latest


def test_solving_twice_is_deterministic(morning) -> None:
    assert solve(morning).times == solve(morning).times


def test_morning_has_no_warnings(morning) -> None:
    assert solve(morning).warnings == []


def test_pinch_is_infeasible_with_a_120_minute_cycle(pinch) -> None:
    solution = solve(pinch)
    assert not solution.feasible
    assert solution.times == {}
    assert solution.cycle
    assert solution.cycle_weight == 120
    assert sum(edge.weight for edge in solution.cycle) == 120


def test_pinch_core_is_the_three_expected_groups(pinch) -> None:
    solution = solve(pinch)
    assert {constraint.cid for constraint in solution.core} == {
        "window:levothyroxine#1",
        "gap:levothyroxine->calcium",
        "window:calcium#1",
    }
    assert solution.dropped_groups == 4


def test_each_core_group_is_required(pinch) -> None:
    solution = solve(pinch)
    system = build_system(pinch)
    for constraint in solution.core:
        kept = [entry for entry in system.constraints if entry.cid != constraint.cid]
        assert is_feasible(system.node_count(), [edge for entry in kept for edge in entry.edges])


def test_relaxation_costs_are_minimal_and_sufficient(pinch) -> None:
    solution = solve(pinch)
    assert len(solution.relaxations) == 3
    assert {item.delta for item in solution.relaxations} == {120}
    system = build_system(pinch)
    for item in solution.relaxations:
        assert _feasible_after(system, [item], item.delta - 1) is False
        assert _feasible_after(system, [item], item.delta) is True


def test_relaxations_are_sorted_by_cost(pinch) -> None:
    solution = solve(pinch)
    assert [item.delta for item in solution.relaxations] == sorted(item.delta for item in solution.relaxations)


def test_relaxation_budget_limits_what_is_offered(pinch) -> None:
    solution = solve(pinch, max_relax=60)
    assert solution.relaxations == ()
    assert solution.combined == ()
    assert solution.max_relax == 60


def test_cheaper_budget_still_reports_affordable_changes(pinch) -> None:
    assert len(solve(pinch, max_relax=120).relaxations) == 3


def test_independent_conflicts_need_a_combined_repair() -> None:
    payload = regimen(
        [
            med("x", "08:00", "08:30"),
            med("y", "09:00", "09:30"),
            med("p", "08:00", "08:30"),
            med("q", "08:30", "09:00"),
        ],
        gaps=[
            {"before": "x", "after": "y", "minutes": "2h"},
            {"before": "p", "after": "q", "minutes": "2h"},
        ],
    )
    problem = _problem(payload)
    solution = solve(problem)
    assert not solution.feasible
    assert solution.relaxations == ()
    assert len(solution.combined) == 2
    assert sum(item.delta for item in solution.combined) == 90
    assert _feasible_after(build_system(problem), solution.combined) is True


def test_dose_outside_waking_hours_is_a_warning() -> None:
    problem = _problem(regimen([med("a", "22:30", "23:00")], wake="07:00", sleep="22:00"))
    solution = solve(problem)
    assert solution.feasible
    assert any("outside waking hours" in warning for warning in solution.warnings)


def test_pinned_dose_is_a_warning() -> None:
    payload = regimen(
        [
            med(
                "a",
                "08:00",
                "08:30",
                food=[{"event": "breakfast", "relation": "before", "minutes": "30m"}],
            )
        ],
        events={"breakfast": "08:30"},
    )
    solution = solve(_problem(payload))
    assert solution.slack["a#1"] == 0
    assert any("pinned" in warning for warning in solution.warnings)


def test_waking_hours_are_not_a_constraint() -> None:
    problem = _problem(regimen([med("a", "23:00", "23:30")], wake="07:00", sleep="22:00"))
    assert solve(problem).feasible


def test_validator_catches_a_broken_schedule(morning) -> None:
    violations = validate_schedule(morning, {dose.label: 600 for dose in morning.doses})
    assert violations
    assert any("outside" in violation for violation in violations)


def _problem(payload: dict):
    from medclock.model import from_dict

    return from_dict(payload)


def _feasible_after(
    system: System,
    relaxations: tuple[Relaxation, ...] | list[Relaxation],
    delta_override: int | None = None,
) -> bool:
    """Apply the reported relaxations and test feasibility.

    ``delta_override`` replaces every relaxation's own delta, which is how the
    minimality assertions probe one minute below the reported cost.
    """
    edges: list[Edge] = []
    for constraint in system.constraints:
        for edge in constraint.edges:
            relaxed = 0
            for item in relaxations:
                if item.cid != constraint.cid:
                    continue
                option = next(option for option in constraint.options if option.kind == item.kind)
                if edge in option.edges:
                    relaxed = item.delta if delta_override is None else delta_override
            edges.append(Edge(edge.src, edge.dst, edge.weight - relaxed, edge.label))
    return is_feasible(system.node_count(), edges)
