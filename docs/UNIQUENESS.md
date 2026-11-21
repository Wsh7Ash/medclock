# Uniqueness

## Closest existing work (researched 2026-11-21)

| Tool / source | What it does | Why it does not cover this |
|---|---|---|
| `polars-scheduler` (GitHub, 2025) | MILP scheduling of recurring events with constraints like ">=6h apart", ">=1h before food", time windows, earliest/latest strategies | closest neighbour: a dataframe plugin for generic events, so a regimen needs hand-built rows; output is a schedule, and an infeasible input reports the solver's infeasibility rather than a cycle, a minimal core and minute-priced repairs |
| `atria` (GitHub) | CP-SAT duty-roster scheduling with named assumption literals, so over-constraint returns the conflicting rules and ranked fixes | same idea of explaining conflicts, but domain is residency rosters, requires OR-Tools, and the explanation is solver-assumption based |
| iMAT / GMS model (Academia Sinica reports 2005-2008) | medication schedule specification and dispenser scheduler with consistency and feasibility checks, dose separation ranges, supply/demand tests | a research programme for dispensing hardware; parameter-consistency theorems, not a CLI over windows and gaps, and no per-constraint minute costs |
| US20110000170A1 (patent) | constraint-propagation scheduling of prescription doses onto a calendar with rescheduling | patent claims a generator with backtracking; no certificate, no core, no relaxation pricing, closed source |
| Reminder apps (PillPal, MedTimer-likes, `jarvis-cmd-medication`) | store dose times, notify, show the next dose | no feasibility reasoning at all: they assume the times you entered are achievable |
| OR-Tools CP-SAT formulations of medication timing | solves a regimen as an integer program | a general solver with no regimen input model; infeasibility is a status, not an explanation you can check by hand |
| FHIR/HL7 dosage invariant guides (e.g. Medication IG DE) | consistency rules for dosage elements (frequency vs time-of-day count) | validates the *document*, not whether times exist inside the windows |
| `DoseBench` (2026) | evaluates LLM dosing decisions under temporal uncertainty | a benchmark, not a scheduler |

## Similarities

Everyone in this space reads the same clinical directions: windows, separations,
meals, and "take it four hours apart". Any tool that places doses on a clock
will produce times that look similar for easy regimens.

## Meaningful differences

1. **The explanation is arithmetic, not a solver verdict.** Because every rule is
   a difference constraint, infeasibility is a positive cycle. The report prints
   each step as `t(a) >= t(b) + w` and the total, so a reader can add three
   numbers and confirm the contradiction.
2. **A minimal core, not a list of all rules.** Deletion-based shrinking reports
   the groups that are jointly impossible, and says how many other groups were
   dropped as irrelevant.
3. **Costs in minutes.** Every single-change repair is priced by bisection: the
   smallest number of minutes that restores feasibility, rendered as a concrete
   change ("4h -> 2h", "09:00 -> 11:00"). One minute less is proven insufficient
   by the test suite.
4. **A regimen input model.** Windows per dose, intervals, ordered gaps and
   event-relative rules are first-class fields, not rows to assemble.
5. **Independent re-check.** The schedule is validated from the problem itself,
   not from the graph that produced it, so a constraint-encoding bug cannot
   silently pass as a valid plan.
6. **No dependencies and no service.** A single offline CLI; runs in a pull
   request.

## Unique mechanism

Regimen -> difference-constraint graph -> longest paths for earliest times and a
positive cycle for the proof -> deletion-based minimal core -> bisection for the
minutes each relaxation needs -> conflict-driven combined repair -> direct
re-validation of the result.

The combination of the certificate, the minimal core and minute-priced single
relaxations in one dependency-free CLI over a regimen file was not found in any
public tool during the search.

## Why an independent repository

The reusable artifact is the explanation model: how a timing contradiction is
certified, reduced and priced. That is useful to any scheduler (a dataframe
plugin, a dispenser, a care-plan pipeline) and is not tied to one of them.

## Remaining originality uncertainties

- Search covered public web results on 2026-11-21; internal pharmacy or EHR
  tooling may already do this, and `polars-scheduler` plus `atria` show the
  conflict-explanation idea is being built in adjacent domains.
- Only difference constraints are modelled, so a tool using a richer formalism
  (disjunctive or resource constraints) can express regimens this one cannot.
- If a mainstream solver adds human-readable unsat cores for integer programs in
  this shape, the niche narrows to the regimen model and the minute pricing.
