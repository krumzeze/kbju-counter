from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from belok.catalog import Group


class CatalogItemOut(BaseModel):
    id: str
    name: str
    group: Group
    primary: list[str]
    equipment: str
    cardio: bool
    images: int


class CatalogDetailOut(CatalogItemOut):
    name_en: str
    secondary: list[str]
    instructions: list[str]
    level: str
    mechanic: str | None
    force: str | None
    exercise_id: int | None


class ExerciseOut(BaseModel):
    id: int
    name: str
    catalog_id: str | None
    group: str | None
    cardio: bool
    sets: int = 0
    last_day: date | None = None


class ExerciseRef(BaseModel):
    exercise_id: int | None = None
    catalog_id: str | None = Field(default=None, max_length=96)

    @model_validator(mode="after")
    def exactly_one(self) -> "ExerciseRef":
        if (self.exercise_id is None) == (self.catalog_id is None):
            raise ValueError("pass exactly one of exercise_id and catalog_id")
        return self


class CustomExerciseIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    group: Group | None = None
    cardio: bool = False


class SetIn(BaseModel):
    exercise_id: int
    weight_kg: float = Field(default=0, ge=0, le=1000)
    reps: int | None = Field(default=None, ge=1, le=1000)
    duration_s: int | None = Field(default=None, ge=1, le=6 * 3600)

    @model_validator(mode="after")
    def reps_or_duration(self) -> "SetIn":
        if self.reps is None and self.duration_s is None:
            raise ValueError("reps or duration_s is required")
        return self


class SetPatchIn(BaseModel):
    weight_kg: float = Field(ge=0, le=1000)
    reps: int | None = Field(default=None, ge=1, le=1000)
    duration_s: int | None = Field(default=None, ge=1, le=6 * 3600)


class SetOut(BaseModel):
    id: int
    workout_id: int
    exercise_id: int
    exercise: str
    day: date
    weight_kg: float
    reps: int | None
    duration_s: int | None


class SetCreatedOut(SetOut):
    record: bool


class PreviousSetOut(BaseModel):
    weight_kg: float
    reps: int | None
    duration_s: int | None


class WorkoutExerciseOut(BaseModel):
    exercise: ExerciseOut
    planned_sets: int
    sets: list[SetOut]
    previous: list[PreviousSetOut]
    previous_day: date | None


class WorkoutOut(BaseModel):
    id: int
    day: date
    started_at: datetime
    finished_at: datetime | None
    title: str | None
    exercises: list[WorkoutExerciseOut]
    sets: int
    volume_kg: float


class WorkoutSummaryOut(BaseModel):
    id: int
    day: date
    started_at: datetime
    finished_at: datetime | None
    title: str | None
    exercises: int
    sets: int
    volume_kg: float
    names: list[str]


class PlanItemIn(ExerciseRef):
    sets: int = Field(default=3, ge=0, le=20)


class WorkoutStartIn(BaseModel):
    template_id: int | None = None
    title: str | None = Field(default=None, max_length=64)


class WorkoutPatchIn(BaseModel):
    title: str | None = Field(default=None, max_length=64)
    finished: bool | None = None


class TemplateItemOut(BaseModel):
    exercise: ExerciseOut
    sets: int


class TemplateOut(BaseModel):
    id: int
    name: str
    items: list[TemplateItemOut]


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    items: list[PlanItemIn] = Field(default_factory=list, max_length=30)
    workout_id: int | None = None


class ProgressSetOut(BaseModel):
    weight_kg: float
    reps: int | None
    duration_s: int | None


class ProgressPointOut(BaseModel):
    day: date
    top_weight_kg: float
    top_reps: int | None
    e1rm: float
    sets: int
    reps: int
    volume_kg: float
    duration_s: int
    items: list[ProgressSetOut]


class RecordsOut(BaseModel):
    e1rm: float
    weight_kg: float
    reps: int
    volume_kg: float
    duration_s: int


class ProgressOut(BaseModel):
    exercise: ExerciseOut
    points: list[ProgressPointOut]
    records: RecordsOut


class WeekOut(BaseModel):
    start: date
    workouts: int
    sets: int
    volume_kg: float
    cardio_min: float


class TopExerciseOut(BaseModel):
    exercise: ExerciseOut
    sets: int
    best_e1rm: float


class AnalyticsOut(BaseModel):
    weeks: list[WeekOut]
    streak_weeks: int
    total_workouts: int
    muscles_week: dict[str, float]
    muscles_month: dict[str, float]
    groups_month: dict[str, int]
    top: list[TopExerciseOut]
