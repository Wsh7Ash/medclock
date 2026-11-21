"""Problem definition, input loading and strict validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .timeutil import format_span, format_time, parse_span, parse_time


class ModelError(ValueError):
    """Raised when a problem file cannot be interpreted."""


@dataclass(frozen=True)
class Dose:
    """One administration of one medication."""

    med: str
    number: int
    start: int
    end: int
    preferred: int | None = None

    @property
    def label(self) -> str:
        return f"{self.med}#{self.number}"

    @property
    def window(self) -> str:
        return f"{format_time(self.start)}-{format_time(self.end)}"


@dataclass(frozen=True)
class Medication:
    name: str
    doses: tuple[Dose, ...]
    min_gap: int | None = None


@dataclass(frozen=True)
class Gap:
    """An ordered absorption gap: every dose of ``after`` follows every dose of ``before``."""

    before: str
    after: str
    minutes: int
    reason: str = ""

    @property
    def cid(self) -> str:
        return f"gap:{self.before}->{self.after}"

    @property
    def text(self) -> str:
        span = format_span(self.minutes)
        suffix = f" ({self.reason})" if self.reason else ""
        return f"{self.after} at least {span} after {self.before}{suffix}"


@dataclass(frozen=True)
class FoodRule:
    """A dose position relative to a named event such as a meal."""

    med: str
    event: str
    relation: str
    minutes: int
    reason: str = ""

    @property
    def cid(self) -> str:
        return f"food:{self.med}@{self.relation}:{self.event}"

    @property
    def text(self) -> str:
        span = format_span(self.minutes)
        suffix = f" ({self.reason})" if self.reason else ""
        if self.relation == "before":
            return f"{self.med} at least {span} before {self.event}{suffix}"
        return f"{self.med} at least {span} after {self.event}{suffix}"


@dataclass(frozen=True)
class Problem:
    name: str
    source: str
    wake: int | None
    sleep: int | None
    events: dict[str, int]
    medications: tuple[Medication, ...]
    gaps: tuple[Gap, ...]
    food: tuple[FoodRule, ...]

    @property
    def doses(self) -> tuple[Dose, ...]:
        return tuple(dose for med in self.medications for dose in med.doses)

    def medication(self, name: str) -> Medication | None:
        for med in self.medications:
            if med.name == name:
                return med
        return None

    @property
    def constraint_groups(self) -> int:
        windows = len(self.doses)
        intervals = sum(1 for med in self.medications if med.min_gap is not None and len(med.doses) > 1)
        return windows + intervals + len(self.gaps) + len(self.food)


def load(path: Path) -> Problem:
    """Load a problem from a JSON file."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ModelError(f"cannot read {path}: {exc.strerror or exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ModelError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    return from_dict(data, source=str(path))


def from_dict(data: Any, source: str = "<memory>") -> Problem:
    """Validate a decoded problem object and return the model."""
    if not isinstance(data, dict):
        raise ModelError("problem must be a JSON object")

    name = _optional_text(data.get("name"), "name") or Path(source).stem or "problem"
    events = _events(data.get("events", {}))
    medications, food = _medications(data.get("medications"), events)
    by_name = {med.name: med for med in medications}
    gaps = _gaps(data.get("gaps", []), by_name)
    wake = _optional_time(data.get("wake"), "wake")
    sleep = _optional_time(data.get("sleep"), "sleep")
    if wake is not None and sleep is not None and wake == sleep:
        raise ModelError("wake and sleep cannot be the same time")

    return Problem(
        name=name,
        source=Path(source).name if source not in {"<memory>", ""} else source,
        wake=wake,
        sleep=sleep,
        events=events,
        medications=medications,
        gaps=gaps,
        food=food,
    )


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ModelError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_time(value: Any, field: str) -> int | None:
    if value is None:
        return None
    try:
        return parse_time(value)
    except ValueError as exc:
        raise ModelError(f"{field}: {exc}") from exc


def _events(raw: Any) -> dict[str, int]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ModelError("events must be an object mapping names to HH:MM times")
    events: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ModelError("event names must be non-empty strings")
        name = key.strip()
        if name in events:
            raise ModelError(f"duplicate event {name!r}")
        try:
            events[name] = parse_time(value)
        except ValueError as exc:
            raise ModelError(f"events.{name}: {exc}") from exc
    return events


def _medications(
    raw: Any, events: dict[str, int]
) -> tuple[tuple[Medication, ...], tuple[FoodRule, ...]]:
    if not isinstance(raw, list) or not raw:
        raise ModelError("medications must be a non-empty list")
    meds: list[Medication] = []
    food: list[FoodRule] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ModelError(f"medications[{index}] must be an object")
        name = _optional_text(entry.get("name"), f"medications[{index}].name")
        if name is None:
            raise ModelError(f"medications[{index}].name is required")
        if name in seen:
            raise ModelError(f"duplicate medication {name!r}")
        seen.add(name)
        windows = _windows(entry, name)
        preferred = _preferred(entry.get("preferred"), windows, name)
        min_gap: int | None = None
        if entry.get("min_gap") is not None:
            try:
                min_gap = parse_span(entry["min_gap"])
            except ValueError as exc:
                raise ModelError(f"{name}.min_gap: {exc}") from exc
            if min_gap <= 0:
                raise ModelError(f"{name}.min_gap must be greater than zero")
            if len(windows) < 2:
                raise ModelError(f"{name}.min_gap needs at least two doses")
        meds.append(
            Medication(
                name=name,
                doses=tuple(
                    Dose(med=name, number=i + 1, start=start, end=end, preferred=preferred[i])
                    for i, (start, end) in enumerate(windows)
                ),
                min_gap=min_gap,
            )
        )
        food.extend(_parse_food(entry.get("food"), name, events))
    return tuple(meds), tuple(food)


def _windows(entry: dict[str, Any], name: str) -> tuple[tuple[int, int], ...]:
    has_single = "window" in entry
    has_many = "windows" in entry
    if has_single and has_many:
        raise ModelError(f"{name}: use either 'window' or 'windows', not both")
    if has_single:
        raw_windows = [entry["window"]]
    elif has_many:
        raw_windows = entry["windows"]
    else:
        raise ModelError(f"{name}: a 'window' or 'windows' entry is required")
    if not isinstance(raw_windows, list) or not raw_windows:
        raise ModelError(f"{name}: 'windows' must be a non-empty list")
    windows: list[tuple[int, int]] = []
    for index, raw in enumerate(raw_windows):
        if not isinstance(raw, dict):
            raise ModelError(f"{name}.windows[{index}] must be an object")
        try:
            start = parse_time(raw.get("start"))
            end = parse_time(raw.get("end"))
        except ValueError as exc:
            raise ModelError(f"{name}.windows[{index}]: {exc}") from exc
        if start >= end:
            raise ModelError(
                f"{name}.windows[{index}]: start {format_time(start)} must be before end {format_time(end)}"
            )
        windows.append((start, end))
    return tuple(windows)


def _preferred(raw: Any, windows: tuple[tuple[int, int], ...], name: str) -> list[int | None]:
    if raw is None:
        return [None] * len(windows)
    values = raw if isinstance(raw, list) else [raw]
    if len(values) != len(windows):
        raise ModelError(f"{name}: 'preferred' must have one entry per dose ({len(windows)})")
    preferred: list[int | None] = []
    for index, value in enumerate(values):
        if value is None:
            preferred.append(None)
            continue
        try:
            minute = parse_time(value)
        except ValueError as exc:
            raise ModelError(f"{name}.preferred[{index}]: {exc}") from exc
        start, end = windows[index]
        if not start <= minute <= end:
            raise ModelError(
                f"{name}.preferred[{index}]: {format_time(minute)} is outside the dose window "
                f"{format_time(start)}-{format_time(end)}"
            )
        preferred.append(minute)
    return preferred


def _gaps(raw: Any, meds: dict[str, Medication]) -> tuple[Gap, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ModelError("gaps must be a list")
    gaps: list[Gap] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ModelError(f"gaps[{index}] must be an object")
        before = _optional_text(entry.get("before"), f"gaps[{index}].before")
        after = _optional_text(entry.get("after"), f"gaps[{index}].after")
        if before is None or after is None:
            raise ModelError(f"gaps[{index}] needs 'before' and 'after'")
        for role, med in (("before", before), ("after", after)):
            if med not in meds:
                raise ModelError(f"gaps[{index}].{role}: unknown medication {med!r}")
        if before == after:
            raise ModelError(f"gaps[{index}]: use 'min_gap' for two doses of the same medication")
        try:
            minutes = parse_span(entry.get("minutes"))
        except ValueError as exc:
            raise ModelError(f"gaps[{index}].minutes: {exc}") from exc
        reason = _optional_text(entry.get("reason"), f"gaps[{index}].reason") or ""
        gap = Gap(before=before, after=after, minutes=minutes, reason=reason)
        if gap.cid in seen:
            raise ModelError(f"duplicate gap between {before} and {after}")
        seen.add(gap.cid)
        gaps.append(gap)
    return tuple(gaps)


def _parse_food(raw: Any, med: str, events: dict[str, int]) -> tuple[FoodRule, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ModelError(f"{med}.food must be a list")
    rules: list[FoodRule] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ModelError(f"{med}.food[{index}] must be an object")
        event = _optional_text(entry.get("event"), f"{med}.food[{index}].event")
        if event is None:
            raise ModelError(f"{med}.food[{index}].event is required")
        if event not in events:
            raise ModelError(f"{med}.food[{index}]: unknown event {event!r}")
        relation = _optional_text(entry.get("relation"), f"{med}.food[{index}].relation")
        if relation not in {"before", "after"}:
            raise ModelError(f"{med}.food[{index}].relation must be 'before' or 'after'")
        try:
            minutes = parse_span(entry.get("minutes"))
        except ValueError as exc:
            raise ModelError(f"{med}.food[{index}].minutes: {exc}") from exc
        reason = _optional_text(entry.get("reason"), f"{med}.food[{index}].reason") or ""
        rule = FoodRule(med=med, event=event, relation=relation, minutes=minutes, reason=reason)
        if rule.cid in seen:
            raise ModelError(f"{med}.food[{index}]: duplicate rule for {event}")
        seen.add(rule.cid)
        rules.append(rule)
    return tuple(rules)
