# Project specification

## Purpose

Decide whether a medication regimen can be scheduled inside its stated windows,
and when it cannot, produce (a) a contradiction that a human can verify by
arithmetic and (b) priced options for relaxing it.

## Users

- A clinician or pharmacist checking a discharge plan before printing it.
- A patient-supporter reconciling several prescriptions and meal times.
- A developer embedding a feasibility gate in a care-plan pipeline.

## Scope

In scope:

- doses with one allowed clock window each;
- a minimum interval between consecutive doses of the same medication;
- ordered absorption gaps between two medications (every dose pair);
- doses positioned before or after a named event such as a meal;
- earliest schedule, preference alignment where slack allows, slack per dose;
- proof of infeasibility, minimal unsatisfiable core, priced relaxations;
- text and JSON reports, gate exit codes, deterministic output.

Out of scope:

- dose amounts, maximum daily dose, cumulative toxicity, half-lives;
- as-needed (PRN) dosing, tapering schedules, multi-day horizons;
- time zones, daylight saving, night-shift days that cross midnight;
- clinical recommendations of any kind.

## Input

A JSON object, validated strictly (see `docs/USAGE.md` for the full field list):

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | no | report label |
| `wake`, `sleep` | `HH:MM` | no | waking hours, used for warnings only |
| `events` | object of `HH:MM` | no | named anchors (meals, shifts) |
| `medications` | list | yes | at least one medication |
| `medications[].name` | string | yes | unique |
| `medications[].window` | object | one of | shared window for all doses |
| `medications[].windows` | list | one of | one window per dose |
| `medications[].min_gap` | minutes | no | minimum interval between consecutive doses |
| `medications[].preferred` | list | no | preferred time per dose, inside its window |
| `medications[].food` | list | no | before/after an event, with minutes |
| `gaps` | list | no | ordered `before` -> `after` minimum separation |

Rejected inputs (exit code 2): unknown medication or event names, duplicate
medications or gaps, start not before end, preferred time outside its window,
duplicate medication entries, malformed clock or duration values, unreadable or
invalid JSON.

## Rules and their constraint form

With `t(x)` the minute of dose `x` and `t(clock) = 0`:

| Rule | Difference constraints |
|---|---|
| window `[start, end]` | `t(x) >= start`, `t(clock) >= t(x) - end` |
| interval `g` between consecutive doses | `t(next) >= t(prev) + g` |
| gap `before` -> `after` of `g` | `t(after) >= t(before) + g` for every dose pair |
| food `before` event at `e` by `m` | `t(clock) >= t(dose) - (e - m)` |
| food `after` event at `e` by `m` | `t(dose) >= e + m` |

## Output

Feasible:

- schedule sorted by time: time, dose, window, slack, preferred time;
- count of rule groups checked and whether any violation was found;
- warnings (outside waking hours, pinned dose);
- summary line and gate verdict.

Infeasible:

- positive-cycle proof: each step as `t(dst) >= t(src) + w`, the total, and the
  conclusion that the start node must exceed itself;
- minimal unsatisfiable core with rule ids and readable texts, plus the number of
  groups that do not contribute;
- single relaxations sorted by minutes, each with the concrete change;
- combined repair when no single change suffices;
- gate verdict.

JSON mirrors the same information under stable keys (see `render_json`).

## Acceptance criteria

| Criterion | Check |
|---|---|
| A produced schedule satisfies every original rule | `validate_schedule` returns no violations; asserted for both fixtures and for the latest-times schedule |
| Reported infeasibility is real | the cycle is a closed loop, sums to a positive number, and every step is an edge of a real rule group |
| The core is minimal | removing any group in the core restores feasibility; asserted |
| A relaxation cost is exact | one minute less still fails, the reported value succeeds; asserted |
| Output is deterministic | repeated solves produce equal schedules |
| Reports are ASCII | demo asserts `encode("ascii")` for all captured output |
| Exit codes are stable | `0` pass, `1` gate fail, `2` input error; CLI tests cover each |
| No dependencies | `pyproject.toml` has an empty runtime dependency list |

## Non-goals

The tool never proposes a clinical change. It reports arithmetic: which rules
collide, and how many minutes separate them from feasibility. Choosing what to
change is the prescriber's decision.
