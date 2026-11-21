#!/usr/bin/env python3
"""Capture real CLI runs for the README and RESULTS.md."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
EXPECTED = {"morning": 0, "pinch": 1, "pinch-without-gate": 0}


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "medclock", *args],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    cases = [
        ("morning", ("check", "fixtures/morning.json")),
        ("pinch", ("check", "fixtures/pinch.json")),
        ("pinch-without-gate", ("check", "fixtures/pinch.json", "--fail-on", "none")),
    ]
    chunks = ["medclock demo - captured CLI output", ""]
    gates: list[str] = []
    for name, args in cases:
        proc = run(*args)
        chunks.append("$ medclock " + " ".join(args))
        chunks.append(proc.stdout.rstrip())
        if proc.stderr.strip():
            chunks.append("stderr: " + proc.stderr.strip())
        chunks.append(f"exit code: {proc.returncode}")
        chunks.append("")
        gates.append(f"{name}: exit code {proc.returncode} (expected {EXPECTED[name]})")

    morning = json.loads(run("check", "fixtures/morning.json", "--json").stdout)
    pinch = json.loads(run("check", "fixtures/pinch.json", "--json").stdout)
    chunks.append(
        "json feasible: " + json.dumps(
            {
                "feasible": morning["feasible"],
                "doses": len(morning["schedule"]),
                "preferences_met": sum(1 for row in morning["schedule"] if row["preference_met"]),
                "groups": morning["constraints"]["groups"],
            },
            sort_keys=True,
        )
    )
    diagnostics = pinch["diagnostics"]
    chunks.append(
        "json infeasible: " + json.dumps(
            {
                "cycle_minutes": diagnostics["cycle"]["weight_minutes"],
                "core_groups": len(diagnostics["core"]),
                "relaxations": [item["minutes"] for item in diagnostics["relaxations"]],
                "dropped_groups": diagnostics["dropped_groups"],
            },
            sort_keys=True,
        )
    )

    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    (results / "demo.txt").write_text("\n".join(chunks) + "\n", encoding="utf-8")

    ok = all(
        int(line.split("exit code ")[1].split()[0]) == EXPECTED[line.split(":")[0]] for line in gates
    )
    checks = [
        f"morning feasible: {morning['feasible'] is True}",
        f"morning schedule rows: {len(morning['schedule'])} (expected 7)",
        f"pinch cycle weight: {diagnostics['cycle']['weight_minutes']} (expected 120)",
        f"pinch core groups: {len(diagnostics['core'])} (expected 3)",
        f"pinch single relaxations: {len(diagnostics['relaxations'])} (expected 3)",
        "ascii only: " + str(_ascii_only("\n".join(chunks))),
        f"exit codes as expected: {ok}",
    ]
    (results / "gate.txt").write_text("\n".join(gates + checks) + f"\nexpectations met: {ok}\n", encoding="utf-8")
    print("\n".join(gates))
    print("\n".join(checks))
    print("expectations met:", ok)
    return 0 if ok else 1


def _ascii_only(text: str) -> bool:
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
