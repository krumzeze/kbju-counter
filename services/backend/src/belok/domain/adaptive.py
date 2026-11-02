"""Maintenance calories measured from logged intake and the weight trend."""

from dataclasses import dataclass
from datetime import date, timedelta

KCAL_PER_KG = 7700
WINDOW_DAYS = 28
MIN_LOGGED_DAYS = 14
MIN_WEIGH_INS = 6
MIN_WEIGHT_SPAN_DAYS = 14
# Days with less than this share of formula maintenance are treated as incompletely logged.
LOGGED_DAY_SHARE = 0.5
# The estimate never moves further than this from the formula, which guards against bad logs.
MAX_DEVIATION = 0.25


@dataclass(frozen=True, slots=True)
class Estimate:
    logged_days: int
    weigh_ins: int
    span_days: int
    tdee: float | None

    @property
    def ready(self) -> bool:
        return self.tdee is not None


def window(day: date) -> tuple[date, date]:
    """Data window used for the target on `day`; today itself is still being logged."""
    return day - timedelta(days=WINDOW_DAYS), day - timedelta(days=1)


def weight_slope(points: list[tuple[date, float]]) -> float:
    """Least-squares trend of body weight in kg per day."""
    origin = points[0][0]
    xs = [(d - origin).days for d, _ in points]
    ys = [w for _, w in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    var = sum((x - mean_x) ** 2 for x in xs)
    if var == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / var


def estimate(
    intake: dict[date, float], weights: list[tuple[date, float]], formula_kcal: float
) -> Estimate:
    logged = [kcal for kcal in intake.values() if kcal >= formula_kcal * LOGGED_DAY_SHARE]
    points = sorted(weights)
    span = (points[-1][0] - points[0][0]).days if points else 0
    ready = (
        len(logged) >= MIN_LOGGED_DAYS
        and len(points) >= MIN_WEIGH_INS
        and span >= MIN_WEIGHT_SPAN_DAYS
    )
    tdee = None
    if ready:
        measured = sum(logged) / len(logged) - weight_slope(points) * KCAL_PER_KG
        low, high = formula_kcal * (1 - MAX_DEVIATION), formula_kcal * (1 + MAX_DEVIATION)
        tdee = min(high, max(low, measured))
    return Estimate(len(logged), len(points), span, tdee)
