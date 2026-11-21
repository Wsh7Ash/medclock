"""Translate a validated problem into difference constraints.

Node ``ZERO`` is the clock itself (``t = 0``); every other node is one dose.
``Edge(src, dst, w)`` means ``t(dst) - t(src) >= w``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .model import Problem
from .stp import Edge
from .timeutil import DAY_MINUTES, format_span, format_time, to_clock

ZERO = "clock"


def _clock(minutes: int) -> str:
    """Format a possibly out-of-day clock value without raising."""
    if 0 <= minutes <= DAY_MINUTES:
        return format_time(minutes)
    return f"{to_clock(minutes)} from midnight"


@dataclass(frozen=True)
class RelaxOption:
    """One way to weaken a constraint by ``delta`` minutes."""

    kind: str
    edges: tuple[Edge, ...]
    describe: Callable[[int], str]


@dataclass(frozen=True)
class Constraint:
    cid: str
    kind: str
    text: str
    edges: tuple[Edge, ...]
    options: tuple[RelaxOption, ...]


@dataclass(frozen=True)
class System:
    nodes: tuple[str, ...]
    constraints: tuple[Constraint, ...]

    def index(self, name: str) -> int:
        return self.nodes.index(name)

    @property
    def edges(self) -> tuple[Edge, ...]:
        return tuple(edge for constraint in self.constraints for edge in constraint.edges)

    def node_count(self) -> int:
        return len(self.nodes)


class _Builder:
    def __init__(self) -> None:
        self.nodes: list[str] = [ZERO]
        self.constraints: list[Constraint] = []

    def node(self, name: str) -> int:
        if name not in self.nodes:
            self.nodes.append(name)
        return self.nodes.index(name)

    def add(
        self,
        cid: str,
        kind: str,
        text: str,
        edges: list[Edge],
        options: tuple[RelaxOption, ...],
    ) -> None:
        self.constraints.append(Constraint(cid=cid, kind=kind, text=text, edges=tuple(edges), options=options))


def build_system(problem: Problem) -> System:
    """Build the constraint system for a problem."""
    builder = _Builder()

    for dose in problem.doses:
        lower = Edge(0, builder.node(dose.label), dose.start, f"{dose.label} is at or after {format_time(dose.start)} (window)")
        upper = Edge(
            builder.node(dose.label),
            0,
            -dose.end,
            f"{dose.label} is at or before {format_time(dose.end)} (window)",
        )
        options = (
            RelaxOption(
                "open-earlier",
                (lower,),
                lambda delta, dose=dose: (
                    f"open the {dose.label} window earlier: {format_time(dose.start)} -> {_clock(dose.start - delta)}"
                ),
            ),
            RelaxOption(
                "extend-later",
                (upper,),
                lambda delta, dose=dose: (
                    f"close the {dose.label} window later: {format_time(dose.end)} -> {_clock(dose.end + delta)}"
                ),
            ),
        )
        builder.add(
            f"window:{dose.label}",
            "window",
            f"{dose.label} within {dose.window}",
            [lower, upper],
            options,
        )

    for med in problem.medications:
        if med.min_gap is None or len(med.doses) < 2:
            continue
        span = format_span(med.min_gap)
        edges = [
            Edge(
                builder.node(earlier.label),
                builder.node(later.label),
                med.min_gap,
                f"{later.label} is at least {span} after {earlier.label} (same medication)",
            )
            for earlier, later in zip(med.doses, med.doses[1:])
        ]
        builder.add(
            f"interval:{med.name}",
            "interval",
            f"{med.name} doses at least {span} apart",
            edges,
            (
                RelaxOption(
                    "shorten",
                    tuple(edges),
                    lambda delta, med=med: (
                        f"shorten the {med.name} interval: {format_span(med.min_gap or 0)} -> "
                        f"{format_span(max((med.min_gap or 0) - delta, 0))}"
                    ),
                ),
            ),
        )

    for gap in problem.gaps:
        before = problem.medication(gap.before)
        after = problem.medication(gap.after)
        if before is None or after is None:  # pragma: no cover - the loader rejects this
            raise ValueError(f"unknown medication in gap {gap.cid}")
        span = format_span(gap.minutes)
        suffix = f" ({gap.reason})" if gap.reason else ""
        edges = [
            Edge(
                builder.node(before_dose.label),
                builder.node(after_dose.label),
                gap.minutes,
                f"{after_dose.label} is at least {span} after {before_dose.label}{suffix}",
            )
            for before_dose in before.doses
            for after_dose in after.doses
        ]
        builder.add(
            gap.cid,
            "gap",
            gap.text,
            edges,
            (
                RelaxOption(
                    "shorten",
                    tuple(edges),
                    lambda delta, gap=gap: (
                        f"shorten {gap.before}->{gap.after}: {format_span(gap.minutes)} -> "
                        f"{format_span(max(gap.minutes - delta, 0))}"
                    ),
                ),
            ),
        )

    for rule in problem.food:
        med = problem.medication(rule.med)
        if med is None:  # pragma: no cover - the loader rejects this
            raise ValueError(f"unknown medication in food rule {rule.cid}")
        event_minute = problem.events[rule.event]
        event_clock = format_time(event_minute)
        span = format_span(rule.minutes)
        edges: list[Edge] = []
        for dose in med.doses:
            index = builder.node(dose.label)
            if rule.relation == "before":
                edges.append(
                    Edge(
                        index,
                        0,
                        -(event_minute - rule.minutes),
                        f"{dose.label} is at least {span} before {rule.event} at {event_clock}",
                    )
                )
            else:
                edges.append(
                    Edge(
                        0,
                        index,
                        event_minute + rule.minutes,
                        f"{dose.label} is at least {span} after {rule.event} at {event_clock}",
                    )
                )
        builder.add(
            rule.cid,
            "food",
            rule.text,
            edges,
            (
                RelaxOption(
                    "shorten",
                    tuple(edges),
                    lambda delta, rule=rule: (
                        f"loosen {rule.med} {rule.relation} {rule.event}: {format_span(rule.minutes)} -> "
                        f"{format_span(max(rule.minutes - delta, 0))}"
                    ),
                ),
            ),
        )

    return System(nodes=tuple(builder.nodes), constraints=tuple(builder.constraints))
