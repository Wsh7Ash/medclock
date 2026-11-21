# medclock

Check whether a medication regimen has a feasible schedule - and when it does
not, get a proof you can re-add by hand plus the exact number of minutes each fix
costs.

```text
$ medclock check fixtures/pinch.json
medclock - medication timing feasibility, with a proof when there is none
problem: pinch.json (4 medication(s), 4 dose(s), 7 constraint group(s))
day 07:00-22:00; events: breakfast 08:00, lunch 13:00, dinner 19:00

SOLVER   infeasible - no assignment of the 4 dose(s) satisfies all 7 group(s)

INFEASIBILITY PROOF (positive cycle, total +2h)
  t(levothyroxine#1) >= t(clock) +7h      levothyroxine#1 is at or after 07:00 (window)
  t(calcium#1) >= t(levothyroxine#1) +4h  calcium#1 is at least 4h after levothyroxine#1 (calcium binds levothyroxine)
  t(clock) >= t(calcium#1) -9h            calcium#1 is at or before 09:00 (window)
  => t(clock) >= t(clock) + 2h, which has no solution

MINIMAL UNSATISFIABLE CORE (3 of 7 groups; dropping any one restores feasibility)
  window:levothyroxine#1      levothyroxine#1 within 07:00-07:30
  window:calcium#1            calcium#1 within 08:00-09:00
  gap:levothyroxine->calcium  calcium at least 4h after levothyroxine (calcium binds levothyroxine)
  (4 other group(s) do not contribute to this conflict)

RELAXATIONS (one change, fewest minutes first)
  2h  shorten levothyroxine->calcium: 4h -> 2h
  2h  close the calcium#1 window later: 09:00 -> 11:00
  2h  open the levothyroxine#1 window earlier: 07:00 -> 05:00
  cheapest single relaxation: 2h
  no single change in 4 other group(s) removes the conflict within 24h
```

## The problem

Timing rules are simple one at a time and entangled in practice: levothyroxine
on an empty stomach at least 30 minutes before breakfast, calcium four hours
later, iron two hours before the calcium, metformin twice a day at least eight
hours apart. Change one dose and three other rules move with it.

Reminder apps store the times you already chose. Guideline checkers look at each
rule alone. Neither answers the question that actually blocks a plan: *can these
doses all be placed inside their windows at all, and if not, which three rules
collide and what is the smallest change that fixes it?*

medclock answers that by treating every rule as a difference constraint
(`t(b) >= t(a) + minutes`), which makes the whole regimen a simple temporal
problem:

1. Parse the regimen: doses with allowed clock windows, same-medication
   intervals, ordered absorption gaps, meal-relative rules.
2. Build the constraint graph, with the clock (`t = 0`) as the reference node.
3. Find the earliest feasible times, or a **positive cycle** - a loop of lower
   bounds whose weights sum to a positive number, which is a contradiction you
   can verify by adding three numbers.
4. If unsatisfiable, shrink the rules to a **minimal unsatisfiable core** and
   price every single-change repair in minutes by bisection.
5. Re-check the resulting schedule against the original rules with a separate
   checker, never against the graph that produced it.

## Features

- Offline, deterministic, standard library only: no solver, no service, no data.
- Windows per dose, same-medication intervals, ordered absorption gaps and
  meal-relative rules (`before`/`after` a named event).
- Feasible output: earliest schedule, preferences aligned where slack allows,
  per-dose slack, and a direct re-check of every rule.
- Infeasible output: positive-cycle certificate, minimal core, minimal minutes
  per single relaxation, and a conflict-driven combined repair when no single
  change is enough.
- Slack reporting in clock terms (`30m`, `1h30m`), so you can see which dose is
  pinned.
- Warnings for doses outside waking hours and for pinned doses.
- Text and `--json` output, `--fail-on infeasible|warning|none`, `--max-relax`.
- ASCII-only reports, so a Windows pipe cannot crash on an arrow.

## Quick start

```shell
git clone https://github.com/Wsh7Ash/medclock.git
cd medclock
PYTHONPATH=src python -m medclock check fixtures/morning.json
```

Observed output (see `results/demo.txt`):

```text
SCHEDULE (earliest feasible, preferences aligned)
time  dose             window       slack  preference
06:30  levothyroxine#1  06:30-07:00    30m  -
07:30  metformin#1      07:30-09:00  1h30m  -
07:45  aspirin#1        07:30-08:30    45m  -
10:30  iron#1           10:00-11:00    30m  10:15
12:30  calcium#1        12:30-13:30     1h  -
19:30  metformin#2      18:30-20:00    30m  19:30
20:00  calcium#2        20:00-21:00     1h  -

constraint groups: 13/13 checked directly against the problem - all groups satisfied

SUMMARY 7 dose(s) scheduled, 1 preference(s) met, 0 warning(s)
GATE     feasible -> PASS
```

`iron#1` asks for 10:15 but the levothyroxine-to-iron gap plus the 10:00 window
opening put the earliest possible time at 10:30, so the scheduler reports 10:30
rather than quietly violating the gap. `metformin#2` has room and moves from
18:30 to its preferred 19:30.

## Install

Python 3.12+, no runtime dependencies.

```shell
python -m venv .venv
source .venv/bin/activate      # Windows: .venv/Scripts/activate
pip install -e .
medclock check regimen.json
```

Or without installing:

```shell
PYTHONPATH=src python -m medclock check regimen.json
```

## Usage

```shell
medclock check PROBLEM [--json] [--fail-on infeasible|warning|none] [--max-relax MINUTES]
```

| Flag | Meaning |
|---|---|
| `PROBLEM` | regimen JSON file |
| `--json` | machine-readable report |
| `--fail-on` | `infeasible` (default), `warning`, `none` |
| `--max-relax` | largest single relaxation to price, in minutes (default 1440) |

Exit codes: `0` gate passed, `1` gate failed, `2` usage or input error.

### Input shape

```json
{
  "name": "morning-routine",
  "wake": "06:30",
  "sleep": "22:30",
  "events": { "breakfast": "07:30" },
  "medications": [
    {
      "name": "levothyroxine",
      "window": { "start": "06:30", "end": "07:00" },
      "food": [
        { "event": "breakfast", "relation": "before", "minutes": "30m",
          "reason": "empty stomach" }
      ]
    },
    {
      "name": "metformin",
      "windows": [
        { "start": "07:30", "end": "09:00" },
        { "start": "18:30", "end": "20:00" }
      ],
      "min_gap": "8h",
      "preferred": [null, "19:30"]
    }
  ],
  "gaps": [
    { "before": "levothyroxine", "after": "calcium", "minutes": "4h",
      "reason": "calcium binds levothyroxine" }
  ]
}
```

Full field reference: `docs/USAGE.md`.

### In CI

```yaml
- name: Regimen feasibility gate
  run: |
    pip install -e .
    medclock check regimens/discharge.json --fail-on infeasible
```

## Architecture

```text
regimen.json -> model.py (validate, doses, rules)
             -> constraints.py (difference-constraint edges per rule group)
             -> stp.py (longest paths, positive-cycle certificate, latest times)
             -> solve.py (schedule, preference alignment, core, relaxations)
             -> render.py (text | JSON) -> cli.py (gate)
```

See `docs/ARCHITECTURE.md` for the algorithms and invariants.

## Testing

```shell
pip install -e ".[dev]"
python -m pytest tests -q     # 120 tests
python scripts/demo.py
```

The suite checks the engine against hand-computed systems, re-validates every
produced schedule against the original rules, asserts the core is minimal
(removing any group in it restores feasibility), and asserts each reported
relaxation cost is both necessary (one minute less still fails) and sufficient.

## Limitations

- One day, `00:00`-`24:00`. Multi-day regimens and rolling 24-hour totals are not
  modelled.
- Every rule is a difference constraint, so an interaction must state an order
  (`before`/`after`). "Never within four hours in either direction" cannot be
  expressed; declare the direction you can defend.
- A `gap` applies to every dose pair of the two medications, not to a chosen
  pair. Split medications when only specific doses interact.
- Preferences are aligned greedily and validated, not optimised globally.
- Relaxation costs are exact per single constraint; the combined repair is
  cheapest-per-conflict, not a minimal total.
- `wake`/`sleep` produce warnings only; they are not constraints.
- No dose amounts, daily maxima, as-needed logic or pharmacokinetics.
- This is a scheduling calculator, not medical advice. The fixtures are
  synthetic; check any real regimen with a pharmacist.

## Roadmap

- Multi-day horizon with rolling 24-hour dose totals.
- Named dose pairs (`"levothyroxine#1"`) in gaps for finer interactions.
- `explain --constraint CID` for a single-rule drill-down.
- Optimal total relaxation via a small integer program in place of greedy repair.

## License

MIT. See `LICENSE`.
