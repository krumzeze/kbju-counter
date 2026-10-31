from datetime import date, datetime
from zoneinfo import ZoneInfo, available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator

from belok.api.workout_schemas import SetOut
from belok.db.models import Meal
from belok.domain.nutrition import Goal, Macros, Sex
from belok.i18n import Language


class MacrosOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kcal: float
    protein: float
    fat: float
    carbs: float


class MealItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    grams: float
    kcal: float
    protein: float
    fat: float
    carbs: float


class MealOut(BaseModel):
    id: int
    day: date
    created_at: datetime
    source: str
    title: str
    scale: float
    items: list[MealItemOut]
    totals: MacrosOut

    @classmethod
    def of(cls, meal: Meal) -> "MealOut":
        return cls(
            id=meal.id,
            day=meal.day,
            created_at=meal.created_at,
            source=meal.source,
            title=meal.title,
            scale=meal.scale,
            items=[MealItemOut.model_validate(i) for i in meal.items],
            totals=MacrosOut.model_validate(meal.totals()),
        )


class DayOut(BaseModel):
    day: date
    eaten: MacrosOut
    target: MacrosOut | None
    steps: int
    activity_kcal: float
    weight_kg: float | None
    meals: list[MealOut]
    sets: list[SetOut]


class MeOut(BaseModel):
    id: int
    username: str | None
    profile_complete: bool
    sex: Sex | None
    age: int | None
    height_cm: int | None
    goal: Goal | None
    weight_kg: float | None
    timezone: str
    language: Language | None
    trial_ends_at: datetime
    subscription_until: datetime | None
    has_access: bool
    status: str
    access_until: datetime
    is_admin: bool
    base_target: MacrosOut | None


class LanguageIn(BaseModel):
    language: Language


class PlanOut(BaseModel):
    code: str
    days: int
    link: str
    web_link: str
    amount: int | None
    currency: str | None


class PromoRedeemIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class PromoRedeemOut(BaseModel):
    days: int
    access_until: datetime


class ReferralOut(BaseModel):
    link: str | None
    invited: int
    paid: int
    days: int
    trial_days: int
    reward_days: int


class ProfileIn(BaseModel):
    sex: Sex
    age: int = Field(ge=12, le=100)
    height_cm: int = Field(ge=120, le=230)
    weight_kg: float = Field(ge=30, le=300)
    goal: Goal
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str | None) -> str | None:
        if value is not None and value not in available_timezones():
            raise ValueError("unknown timezone")
        return value if value is None else ZoneInfo(value).key


class WebAppAuthIn(BaseModel):
    init_data: str = Field(max_length=4096)


class WidgetAuthIn(BaseModel):
    id: int
    auth_date: int
    hash: str
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None


class TokenOut(BaseModel):
    token: str


class PublicConfigOut(BaseModel):
    bot_username: str | None


class TextMealIn(BaseModel):
    text: str = Field(min_length=2, max_length=500)


class MealPatchIn(BaseModel):
    scale: float = Field(ge=0.25, le=5)


class WeightIn(BaseModel):
    weight_kg: float = Field(ge=30, le=300)


class WeightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    weight_kg: float


class StepsIn(BaseModel):
    steps: int = Field(ge=0, le=100_000)


def macros_out(m: Macros | None) -> MacrosOut | None:
    return None if m is None else MacrosOut.model_validate(m)
