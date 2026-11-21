"""Clock arithmetic for a single day, measured in integer minutes since midnight."""

from __future__ import annotations

import re

DAY_MINUTES = 1440

_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})$")
_SPAN = re.compile(r"^(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?$", re.IGNORECASE)


def parse_time(value: object) -> int:
    """Parse ``HH:MM`` into minutes since midnight. ``24:00`` means end of day."""
    if not isinstance(value, str):
        raise ValueError(f"expected a HH:MM clock time, got {value!r}")
    match = _CLOCK.match(value.strip())
    if match is None:
        raise ValueError(f"expected a HH:MM clock time, got {value!r}")
    hours, minutes = int(match.group(1)), int(match.group(2))
    if minutes > 59:
        raise ValueError(f"minutes must be 00-59 in {value!r}")
    if hours > 24 or (hours == 24 and minutes != 0):
        raise ValueError(f"hour must be 00-23 (or 24:00) in {value!r}")
    return hours * 60 + minutes


def format_time(minutes: int) -> str:
    """Render minutes since midnight as ``HH:MM``."""
    if not isinstance(minutes, int) or isinstance(minutes, bool):
        raise ValueError(f"expected integer minutes, got {minutes!r}")
    if minutes < 0 or minutes > DAY_MINUTES:
        raise ValueError(f"time out of range for a single day: {minutes}")
    if minutes == DAY_MINUTES:
        return "24:00"
    hours, rest = divmod(minutes, 60)
    return f"{hours:02d}:{rest:02d}"


def format_span(minutes: int) -> str:
    """Render a duration compactly: ``45m``, ``4h``, ``1h30m``."""
    if minutes < 0:
        raise ValueError(f"duration must not be negative: {minutes}")
    if minutes < 60:
        return f"{minutes}m"
    hours, rest = divmod(minutes, 60)
    if rest == 0:
        return f"{hours}h"
    return f"{hours}h{rest}m"


def parse_span(value: object) -> int:
    """Parse a duration into minutes. Accepts ``240``, ``"240m"``, ``"4h"``, ``"1h30m"``."""
    if isinstance(value, bool):
        raise ValueError(f"expected minutes or a duration like '4h', got {value!r}")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"duration must not be negative: {value}")
        return value
    if isinstance(value, float) and value.is_integer():
        return parse_span(int(value))
    if not isinstance(value, str):
        raise ValueError(f"expected minutes or a duration like '4h', got {value!r}")
    text = value.strip().lower()
    if re.fullmatch(r"\d+", text):
        return int(text)
    match = _SPAN.match(text)
    if match is None or (match.group(1) is None and match.group(2) is None):
        raise ValueError(f"expected minutes or a duration like '4h', got {value!r}")
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    if hours and minutes > 59:
        raise ValueError(f"minutes part must be below 60 in {value!r}")
    return hours * 60 + minutes


def to_clock(minutes: int) -> str:
    """Render an offset the way a clinician reads it: ``+240m`` or ``-15m``."""
    sign = "+" if minutes >= 0 else "-"
    return f"{sign}{format_span(abs(minutes))}"
