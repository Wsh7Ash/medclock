from __future__ import annotations

import json

import pytest

from medclock.model import load
from medclock.render import failed, gate_label, render_json, render_text
from medclock.solve import solve
from conftest import FIXTURES


@pytest.fixture(scope="module")
def morning_text() -> str:
    return render_text(solve(load(FIXTURES / "morning.json")))


@pytest.fixture(scope="module")
def pinch_text() -> str:
    return render_text(solve(load(FIXTURES / "pinch.json")))


def test_feasible_report_sections(morning_text: str) -> None:
    assert morning_text.startswith("medclock - medication timing feasibility")
    assert "SCHEDULE (earliest feasible, preferences aligned)" in morning_text
    assert "constraint groups: 13/13 checked directly against the problem" in morning_text
    assert "SUMMARY 7 dose(s) scheduled, 1 preference(s) met, 0 warning(s)" in morning_text
    assert "GATE     feasible -> PASS" in morning_text


def test_schedule_rows_are_sorted_by_time(morning_text: str) -> None:
    times = [line[:5] for line in morning_text.splitlines() if line[:2].isdigit() and line[2] == ":"]
    assert times == sorted(times)
    assert times[0] == "06:30"


def test_infeasible_report_sections(pinch_text: str) -> None:
    assert "SOLVER   infeasible" in pinch_text
    assert "INFEASIBILITY PROOF (positive cycle, total +2h)" in pinch_text
    assert "MINIMAL UNSATISFIABLE CORE (3 of 7 groups" in pinch_text
    assert "dropping any one restores feasibility" in pinch_text
    assert "(4 other group(s) do not contribute to this conflict)" in pinch_text
    assert "RELAXATIONS (one change, fewest minutes first)" in pinch_text
    assert "GATE     infeasible -> FAIL" in pinch_text


def test_proof_prints_checkable_relations(pinch_text: str) -> None:
    assert "t(calcium#1) >= t(levothyroxine#1) +4h" in pinch_text
    assert "which has no solution" in pinch_text


def test_reports_are_ascii(morning_text: str, pinch_text: str) -> None:
    morning_text.encode("ascii")
    pinch_text.encode("ascii")


def test_json_feasible_payload_keys() -> None:
    payload = json.loads(render_json(solve(load(FIXTURES / "morning.json"))))
    assert payload["tool"] == "medclock"
    assert payload["problem"]["constraint_groups"] == 13
    assert payload["constraints"]["violations"] == []
    assert payload["warnings"] == []
    assert payload["diagnostics"] is None


def test_json_infeasible_payload_keys() -> None:
    payload = json.loads(render_json(solve(load(FIXTURES / "pinch.json"))))
    diagnostics = payload["diagnostics"]
    assert diagnostics["core_is_minimal"] is True
    assert diagnostics["dropped_groups"] == 4
    assert diagnostics["combined"] == []
    assert diagnostics["cycle"]["steps"][0]["relation"].startswith("t(")


def test_gate_helpers() -> None:
    morning = solve(load(FIXTURES / "morning.json"))
    pinch = solve(load(FIXTURES / "pinch.json"))
    assert gate_label(morning, "infeasible") == "feasible"
    assert gate_label(pinch, "infeasible") == "infeasible"
    assert failed(morning, "infeasible") is False
    assert failed(pinch, "none") is False
    assert failed(pinch, "warning") is True
