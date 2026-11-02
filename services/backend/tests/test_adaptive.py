from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from belok.domain import adaptive
from belok.services.reminders import Reminder, due

DAY = date(2026, 11, 2)
FORMULA = 2200.0


def days_back(n: int) -> date:
    return DAY - timedelta(days=n)


def weights(start: float, per_day: float, every: int = 3, count: int = 8):
    return [(days_back(25 - i * every), start + per_day * i * every) for i in range(count)]


def test_slope_of_a_straight_line():
    points = [(days_back(20 - i), 80 - 0.05 * i) for i in range(10)]
    assert adaptive.weight_slope(points) == pytest.approx(-0.05)


def test_not_ready_without_enough_logged_days():
    intake = {days_back(i): 2000.0 for i in range(1, 10)}
    est = adaptive.estimate(intake, weights(80, -0.02), FORMULA)
    assert not est.ready
    assert est.logged_days == 9
    assert est.tdee is None


def test_not_ready_when_weigh_ins_span_too_short():
    intake = {days_back(i): 2000.0 for i in range(1, 21)}
    points = [(days_back(i), 80.0) for i in range(1, 8)]
    est = adaptive.estimate(intake, points, FORMULA)
    assert est.weigh_ins == 7
    assert est.span_days == 6
    assert not est.ready


def test_losing_weight_means_expenditure_above_intake():
    intake = {days_back(i): 2000.0 for i in range(1, 21)}
    est = adaptive.estimate(intake, weights(80, -0.03), FORMULA)
    assert est.ready
    assert est.tdee == pytest.approx(2000 + 0.03 * adaptive.KCAL_PER_KG)


def test_stable_weight_means_expenditure_equals_intake():
    intake = {days_back(i): 2100.0 for i in range(1, 21)}
    est = adaptive.estimate(intake, weights(80, 0.0), FORMULA)
    assert est.tdee == pytest.approx(2100)


def test_half_logged_days_are_ignored():
    intake = {days_back(i): 2000.0 for i in range(1, 21)} | {days_back(21): 300.0}
    est = adaptive.estimate(intake, weights(80, 0.0), FORMULA)
    assert est.logged_days == 20
    assert est.tdee == pytest.approx(2000)


def test_estimate_is_clamped_around_the_formula():
    intake = {days_back(i): 1200.0 for i in range(1, 21)}
    est = adaptive.estimate(intake, weights(80, 0.1), FORMULA)
    assert est.tdee == pytest.approx(FORMULA * (1 - adaptive.MAX_DEVIATION))


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (8, 29, []),
        (8, 30, [Reminder.WEIGHT]),
        (9, 29, [Reminder.WEIGHT]),
        (9, 30, []),
        (14, 5, [Reminder.LUNCH]),
        (20, 45, [Reminder.DINNER]),
        (23, 0, []),
    ],
)
def test_reminder_slots(hour, minute, expected):
    now = datetime(2026, 11, 2, hour, minute, tzinfo=ZoneInfo("Europe/Moscow"))
    assert due(now) == expected
