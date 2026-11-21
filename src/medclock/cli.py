"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .model import ModelError, load
from .render import FAIL_ON, failed, render_json, render_text
from .solve import MAX_RELAX_DEFAULT, solve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="medclock",
        description="Check whether a medication regimen has a feasible schedule, and prove why not when it does not.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="solve one regimen file")
    check.add_argument("problem", help="regimen JSON file")
    check.add_argument("--json", action="store_true", dest="as_json", help="machine-readable report")
    check.add_argument(
        "--fail-on",
        default="infeasible",
        choices=FAIL_ON,
        help="infeasible (default) fails on an unsatisfiable regimen, warning also fails on warnings, none never fails",
    )
    check.add_argument(
        "--max-relax",
        type=int,
        default=MAX_RELAX_DEFAULT,
        metavar="MINUTES",
        help=f"largest single relaxation to consider (default {MAX_RELAX_DEFAULT})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "check":  # pragma: no cover - argparse enforces the subcommand
        return 2
    if args.max_relax < 0:
        print("medclock: error: --max-relax must not be negative", file=sys.stderr)
        return 2
    try:
        problem = load(Path(args.problem))
    except ModelError as exc:
        print(f"medclock: error: {exc}", file=sys.stderr)
        return 2

    solution = solve(problem, max_relax=args.max_relax)
    output = (
        render_json(solution, args.fail_on) if args.as_json else render_text(solution, args.fail_on)
    )
    sys.stdout.write(output)
    return 1 if failed(solution, args.fail_on) else 0
