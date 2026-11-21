"""Text and JSON reports."""

from __future__ import annotations

import json

from .solve import Relaxation, Solution
from .timeutil import format_span, format_time, to_clock

FAIL_ON = ("infeasible", "warning", "none")


def failed(solution: Solution, fail_on: str) -> bool:
    if fail_on == "none":
        return False
    if fail_on == "warning":
        return (not solution.feasible) or bool(solution.warnings)
    return not solution.feasible


def gate_label(solution: Solution, fail_on: str) -> str:
    if not solution.feasible:
        return "infeasible"
    return "warning" if solution.warnings else "feasible"


def render_text(solution: Solution, fail_on: str = "infeasible") -> str:
    problem = solution.problem
    lines: list[str] = [
        "medclock - medication timing feasibility, with a proof when there is none",
        (
            f"problem: {problem.source} ({len(problem.medications)} medication(s), "
            f"{len(problem.doses)} dose(s), {problem.constraint_groups} constraint group(s))"
        ),
    ]
    day: list[str] = []
    if problem.wake is not None and problem.sleep is not None:
        day.append(f"day {format_time(problem.wake)}-{format_time(problem.sleep)}")
    if problem.events:
        day.append("events: " + ", ".join(f"{name} {format_time(minute)}" for name, minute in problem.events.items()))
    if day:
        lines.append("; ".join(day))
    lines.append("")

    if solution.feasible:
        lines.extend(_schedule_lines(solution))
    else:
        lines.extend(_diagnostic_lines(solution))

    if solution.warnings:
        lines.append("")
        lines.append("WARNINGS")
        lines.extend(f"- {warning}" for warning in solution.warnings)

    lines.append("")
    if solution.feasible:
        lines.append(
            f"SUMMARY {len(problem.doses)} dose(s) scheduled, {solution.preferences_met} preference(s) met, "
            f"{len(solution.warnings)} warning(s)"
        )
    else:
        cheapest = solution.relaxations[0].delta if solution.relaxations else None
        cost = f"{format_span(cheapest)}" if cheapest is not None else "none within budget"
        lines.append(
            f"SUMMARY infeasible; core of {len(solution.core)} group(s); cheapest single relaxation: {cost}"
        )
    verdict = "PASS" if not failed(solution, fail_on) else "FAIL"
    lines.append(f"GATE     {gate_label(solution, fail_on)} -> {verdict}")
    return "\n".join(lines) + "\n"


def _schedule_lines(solution: Solution) -> list[str]:
    problem = solution.problem
    rows = []
    for dose in problem.doses:
        preferred = "" if dose.preferred is None else format_time(dose.preferred)
        rows.append(
            (
                solution.times[dose.label],
                dose.label,
                dose.window,
                format_span(solution.slack[dose.label]),
                preferred,
            )
        )
    rows.sort(key=lambda row: (row[0], row[1]))
    width_dose = max([len("dose")] + [len(row[1]) for row in rows])
    width_window = max([len("window")] + [len(row[2]) for row in rows])
    width_slack = max([len("slack")] + [len(row[3]) for row in rows])

    lines = ["SCHEDULE (earliest feasible, preferences aligned)"]
    lines.append(
        f"{'time':4s}  {'dose':{width_dose}s}  {'window':{width_window}s}  {'slack':>{width_slack}s}  preference"
    )
    for minute, label, window, slack, preferred in rows:
        lines.append(
            f"{format_time(minute):4s}  {label:{width_dose}s}  {window:{width_window}s}  "
            f"{slack:>{width_slack}s}  {preferred or '-'}"
        )
    total = len(solution.system.constraints)
    lines.append("")
    checked = "all groups satisfied" if not solution.violations else f"{len(solution.violations)} violation(s)"
    lines.append(f"constraint groups: {total}/{total} checked directly against the problem - {checked}")
    return lines


def _diagnostic_lines(solution: Solution) -> list[str]:
    names = solution.system.nodes
    lines = [
        f"SOLVER   infeasible - no assignment of the {len(solution.problem.doses)} dose(s) "
        f"satisfies all {len(solution.system.constraints)} group(s)",
        "",
    ]
    if solution.cycle:
        lines.append(f"INFEASIBILITY PROOF (positive cycle, total {to_clock(solution.cycle_weight)})")
        relations = [_relation(edge, names) for edge in solution.cycle]
        width = max(len(relation) for relation in relations)
        for relation, edge in zip(relations, solution.cycle):
            lines.append(f"  {relation:{width}s}  {edge.label}")
        start = names[solution.cycle[0].src]
        lines.append(
            f"  => t({start}) >= t({start}) + {format_span(solution.cycle_weight)}, which has no solution"
        )
        lines.append("")
    else:  # pragma: no cover - defensive
        lines.append("INFEASIBILITY PROOF unavailable (no positive cycle found)")
        lines.append("")

    if solution.core:
        lines.append(
            f"MINIMAL UNSATISFIABLE CORE ({len(solution.core)} of {len(solution.system.constraints)} groups; "
            f"dropping any one restores feasibility)"
        )
        widths = max(len(constraint.cid) for constraint in solution.core)
        for constraint in solution.core:
            lines.append(f"  {constraint.cid:{widths}s}  {constraint.text}")
        if solution.dropped_groups:
            lines.append(f"  ({solution.dropped_groups} other group(s) do not contribute to this conflict)")
        lines.append("")

    if solution.relaxations:
        lines.append("RELAXATIONS (one change, fewest minutes first)")
        width = max(len(format_span(item.delta)) for item in solution.relaxations)
        for item in solution.relaxations:
            lines.append(f"  {format_span(item.delta):>{width}s}  {item.text}")
        lines.append(f"  cheapest single relaxation: {format_span(solution.relaxations[0].delta)}")
        missing = len(solution.system.constraints) - len(solution.relaxations)
        if missing:
            lines.append(f"  no single change in {missing} other group(s) removes the conflict within {format_span(solution.max_relax)}")
    elif solution.combined:
        lines.append("COMBINED RELAXATION (cheapest-first, no single change is enough)")
        total = sum(item.delta for item in solution.combined)
        for item in solution.combined:
            lines.append(f"  {format_span(item.delta):>5s}  {item.text}")
        lines.append(f"  total: {format_span(total)} across {len(solution.combined)} change(s)")
    else:
        lines.append(f"RELAXATIONS none within the {format_span(solution.max_relax)} budget")
    return lines


def _relation(edge, names: tuple[str, ...]) -> str:
    return f"t({names[edge.dst]}) >= t({names[edge.src]}) {to_clock(edge.weight)}"


def render_json(solution: Solution, fail_on: str = "infeasible") -> str:
    problem = solution.problem
    payload: dict = {
        "tool": "medclock",
        "problem": {
            "name": problem.name,
            "source": problem.source,
            "wake": None if problem.wake is None else format_time(problem.wake),
            "sleep": None if problem.sleep is None else format_time(problem.sleep),
            "events": {name: format_time(minute) for name, minute in problem.events.items()},
            "medications": len(problem.medications),
            "doses": len(problem.doses),
            "constraint_groups": problem.constraint_groups,
        },
        "feasible": solution.feasible,
        "gate": gate_label(solution, fail_on),
        "schedule": (
            [
                {
                    "dose": dose.label,
                    "time": format_time(solution.times[dose.label]),
                    "minutes": solution.times[dose.label],
                    "window": dose.window,
                    "slack": format_span(solution.slack[dose.label]),
                    "slack_minutes": solution.slack[dose.label],
                    "preferred": None if dose.preferred is None else format_time(dose.preferred),
                    "preference_met": dose.preferred is not None and solution.times[dose.label] == dose.preferred,
                }
                for dose in sorted(problem.doses, key=lambda item: (solution.times[item.label], item.label))
            ]
            if solution.feasible
            else []
        ),
        "constraints": {
            "groups": len(solution.system.constraints),
            "violations": solution.violations,
        },
        "warnings": solution.warnings,
        "diagnostics": None,
    }
    if not solution.feasible:
        payload["diagnostics"] = {
            "cycle": {
                "weight_minutes": solution.cycle_weight,
                "steps": [
                    {
                        "from": solution.system.nodes[edge.src],
                        "to": solution.system.nodes[edge.dst],
                        "weight_minutes": edge.weight,
                        "relation": _relation(edge, solution.system.nodes),
                        "label": edge.label,
                    }
                    for edge in solution.cycle
                ],
            },
            "core": [{"id": constraint.cid, "kind": constraint.kind, "text": constraint.text} for constraint in solution.core],
            "core_is_minimal": True,
            "dropped_groups": solution.dropped_groups,
            "relaxations": [_relaxation_payload(item) for item in solution.relaxations],
            "combined": [_relaxation_payload(item) for item in solution.combined],
            "max_relax_minutes": solution.max_relax,
        }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _relaxation_payload(item: Relaxation) -> dict:
    return {"id": item.cid, "kind": item.kind, "minutes": item.delta, "text": item.text}
