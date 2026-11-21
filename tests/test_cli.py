from __future__ import annotations

import json
from pathlib import Path

from conftest import FIXTURES, med, regimen, run_cli, write_problem


def test_morning_exits_zero() -> None:
    proc = run_cli("check", "fixtures/morning.json")
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""
    assert "SCHEDULE" in proc.stdout
    assert "GATE     feasible -> PASS" in proc.stdout


def test_pinch_exits_one_and_explains() -> None:
    proc = run_cli("check", "fixtures/pinch.json")
    assert proc.returncode == 1
    assert "INFEASIBILITY PROOF" in proc.stdout
    assert "MINIMAL UNSATISFIABLE CORE (3 of 7 groups" in proc.stdout
    assert "cheapest single relaxation: 2h" in proc.stdout
    assert "GATE     infeasible -> FAIL" in proc.stdout


def test_fail_on_none_exits_zero() -> None:
    proc = run_cli("check", "fixtures/pinch.json", "--fail-on", "none")
    assert proc.returncode == 0
    assert "INFEASIBILITY PROOF" in proc.stdout
    assert "GATE     infeasible -> PASS" in proc.stdout


def test_json_feasible_report() -> None:
    proc = run_cli("check", "fixtures/morning.json", "--json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["feasible"] is True
    assert payload["gate"] == "feasible"
    assert payload["diagnostics"] is None
    assert payload["constraints"]["groups"] == 13
    assert len(payload["schedule"]) == 7
    assert [row["time"] for row in payload["schedule"]] == sorted(row["time"] for row in payload["schedule"])
    metformin = next(row for row in payload["schedule"] if row["dose"] == "metformin#2")
    assert metformin["time"] == "19:30"
    assert metformin["preference_met"] is True


def test_json_infeasible_report() -> None:
    payload = json.loads(run_cli("check", "fixtures/pinch.json", "--json").stdout)
    assert payload["feasible"] is False
    assert payload["gate"] == "infeasible"
    assert payload["schedule"] == []
    diagnostics = payload["diagnostics"]
    assert diagnostics["cycle"]["weight_minutes"] == 120
    assert len(diagnostics["cycle"]["steps"]) >= 3
    assert len(diagnostics["core"]) == 3
    assert diagnostics["core_is_minimal"] is True
    assert len(diagnostics["relaxations"]) == 3
    assert diagnostics["max_relax_minutes"] == 1440


def test_output_is_ascii() -> None:
    for args in (("check", "fixtures/morning.json"), ("check", "fixtures/pinch.json")):
        proc = run_cli(*args)
        proc.stdout.encode("ascii")
        proc.stderr.encode("ascii")


def test_missing_file_exits_two(tmp_path: Path) -> None:
    proc = run_cli("check", str(tmp_path / "nope.json"))
    assert proc.returncode == 2
    assert "cannot read" in proc.stderr
    assert proc.stdout == ""


def test_invalid_json_exits_two(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    proc = run_cli("check", str(path))
    assert proc.returncode == 2
    assert "invalid JSON" in proc.stderr


def test_invalid_problem_exits_two(tmp_path: Path) -> None:
    path = write_problem(tmp_path, {"medications": []})
    proc = run_cli("check", str(path))
    assert proc.returncode == 2
    assert "non-empty list" in proc.stderr


def test_negative_max_relax_exits_two() -> None:
    proc = run_cli("check", "fixtures/morning.json", "--max-relax", "-5")
    assert proc.returncode == 2
    assert "--max-relax" in proc.stderr


def test_fail_on_warning(tmp_path: Path) -> None:
    path = write_problem(tmp_path, regimen([med("a", "22:30", "23:00")], wake="07:00", sleep="22:00"))
    assert run_cli("check", str(path)).returncode == 0
    proc = run_cli("check", str(path), "--fail-on", "warning")
    assert proc.returncode == 1
    assert "WARNINGS" in proc.stdout
    assert "GATE     warning -> FAIL" in proc.stdout


def test_fixture_paths_exist() -> None:
    assert (FIXTURES / "morning.json").is_file()
    assert (FIXTURES / "pinch.json").is_file()
