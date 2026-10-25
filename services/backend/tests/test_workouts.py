import pytest

from belok.domain.workouts import (
    ParsedSet,
    WorkoutParseError,
    estimated_1rm,
    normalize_exercise,
    parse_workout,
)


def test_parse_individual_sets():
    name, sets = parse_workout("Жим лёжа 80x8 80х8 75*10")
    assert name == "жим лежа"
    assert sets == [ParsedSet(80, 8), ParsedSet(80, 8), ParsedSet(75, 10)]


def test_parse_repeated_sets_and_decimal_weight():
    name, sets = parse_workout("присед 102,5x5x3")
    assert name == "присед"
    assert sets == [ParsedSet(102.5, 5)] * 3


@pytest.mark.parametrize("text", ["", "жим лежа", "80x8", "80x8 жим", "жим 80x0", "жим 80x5x50"])
def test_parse_rejects_invalid_input(text):
    with pytest.raises(WorkoutParseError):
        parse_workout(text)


def test_normalize_exercise():
    assert normalize_exercise("  Тяга   ВЕРХНЕГО блока ") == "тяга верхнего блока"


def test_estimated_1rm():
    assert estimated_1rm(100, 1) == 100
    assert estimated_1rm(90, 6) == pytest.approx(108)
