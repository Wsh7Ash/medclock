from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, "-m", "medclock", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def regimen(
    medications: list[dict],
    gaps: list[dict] | None = None,
    events: dict | None = None,
    wake: str | None = None,
    sleep: str | None = None,
    name: str = "test-regimen",
) -> dict:
    payload: dict = {"name": name, "medications": medications}
    if gaps:
        payload["gaps"] = gaps
    if events:
        payload["events"] = events
    if wake:
        payload["wake"] = wake
    if sleep:
        payload["sleep"] = sleep
    return payload


def med(name: str, start: str, end: str, **extra) -> dict:
    entry = {"name": name, "window": {"start": start, "end": end}}
    entry.update(extra)
    return entry


def write_problem(tmp_path: Path, payload: dict, filename: str = "regimen.json") -> Path:
    path = tmp_path / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
