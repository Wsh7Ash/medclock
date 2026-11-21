# Changelog

All notable changes to this project are documented here. The format follows
Keep a Changelog, and the project uses semantic versioning.

## [0.1.0] - 2026-11-21

### Added

- Regimen model with per-dose windows, shared windows, same-medication intervals,
  ordered absorption gaps and event-relative food rules, with strict validation.
- Difference-constraint engine: Bellman-Ford longest paths for earliest times,
  reversed-graph longest paths for latest times and slack.
- Positive-cycle infeasibility certificate with edge weights that sum to the
  contradiction, rendered as checkable `t(dst) >= t(src) + w` steps.
- Deletion-based minimal unsatisfiable core over rule groups.
- Bisection pricing of single relaxations in minutes, with concrete edits
  (`4h -> 2h`, `09:00 -> 11:00`).
- Conflict-driven combined repair for regimens where no single change suffices.
- Independent schedule validator used on every produced schedule.
- Text and JSON reports with `--fail-on infeasible|warning|none` and
  `--max-relax`, plus exit codes 0/1/2.
- Demo script capturing real CLI output into `results/demo.txt` and
  `results/gate.txt`; 120 tests; CI on Python 3.12 and 3.13.
