# Architecture

## Data flow

```text
regimen.json
  -> model.py        strict validation; Dose, Medication, Gap, FoodRule, Problem
  -> constraints.py  one Constraint per rule group, each holding its edges
  -> stp.py          longest paths, latest times, positive-cycle certificate
  -> solve.py        schedule, preference alignment, core, relaxation pricing
  -> render.py       text report or JSON
  -> cli.py          argument parsing, exit codes
```

`model` knows nothing about graphs; `stp` knows nothing about medications (nodes
are integers, edges carry a human label); `solve` is the only module that maps
doses to nodes.

## Constraint encoding

Node `0` is the clock (`t = 0`). Edge `(src, dst, w)` is `t(dst) >= t(src) + w`.

| Group kind | Id | Edges |
|---|---|---|
| `window` | `window:<dose>` | `(0, dose, start)`, `(dose, 0, -end)` |
| `interval` | `interval:<med>` | `(dose[k], dose[k+1], min_gap)` |
| `gap` | `gap:<before>-><after>` | `(before_dose, after_dose, minutes)` for each pair |
| `food` | `food:<med>@<relation>:<event>` | `before`: `(dose, 0, -(event - minutes))`; `after`: `(0, dose, event + minutes)` |

A group is the unit of diagnosis: it can be dropped or relaxed as a whole, so the
reported core and costs refer to rules a person recognises, not to single edges.

## Feasibility

`longest_paths` is Bellman-Ford in the max-plus semiring with the clock as the
source. Every dose has a window, so every node is reachable. The system is
satisfiable exactly when no positive cycle exists; after `n` passes without a
change the distances are the **earliest** feasible times.

Complexity: `O(n * E)` per feasibility test, which is what makes the diagnostic
search affordable (dozens of tests per run on regimens of this size).

## Certificate

When the earliest pass still changes on its last iteration, a positive cycle is
reachable. `positive_cycle` uses Floyd-Warshall in the same semiring and returns
the cycle in walking order; the sum of its weights is `best[i][i] > 0`.

The report renders each edge as `t(dst) >= t(src) + w` and closes with
`t(start) >= t(start) + total`, so the contradiction can be checked by adding the
printed weights. The tests assert that the steps form a closed loop and that the
sum matches.

Floyd-Warshall is `O(n^3)` and is only run when a certificate is requested, never
inside the search.

## Latest times and slack

A path `v -> 0` of weight `W` proves `t(v) <= t(0) - W`, so the latest value is
the negative of the longest path from the clock in the **reversed** graph with the
same weights. Slack per dose is `latest - chosen`. The latest assignment is a
feasible schedule in its own right, and the tests re-validate it.

## Preferences

Each dose with a `preferred` time is moved to the closest point to that
preference inside `[earliest, latest]`, and the move is kept only if the direct
checker finds no violation. Two passes. The result is feasible by construction
and named as a local alignment, not an optimisation.

## Minimal core

Deletion-based MUS over groups: iterate the groups, remove one, and test. If the
remainder is still infeasible, the group was not needed and stays out. The result
is a minimal unsatisfiable subset (every retained group is required), which the
tests assert by removing each one in turn.

Because two disjoint conflicts can exist, the core is *a* minimal core, not all
of them; the report says how many groups were dropped and the relaxation table
covers every group independently.

## Relaxation pricing

Each option relaxes edges by subtracting `delta` from their weights:

| Kind | Effect |
|---|---|
| `shorten` (gap, interval, food) | required separation reduced by `delta` minutes |
| `open-earlier` (window) | only the lower-bound edge moves: start minus `delta` |
| `extend-later` (window) | only the upper-bound edge moves: end plus `delta` |

Relaxing more never hurts, so feasibility is monotone in `delta` and the smallest
sufficient value is found by bisection over `[0, max_relax]`. `None` means the
change does not help within the budget, which is printed as such.

## Combined repair

When no single change restores feasibility, the repair loop reads the current
positive cycle, and for each group with an edge on that cycle computes the
smallest `delta` that shortens the cycle to zero or below
(`ceil(weight / hits)`), then applies the cheapest. It repeats until feasible or
the budget is exhausted. Greedy and labelled as such; the report prints each
step and the total.

## Invariants

1. A feasible solution has `validate_schedule(problem, times) == []`.
2. `earliest[dose] <= times[dose] <= latest[dose]` for every dose.
3. A reported cycle is closed and its weight sum is positive.
4. Every group in a reported core is required for infeasibility.
5. Each reported relaxation is necessary (delta - 1 fails) and sufficient.
6. Reports contain ASCII only.
7. Solving is deterministic: no randomness, no clock reads, ordered iteration.
