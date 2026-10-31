import pytest

from belok.domain.nutrition import (
    Goal,
    Macros,
    Sex,
    bmr,
    cardio_kcal,
    daily_target,
    steps_kcal,
    strength_kcal,
)


def test_bmr_mifflin_st_jeor():
    assert bmr(Sex.MALE, 80, 180, 30) == pytest.approx(1780)
    assert bmr(Sex.FEMALE, 60, 165, 25) == pytest.approx(1345.25)


def test_steps_below_baseline_add_nothing():
    assert steps_kcal(2500, 80) == 0
    assert steps_kcal(13000, 80) == pytest.approx(400)


def test_strength_kcal_scales_with_sets():
    assert strength_kcal(0, 80) == 0
    assert strength_kcal(24, 80) == pytest.approx(320)


def test_cardio_kcal():
    assert cardio_kcal(30, 80) == pytest.approx(240)


def test_daily_target_macros_add_up():
    target = daily_target(Sex.MALE, 80, 180, 30, Goal.MAINTAIN)
    assert target.kcal == pytest.approx(1780 * 1.2)
    assert target.protein == pytest.approx(144)
    assert target.fat == pytest.approx(72)
    assert target.protein * 4 + target.fat * 9 + target.carbs * 4 == pytest.approx(target.kcal)


def test_activity_and_goal_change_target():
    base = daily_target(Sex.MALE, 80, 180, 30, Goal.MAINTAIN)
    active = daily_target(Sex.MALE, 80, 180, 30, Goal.MAINTAIN, activity_kcal=300)
    cutting = daily_target(Sex.MALE, 80, 180, 30, Goal.LOSE)
    assert active.kcal > base.kcal > cutting.kcal


def test_carbs_never_negative():
    target = daily_target(Sex.FEMALE, 150, 150, 80, Goal.LOSE)
    assert target.carbs >= 0


def test_macros_arithmetic():
    total = Macros(100, 10, 5, 8) + Macros(50, 2, 1, 4)
    assert total == Macros(150, 12, 6, 12)
    assert total.scaled(2) == Macros(300, 24, 12, 24)
