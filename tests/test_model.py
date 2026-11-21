from __future__ import annotations

import json
from pathlib import Path

import pytest

from medclock.model import ModelError, from_dict, load
from conftest import FIXTURES, med, regimen, write_problem  # noqa: F401


def test_load_morning_fixture() -> None:
    problem = load(FIXTURES / "morning.json")
    assert problem.name == "morning-routine"
    assert len(problem.medications) == 5
    assert len(problem.doses) == 7
    assert problem.constraint_groups == 13
    assert problem.events["breakfast"] == 450
    assert problem.wake == 390 and problem.sleep == 1350
    metformin = problem.medication("metformin")
    assert metformin is not None
    assert metformin.min_gap == 480
    assert [dose.label for dose in metformin.doses] == ["metformin#1", "metformin#2"]
    assert metformin.doses[1].preferred == 1170


def test_shared_window_expands_to_all_doses() -> None:
    problem = from_dict(regimen([{"name": "a", "windows": [
        {"start": "08:00", "end": "09:00"},
        {"start": "20:00", "end": "21:00"},
    ]}]))
    assert [dose.number for dose in problem.doses] == [1, 2]
    assert problem.constraint_groups == 2


def test_interval_counts_as_one_group() -> None:
    problem = from_dict(
        regimen(
            [
                {
                    "name": "a",
                    "windows": [
                        {"start": "08:00", "end": "09:00"},
                        {"start": "20:00", "end": "21:00"},
                    ],
                    "min_gap": "10h",
                }
            ]
        )
    )
    assert problem.constraint_groups == 3  # two windows plus the interval


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        (regimen([med("a", "09:00", "08:00")]), "must be before end"),
        (regimen([{"name": "a"}]), "window' or 'windows"),
        (regimen([{**med("a", "08:00", "09:00"), "windows": [{"start": "08:00", "end": "09:00"}]}]), "not both"),
        (regimen([med("a", "08:00", "09:00"), med("a", "10:00", "11:00")]), "duplicate medication"),
        (regimen([med("a", "08:00", "09:00", preferred="10:00")]), "outside the dose window"),
        (regimen([med("a", "08:00", "09:00", preferred=["08:30", "08:45"])]), "one entry per dose"),
        (regimen([med("a", "08:00", "09:00", min_gap="2h")]), "at least two doses"),
        (regimen([med("a", "08:00", "09:00", min_gap=0)]), "greater than zero"),
        (
            regimen([med("a", "08:00", "09:00")], gaps=[{"before": "a", "after": "b", "minutes": 30}]),
            "unknown medication 'b'",
        ),
        (
            regimen([med("a", "08:00", "09:00")], gaps=[{"before": "a", "after": "a", "minutes": 30}]),
            "min_gap",
        ),
        (
            regimen([med("a", "08:00", "09:00")], gaps=[{"before": "a", "minutes": 30}]),
            "needs 'before' and 'after'",
        ),
        (
            regimen(
                [med("a", "08:00", "09:00", food=[{"event": "breakfast", "relation": "with", "minutes": 15}])],
                events={"breakfast": "08:00"},
            ),
            "relation must be",
        ),
        (
            regimen([med("a", "08:00", "09:00", food=[{"event": "lunch", "relation": "after", "minutes": 15}])]),
            "unknown event",
        ),
        (regimen([med("a", "08:00", "09:00")], wake="07:00", sleep="07:00"), "cannot be the same"),
        (regimen([med("a", "08:00", "09:00")], events={"lunch": "25:00"}), "events.lunch"),
    ],
)
def test_invalid_problems_are_rejected(payload: dict, fragment: str) -> None:
    with pytest.raises(ModelError) as excinfo:
        from_dict(payload)
    assert fragment in str(excinfo.value)


def test_duplicate_gap_is_rejected() -> None:
    payload = regimen(
        [med("a", "08:00", "09:00"), med("b", "10:00", "11:00")],
        gaps=[
            {"before": "a", "after": "b", "minutes": 30},
            {"before": "a", "after": "b", "minutes": 60},
        ],
    )
    with pytest.raises(ModelError, match="duplicate gap"):
        from_dict(payload)


def test_top_level_must_be_object() -> None:
    with pytest.raises(ModelError, match="JSON object"):
        from_dict([])


def test_medications_must_be_non_empty_list() -> None:
    with pytest.raises(ModelError, match="non-empty list"):
        from_dict({"medications": []})


def test_invalid_time_in_window_is_reported() -> None:
    with pytest.raises(ModelError, match="a.windows"):
        from_dict(regimen([{"name": "a", "window": {"start": "8", "end": "09:00"}}]))


def test_unknown_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ModelError, match="cannot read"):
        load(tmp_path / "missing.json")


def test_invalid_json_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ModelError, match="invalid JSON"):
        load(path)


def test_valid_file_round_trip(tmp_path: Path) -> None:
    payload = regimen([med("a", "08:00", "09:00")], events={"breakfast": "08:15"})
    problem = load(write_problem(tmp_path, payload))
    assert problem.source == "regimen.json"
    assert problem.events == {"breakfast": 495}
    assert json.loads((tmp_path / "regimen.json").read_text(encoding="utf-8"))["name"] == "test-regimen"
