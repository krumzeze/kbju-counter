import re
from dataclasses import dataclass

SET_RE = re.compile(r"^(\d+(?:[.,]\d+)?)[xх×*](\d+)(?:[xх×*](\d+))?$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ParsedSet:
    weight_kg: float
    reps: int


class WorkoutParseError(ValueError):
    pass


def normalize_exercise(name: str) -> str:
    return " ".join(name.lower().replace("ё", "е").split())


def parse_workout(text: str) -> tuple[str, list[ParsedSet]]:
    """Parse "bench press 80x8 80x8 75x10" or "squat 100x5x3" (weight x reps x sets)."""
    name_parts: list[str] = []
    sets: list[ParsedSet] = []
    for token in text.split():
        match = SET_RE.match(token)
        if match is None:
            if sets:
                raise WorkoutParseError("exercise name must come before sets")
            name_parts.append(token)
            continue
        weight = float(match[1].replace(",", "."))
        reps = int(match[2])
        count = int(match[3]) if match[3] else 1
        if reps <= 0 or count <= 0 or count > 20:
            raise WorkoutParseError("invalid reps or set count")
        sets.extend([ParsedSet(weight, reps)] * count)
    if not name_parts or not sets:
        raise WorkoutParseError("expected an exercise name followed by sets")
    return normalize_exercise(" ".join(name_parts)), sets


def estimated_1rm(weight_kg: float, reps: int) -> float:
    """Epley formula."""
    return weight_kg if reps == 1 else weight_kg * (1 + reps / 30)
