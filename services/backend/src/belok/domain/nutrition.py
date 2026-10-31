from dataclasses import dataclass
from enum import StrEnum


class Sex(StrEnum):
    MALE = "m"
    FEMALE = "f"


class Goal(StrEnum):
    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


GOAL_KCAL_FACTOR = {Goal.LOSE: 0.85, Goal.MAINTAIN: 1.0, Goal.GAIN: 1.1}
PROTEIN_G_PER_KG = {Goal.LOSE: 2.0, Goal.MAINTAIN: 1.8, Goal.GAIN: 1.8}
FAT_G_PER_KG = 0.9

SEDENTARY_FACTOR = 1.2
# Steps below this are already covered by the sedentary factor.
BASELINE_STEPS = 3000
KCAL_PER_STEP_PER_KG = 0.0005
STRENGTH_NET_MET = 4.0
MINUTES_PER_SET = 2.5
CARDIO_NET_MET = 6.0
# Activity is averaged over this many days so the target stays steady between gym and rest days.
ACTIVITY_WINDOW_DAYS = 7


@dataclass(frozen=True, slots=True)
class Macros:
    kcal: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carbs: float = 0.0

    def __add__(self, other: "Macros") -> "Macros":
        return Macros(
            self.kcal + other.kcal,
            self.protein + other.protein,
            self.fat + other.fat,
            self.carbs + other.carbs,
        )

    def scaled(self, factor: float) -> "Macros":
        return Macros(
            self.kcal * factor, self.protein * factor, self.fat * factor, self.carbs * factor
        )


def bmr(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    """Mifflin-St Jeor basal metabolic rate."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == Sex.MALE else base - 161


def steps_kcal(steps: int, weight_kg: float) -> float:
    return max(0, steps - BASELINE_STEPS) * weight_kg * KCAL_PER_STEP_PER_KG


def strength_kcal(sets: int, weight_kg: float) -> float:
    hours = sets * MINUTES_PER_SET / 60
    return STRENGTH_NET_MET * weight_kg * hours


def cardio_kcal(minutes: float, weight_kg: float) -> float:
    return CARDIO_NET_MET * weight_kg * minutes / 60


def daily_target(
    sex: Sex,
    weight_kg: float,
    height_cm: float,
    age: int,
    goal: Goal,
    activity_kcal: float = 0.0,
) -> Macros:
    tdee = bmr(sex, weight_kg, height_cm, age) * SEDENTARY_FACTOR + activity_kcal
    kcal = tdee * GOAL_KCAL_FACTOR[goal]
    protein = PROTEIN_G_PER_KG[goal] * weight_kg
    fat = FAT_G_PER_KG * weight_kg
    carbs = max(0.0, (kcal - protein * 4 - fat * 9) / 4)
    return Macros(kcal, protein, fat, carbs)
