# Results

## Environment

- OS: Windows (win32), Git Bash
- Runtime: Python 3.14.3
- Dependency manager: none at runtime; pytest for the dev extra

## Validation performed

- install: N/A - standard library only, suite runs with `PYTHONPATH=src`
- build: PASS - `python -m compileall -q src`
- unit tests: PASS - 120 passed
- integration tests: PASS - CLI tests run the package as a subprocess with UTF-8
  pipes, covering exit codes 0/1/2, `--json`, every `--fail-on` value,
  `--max-relax` and the input-error paths
- lint: N/A - no linter configured
- type check: N/A - no type checker configured
- demo run: PASS - `python scripts/demo.py` exited 0 with
  `expectations met: True`
- secret scan: PASS - no credentials, keys or tokens in the tree

## Commands executed

```shell
PYTHONPATH=src python -m pytest tests -q
python -m compileall -q src
python scripts/demo.py
```

## Observed result

```text
120 passed in 4.79s

morning: exit code 0 (expected 0)
pinch: exit code 1 (expected 1)
pinch-without-gate: exit code 0 (expected 0)
morning feasible: True
morning schedule rows: 7 (expected 7)
pinch cycle weight: 120 (expected 120)
pinch core groups: 3 (expected 3)
pinch single relaxations: 3 (expected 3)
ascii only: True
exit codes as expected: True
expectations met: True
```

`results/demo.txt` holds the full reports. On `fixtures/morning.json`:

- 7 doses across 5 medications and 13 rule groups;
- `levothyroxine#1` at 06:30 with 30m slack (the 07:00 window close and the
  30-minute empty-stomach rule both bind);
- `iron#1` at 10:30, not the requested 10:15, because 06:30 + 4h is the earliest
  the gap allows; slack 30m to the 11:00 window close;
- `calcium#1` at 12:30, which is exactly 2h after `iron#1`;
- `metformin#2` moved from its earliest 18:30 to the preferred 19:30, with 30m
  slack left;
- no warnings: every dose is inside 06:30-22:30 and no dose has zero slack.

On `fixtures/pinch.json` (infeasible):

- the proof is three bounds: `levothyroxine#1 >= 07:00`, `calcium#1 >=
  levothyroxine#1 + 4h`, `calcium#1 <= 09:00`, totalling +2h;
- the minimal core is those three groups; the other four (the iron gap, the
  metformin window, the empty-stomach rule and the levothyroxine window's upper
  bound) are not required;
- three single changes cost 2h each: shorten the gap to 2h, close the calcium
  window at 11:00, or open the levothyroxine window at 05:00;
- no single change in the other four groups helps within the 1440-minute budget.

## Defects found while building the suite and fixed

1. **Food rules were parsed by a stub and silently dropped.** The first version
   of the loader ended `_food_rules` with `return ()` while the real parser sat
   unused below it, so a `food` block validated clean and then vanished from the
   model. `morning.json` reported 11 groups instead of 13 and the empty-stomach
   rule had no effect. The loader now parses food rules with the medication and
   returns them alongside it; `test_load_morning_fixture` pins the group count.
2. **`parse_span` rejected minute values above 59 without an hour part.**
   `"240m"` raised "minutes part must be below 60", which made the documented
   `"240m"` form unusable while `"4h"` worked. The limit now applies only when an
   hour component is present. Caught by
   `test_parse_span_accepts_minutes_and_durations`.
3. **Combined repair could not start when two independent conflicts existed.**
   The first greedy version asked each candidate change to make the whole system
   feasible, so with two disjoint conflicts no candidate qualified and the tool
   reported no repair at all despite one existing. It now walks the current
   positive cycle and breaks it by the cheapest per-cycle step, repeating until
   feasible. Caught by `test_independent_conflicts_need_a_combined_repair`.
4. **A test helper double-counted the relaxation delta.** The minimality
   assertion added the reported cost to the probe value, so a 119-minute probe
   was applied as 239 minutes and the test failed against correct code. The
   helper now takes an absolute override; the implementation was unchanged and
   the assertions pass at `delta - 1` and `delta`.

## Notes

- `pip install -e .` was not run here; the suite and demo run from source with
  `PYTHONPATH=src`. CI installs with `pip install -e ".[dev]"` on Python 3.12 and
  3.13.
- Both fixtures are synthetic regimens written for the demo. They are not
  clinical guidance and no real patient data is present.
