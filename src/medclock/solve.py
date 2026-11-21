"""Solving, schedule validation and failure diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from .constraints import Constraint, RelaxOption, System, build_system
from .model import Problem
from .stp import Edge, is_feasible, latest_times, longest_paths, positive_cycle
from .timeutil import format_time

MAX_RELAX_DEFAULT = 1440


@dataclass(frozen=True)
class Relaxation:
    cid: str
    kind: str
    delta: int
    text: str


@dataclass
class Solution:
    problem: Problem
    system: System
    feasible: bool
    times: dict[str, int]
    earliest: dict[str, int]
    latest: dict[str, int]
    slack: dict[str, int]
    preferences_met: int
    violations: list[str]
    warnings: list[str]
    cycle: tuple[Edge, ...]
    cycle_weight: int
    core: tuple[Constraint, ...]
    relaxations: tuple[Relaxation, ...]
    combined: tuple[Relaxation, ...]
    max_relax: int

    @property
    def dropped_groups(self) -> int:
        return len(self.system.constraints) - len(self.core)


def solve(problem: Problem, max_relax: int = MAX_RELAX_DEFAULT) -> Solution:
    """Solve the problem, or explain why it cannot be solved."""
    system = build_system(problem)
    node_count = system.node_count()
    distances = longest_paths(node_count, system.edges)
    if distances is None:
        return _infeasible(problem, system, max_relax)

    earliest = {dose.label: _value(distances[system.index(dose.label)]) for dose in problem.doses}
    latest_raw = latest_times(node_count, system.edges)
    latest = (
        {dose.label: _value(latest_raw[system.index(dose.label)]) for dose in problem.doses}
        if latest_raw is not None
        else dict(earliest)
    )

    times = dict(earliest)
    for _ in range(2):
        times = _align_preferences(times, latest, problem)

    violations = validate_schedule(problem, times)
    slack = {label: latest[label] - minutes for label, minutes in times.items()}
    warnings = _warnings(problem, times, slack)
    preferences_met = sum(
        1 for dose in problem.doses if dose.preferred is not None and times[dose.label] == dose.preferred
    )
    return Solution(
        problem=problem,
        system=system,
        feasible=True,
        times=times,
        earliest=earliest,
        latest=latest,
        slack=slack,
        preferences_met=preferences_met,
        violations=violations,
        warnings=warnings,
        cycle=(),
        cycle_weight=0,
        core=(),
        relaxations=(),
        combined=(),
        max_relax=max_relax,
    )


def validate_schedule(problem: Problem, times: dict[str, int]) -> list[str]:
    """Check a schedule against every rule of the problem, independently of the graph."""
    violations: list[str] = []
    for dose in problem.doses:
        minute = times.get(dose.label)
        if minute is None:
            violations.append(f"{dose.label}: no time assigned")
        elif not dose.start <= minute <= dose.end:
            violations.append(
                f"{dose.label}: {format_time(minute)} is outside {format_time(dose.start)}-{format_time(dose.end)}"
            )
    for med in problem.medications:
        if med.min_gap is None:
            continue
        for earlier, later in zip(med.doses, med.doses[1:]):
            gap = times[later.label] - times[earlier.label]
            if gap < med.min_gap:
                violations.append(
                    f"{earlier.label} -> {later.label}: {gap}m apart, needs {med.min_gap}m"
                )
    for rule in problem.gaps:
        before = problem.medication(rule.before)
        after = problem.medication(rule.after)
        if before is None or after is None:  # pragma: no cover
            continue
        for before_dose in before.doses:
            for after_dose in after.doses:
                gap = times[after_dose.label] - times[before_dose.label]
                if gap < rule.minutes:
                    violations.append(
                        f"{before_dose.label} -> {after_dose.label}: {gap}m apart, needs {rule.minutes}m"
                    )
    for rule in problem.food:
        med = problem.medication(rule.med)
        if med is None:  # pragma: no cover
            continue
        event = problem.events[rule.event]
        for dose in med.doses:
            minute = times[dose.label]
            if rule.relation == "before" and minute > event - rule.minutes:
                violations.append(f"{dose.label}: {format_time(minute)} is less than {rule.minutes}m before {rule.event}")
            if rule.relation == "after" and minute < event + rule.minutes:
                violations.append(f"{dose.label}: {format_time(minute)} is less than {rule.minutes}m after {rule.event}")
    return violations


def _value(minutes: int | None) -> int:
    if minutes is None:  # pragma: no cover - every dose has a window bound
        raise ValueError("dose not reachable from the clock")
    return minutes


def _align_preferences(times: dict[str, int], latest: dict[str, int], problem: Problem) -> dict[str, int]:
    """Move doses toward their preferred time, keeping the schedule valid at every step."""
    for dose in problem.doses:
        if dose.preferred is None:
            continue
        target = min(max(dose.preferred, times[dose.label]), latest[dose.label])
        if target == times[dose.label]:
            continue
        trial = {**times, dose.label: target}
        if not validate_schedule(problem, trial):
            times = trial
    return times


def _warnings(problem: Problem, times: dict[str, int], slack: dict[str, int]) -> list[str]:
    warnings: list[str] = []
    wake, sleep = problem.wake, problem.sleep
    if wake is not None and sleep is not None and wake < sleep:
        for dose in problem.doses:
            minute = times[dose.label]
            if not wake <= minute <= sleep:
                warnings.append(
                    f"{dose.label} at {format_time(minute)} is outside waking hours "
                    f"{format_time(wake)}-{format_time(sleep)}"
                )
    for dose in problem.doses:
        if slack.get(dose.label) == 0:
            warnings.append(f"{dose.label} is pinned at {format_time(times[dose.label])} (no slack)")
    return warnings


def _infeasible(problem: Problem, system: System, max_relax: int) -> Solution:
    cycle = positive_cycle(system.node_count(), system.edges)
    core = _minimal_core(system)
    relaxations = _single_relaxations(system, max_relax)
    combined = _greedy_relaxations(system, max_relax) if not relaxations else ()
    return Solution(
        problem=problem,
        system=system,
        feasible=False,
        times={},
        earliest={},
        latest={},
        slack={},
        preferences_met=0,
        violations=[],
        warnings=[],
        cycle=cycle,
        cycle_weight=sum(edge.weight for edge in cycle),
        core=core,
        relaxations=relaxations,
        combined=combined,
        max_relax=max_relax,
    )


def _edges_with(system: System, relax: dict[str, tuple[RelaxOption, int]]) -> list[Edge]:
    edges: list[Edge] = []
    for constraint in system.constraints:
        entry = relax.get(constraint.cid)
        for edge in constraint.edges:
            if entry is not None and edge in entry[0].edges:
                edges.append(Edge(edge.src, edge.dst, edge.weight - entry[1], edge.label))
            else:
                edges.append(edge)
    return edges


def _min_delta(
    system: System,
    relax: dict[str, tuple[RelaxOption, int]],
    constraint: Constraint,
    option: RelaxOption,
    budget: int,
) -> int | None:
    """Smallest ``delta`` that restores feasibility, or ``None`` inside the budget."""
    if budget <= 0:
        return 0 if is_feasible(system.node_count(), _edges_with(system, {**relax, constraint.cid: (option, 0)})) else None

    def ok(delta: int) -> bool:
        return is_feasible(system.node_count(), _edges_with(system, {**relax, constraint.cid: (option, delta)}))

    if not ok(budget):
        return None
    if ok(0):
        return 0
    low, high = 0, budget
    while low + 1 < high:
        middle = (low + high) // 2
        if ok(middle):
            high = middle
        else:
            low = middle
    return high


def _minimal_core(system: System) -> tuple[Constraint, ...]:
    """Deletion-based minimal unsatisfiable subset of constraint groups."""
    kept = list(system.constraints)
    for constraint in system.constraints:
        trial = [entry for entry in kept if entry.cid != constraint.cid]
        if not is_feasible(system.node_count(), [edge for entry in trial for edge in entry.edges]):
            kept = trial
    return tuple(kept)


def _single_relaxations(system: System, max_relax: int) -> tuple[Relaxation, ...]:
    found: list[Relaxation] = []
    for constraint in system.constraints:
        for option in constraint.options:
            delta = _min_delta(system, {}, constraint, option, max_relax)
            if delta is None or delta == 0:
                continue
            found.append(Relaxation(cid=constraint.cid, kind=option.kind, delta=delta, text=option.describe(delta)))
    found.sort(key=lambda item: (item.delta, item.cid, item.kind))
    return tuple(found)


def _greedy_relaxations(system: System, max_relax: int) -> tuple[Relaxation, ...]:
    """Conflict-driven repair, used only when no single change is enough.

    Each round reads the current positive cycle and relaxes, by the smallest
    possible amount, the one constraint that can shorten that cycle the most
    cheaply. This is a greedy repair, not a minimal total: the report says so.
    """
    relax: dict[str, tuple[RelaxOption, int]] = {}
    applied: list[Relaxation] = []
    budget = max_relax
    for _ in range(len(system.constraints) * 2):
        edges = _edges_with(system, relax)
        if is_feasible(system.node_count(), edges):
            return tuple(applied)
        cycle = positive_cycle(system.node_count(), edges)
        if not cycle:
            break
        weight = sum(edge.weight for edge in cycle)
        best: tuple[int, Constraint, RelaxOption] | None = None
        for constraint in system.constraints:
            if constraint.cid in relax:
                continue
            for option in constraint.options:
                hits = sum(1 for edge in cycle if edge in option.edges)
                if hits == 0:
                    continue
                delta = -(-weight // hits)
                if delta <= 0 or delta > budget:
                    continue
                if best is None or delta < best[0]:
                    best = (delta, constraint, option)
        if best is None:
            break
        delta, constraint, option = best
        relax[constraint.cid] = (option, delta)
        applied.append(
            Relaxation(cid=constraint.cid, kind=option.kind, delta=delta, text=option.describe(delta))
        )
        budget -= delta
        if budget <= 0:
            break
    return tuple(applied) if is_feasible(system.node_count(), _edges_with(system, relax)) else ()
