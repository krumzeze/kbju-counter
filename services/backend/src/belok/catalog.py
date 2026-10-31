import json
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

from belok.domain.workouts import normalize_exercise
from belok.i18n import Language

DATA = Path(__file__).parent / "data" / "exercises.json"


class Group(StrEnum):
    DELTS = "delts"
    CHEST = "chest"
    ARMS = "arms"
    ABS = "abs"
    BACK = "back"
    LEGS = "legs"
    GLUTES = "glutes"
    CALVES = "calves"
    CARDIO = "cardio"


MUSCLE_GROUP = {
    "shoulders": Group.DELTS,
    "chest": Group.CHEST,
    "biceps": Group.ARMS,
    "triceps": Group.ARMS,
    "forearms": Group.ARMS,
    "abdominals": Group.ABS,
    "lats": Group.BACK,
    "middle back": Group.BACK,
    "lower back": Group.BACK,
    "traps": Group.BACK,
    "neck": Group.BACK,
    "quadriceps": Group.LEGS,
    "hamstrings": Group.LEGS,
    "adductors": Group.LEGS,
    "abductors": Group.LEGS,
    "glutes": Group.GLUTES,
    "calves": Group.CALVES,
}


@dataclass(frozen=True, slots=True)
class CatalogExercise:
    id: str
    name: dict[str, str]
    instructions: dict[str, list[str]]
    primary: list[str]
    secondary: list[str]
    equipment: str
    category: str
    level: str
    mechanic: str | None
    force: str | None
    images: int

    @property
    def cardio(self) -> bool:
        return self.category == "cardio"

    @property
    def group(self) -> Group:
        if self.cardio:
            return Group.CARDIO
        return MUSCLE_GROUP.get(self.primary[0], Group.LEGS) if self.primary else Group.LEGS

    def title(self, lang: Language) -> str:
        return self.name.get(lang, self.name["en"])

    def steps(self, lang: Language) -> list[str]:
        return self.instructions.get(lang, self.instructions["en"])


@cache
def catalog() -> dict[str, CatalogExercise]:
    return {x["id"]: CatalogExercise(**x) for x in json.loads(DATA.read_text())}


@cache
def _by_name() -> dict[str, CatalogExercise]:
    index = {}
    for x in catalog().values():
        for name in x.name.values():
            index.setdefault(normalize_exercise(name), x)
    return index


def find_by_name(name: str) -> CatalogExercise | None:
    return _by_name().get(normalize_exercise(name))
