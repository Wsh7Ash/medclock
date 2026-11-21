from __future__ import annotations

import pytest

from medclock.timeutil import format_span, format_time, parse_span, parse_time, to_clock


@pytest.mark.parametrize(
    ("text", "minutes"),
    [("00:00", 0), ("06:30", 390), ("6:05", 365), ("23:59", 1439), ("24:00", 1440), (" 07:15 ", 435)],
)
def test_parse_time_accepts_clock_values(text: str, minutes: int) -> None:
    assert parse_time(text) == minutes


@pytest.mark.parametrize("text", ["6:60", "25:00", "24:30", "06:30:00", "07:5", "", "abc"])
def test_parse_time_rejects_malformed_values(text: str) -> None:
    with pytest.raises(ValueError):
        parse_time(text)


@pytest.mark.parametrize("value", [630, None, 6.5, ["06:30"]])
def test_parse_time_rejects_non_strings(value: object) -> None:
    with pytest.raises(ValueError):
        parse_time(value)


def test_format_time_round_trips() -> None:
    for minutes in (0, 1, 59, 60, 390, 1439, 1440):
        assert parse_time(format_time(minutes)) == minutes


def test_format_time_end_of_day() -> None:
    assert format_time(1440) == "24:00"


@pytest.mark.parametrize("minutes", [-1, 1441, 2000])
def test_format_time_rejects_out_of_day_values(minutes: int) -> None:
    with pytest.raises(ValueError):
        format_time(minutes)


@pytest.mark.parametrize(
    ("minutes", "text"), [(0, "0m"), (45, "45m"), (60, "1h"), (90, "1h30m"), (240, "4h"), (145, "2h25m")]
)
def test_format_span(minutes: int, text: str) -> None:
    assert format_span(minutes) == text


def test_format_span_rejects_negative() -> None:
    with pytest.raises(ValueError):
        format_span(-5)


@pytest.mark.parametrize(
    ("value", "minutes"), [(240, 240), ("240", 240), ("240m", 240), ("4h", 240), ("1h30m", 90), ("1H", 60), (90.0, 90)]
)
def test_parse_span_accepts_minutes_and_durations(value: object, minutes: int) -> None:
    assert parse_span(value) == minutes


@pytest.mark.parametrize("value", [-5, "-5m", "4 hours", True, 90.5, "1h75m", None, "h"])
def test_parse_span_rejects_bad_durations(value: object) -> None:
    with pytest.raises(ValueError):
        parse_span(value)


def test_to_clock_keeps_sign() -> None:
    assert to_clock(240) == "+4h"
    assert to_clock(-15) == "-15m"
    assert to_clock(0) == "+0m"
