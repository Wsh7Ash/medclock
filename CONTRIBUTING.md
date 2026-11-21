# Contributing

## Setup

```shell
python -m venv .venv
source .venv/bin/activate      # Windows: .venv/Scripts/activate
pip install -e ".[dev]"
python -m pytest tests -q
```

Python 3.12 or newer. There are no runtime dependencies and adding one needs a
strong reason: the point of the tool is that it runs anywhere with a stock
interpreter.

## Before opening a pull request

```shell
python -m pytest tests -q
python -m compileall -q src
python scripts/demo.py
```

`scripts/demo.py` rewrites `results/demo.txt` and `results/gate.txt`; commit the
new capture only when the output genuinely changed.

## What to keep true

- A produced schedule must pass `validate_schedule` against the original rules.
- An infeasibility report must carry a cycle whose weights sum to a positive
  number and whose steps are edges of real rule groups.
- Every group in a reported core must be required: removing it restores
  feasibility.
- A reported relaxation must be necessary and sufficient (`delta - 1` fails,
  `delta` succeeds).
- Reports stay ASCII-only.
- Solving stays deterministic: no randomness, no wall-clock reads, no unordered
  iteration over sets in output paths.

## Style

- Standard library only; `from __future__ import annotations` at the top.
- Type hints on public functions; dataclasses for value objects.
- Errors for bad input go through `ModelError` so the CLI can exit 2.
- Tests name the behaviour, not the function: `test_gap_pins_iron_after_levothyroxine`.

## Adding a rule kind

1. Add the validated field in `model.py` and include it in `constraint_groups`.
2. Build its edges and one relaxation option in `constraints.py`.
3. Extend `validate_schedule` with a direct check.
4. Extend the proof rendering only if the edge wording needs it.
5. Add tests for: feasible schedule, infeasible proof containing the new group,
   core membership, relaxation cost minimality.

## Reporting a bug

Include the regimen file (redacted), the command, the exit code, and the full
report. If a schedule is wrong, say which rule it violates; the validator output
is the fastest way to localise it.
