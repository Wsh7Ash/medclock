# Usage

## Command

```shell
medclock check PROBLEM [--json] [--fail-on infeasible|warning|none] [--max-relax MINUTES]
```

| Flag | Default | Meaning |
|---|---|---|
| `PROBLEM` | required | regimen JSON file |
| `--json` | off | machine-readable report on stdout |
| `--fail-on` | `infeasible` | `warning` also fails when warnings exist; `none` never fails |
| `--max-relax` | `1440` | largest single relaxation to price, in minutes |

Exit codes:

| Code | Meaning |
|---|---|
| `0` | gate passed |
| `1` | gate failed (infeasible, or a warning with `--fail-on warning`) |
| `2` | usage or input error, message on stderr, nothing on stdout |

## Regimen file

```json
{
  "name": "morning-routine",
  "wake": "06:30",
  "sleep": "22:30",
  "events": { "breakfast": "07:30", "lunch": "12:30", "dinner": "18:30" },
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

### Fields

| Field | Type | Notes |
|---|---|---|
| `name` | string | report label; defaults to the file stem |
| `wake`, `sleep` | `HH:MM` | warnings only, not constraints; must differ |
| `events` | object | name -> `HH:MM`; names are referenced by `food` |
| `medications[].name` | string | unique within the file |
| `medications[].window` | object | `start` and `end`, `start < end`, `24:00` allowed as an end |
| `medications[].windows` | list | one entry per dose; use instead of `window` |
| `medications[].min_gap` | minutes or duration | interval between consecutive doses; needs two or more doses |
| `medications[].preferred` | list | one time (or `null`) per dose, inside its window |
| `medications[].food` | list | `event`, `relation` (`before`/`after`), `minutes`, optional `reason` |
| `gaps[]` | list | `before`, `after`, `minutes`, optional `reason` |

Durations accept minutes as an integer (`240`), a numbered string (`"240"`),
`"240m"`, `"4h"`, or `"1h30m"`. Clock times are `HH:MM` on a 24-hour clock.

### Rules of the road

- A `gap` is **ordered**: every dose of `after` must come at least `minutes` after
  every dose of `before`. For a symmetric "never within X" rule, declare the
  direction that is true for your case.
- A `gap` applies to all pairs of the two medications. If only dose 1 of A
  interacts with B, split A into two entries (for example `a-morning` and
  `a-evening`) with their own windows.
- Windows are within one day. A regimen that wraps past midnight needs separate
  entries with a gap across the boundary.
- `min_gap` relates consecutive doses in the order given, so list windows in
  chronological order.
- Preference times are inside the window by validation; they are soft and never
  override a rule.

## Reading the report

Feasible:

- `SCHEDULE` rows are sorted by time; `slack` is how many minutes the dose could
  move later before breaking a rule; the preference column shows the requested
  time even when it could not be met.
- `constraint groups: N/N checked directly against the problem` means a separate
  checker walked the original rules, not the graph.
- `WARNINGS` lists doses outside waking hours and doses with zero slack.

Infeasible:

- `INFEASIBILITY PROOF` lists the cycle; add the weights and the total must be
  positive, which is why the start node would have to exceed itself.
- `MINIMAL UNSATISFIABLE CORE` is the smallest set of rule groups that is already
  impossible; dropping any one of them restores feasibility.
- `RELAXATIONS` gives the smallest single change, in minutes, with the concrete
  edit. `no single change in N other group(s)...` means relaxing that rule does
  not help within the budget.
- `COMBINED RELAXATION` appears only when no single change suffices; it is a
  cheapest-first repair, not a minimal total.

## JSON

```json
{
  "tool": "medclock",
  "problem": {"name": "...", "source": "...", "wake": "06:30", "sleep": "22:30",
              "events": {"breakfast": "07:30"}, "medications": 5, "doses": 7,
              "constraint_groups": 13},
  "feasible": true,
  "gate": "feasible",
  "schedule": [
    {"dose": "levothyroxine#1", "time": "06:30", "minutes": 390,
     "window": "06:30-07:00", "slack": "30m", "slack_minutes": 30,
     "preferred": null, "preference_met": false}
  ],
  "constraints": {"groups": 13, "violations": []},
  "warnings": [],
  "diagnostics": null
}
```

Infeasible reports fill `diagnostics`:

```json
{
  "cycle": {"weight_minutes": 120,
            "steps": [{"from": "clock", "to": "levothyroxine#1",
                       "weight_minutes": 420,
                       "relation": "t(levothyroxine#1) >= t(clock) +7h",
                       "label": "levothyroxine#1 is at or after 07:00 (window)"}]},
  "core": [{"id": "window:calcium#1", "kind": "window", "text": "..."}],
  "core_is_minimal": true,
  "dropped_groups": 4,
  "relaxations": [{"id": "gap:levothyroxine->calcium", "kind": "shorten",
                   "minutes": 120, "text": "shorten levothyroxine->calcium: 4h -> 2h"}],
  "combined": [],
  "max_relax_minutes": 1440
}
```

`schedule` is `[]` and `warnings` is `[]` when infeasible.

## Examples

```shell
# is this plan achievable?
medclock check fixtures/morning.json

# why not, in machine-readable form
medclock check fixtures/pinch.json --json

# only price small changes: up to 30 minutes
medclock check plan.json --max-relax 30

# do not fail the pipeline, just report
medclock check plan.json --fail-on none
```

## Troubleshooting

| Message | Cause |
|---|---|
| `start HH:MM must be before end` | a window with equal or reversed bounds; use two entries or a longer window |
| `unknown medication` / `unknown event` | a gap or food rule names something not declared (names are case-sensitive) |
| `preferred[i] is outside the dose window` | the requested time is not inside that dose's window |
| `use 'min_gap' for two doses of the same medication` | self-referential gap |
| `no single change in N other group(s) removes the conflict` | the listed rules are not the bottleneck, or the budget is too small |
