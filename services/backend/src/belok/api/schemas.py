from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator

from belok.api.workout_schemas import SetOut
from belok.db.models import Meal
from belok.domain import adaptive
from belok.domain.nutrition import Goal, Macros, Sex
from belok.i18n import Language
from belok.services.targets import TargetSource


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
    photo_url: str | None = None

    @classmethod
    def of(cls, meal: Meal, photo_url: str | None = None) -> "MealOut":
        return cls(
            id=meal.id,
            day=meal.day,
            created_at=meal.created_at,
            source=meal.source,
            title=meal.title,
            scale=meal.scale,
            items=[MealItemOut.model_validate(i) for i in meal.items],
            totals=MacrosOut.model_validate(meal.totals()),
            photo_url=photo_url,
        )


class DayOut(BaseModel):
    day: date
    eaten: MacrosOut
    target: MacrosOut | None
    target_source: TargetSource | None
    # Adaptive target is switched on but there is not enough recent data, so the formula is used.
    adaptive_paused: bool
    steps: int
    water_ml: int
    water_target_ml: int | None
    activity_kcal: float
    weight_kg: float | None
    meals: list[MealOut]
    sets: list[SetOut]


class AdaptiveOut(BaseModel):
    ready: bool
    logged_days: int
    weigh_ins: int
    span_days: int
    need_logged_days: int = adaptive.MIN_LOGGED_DAYS
    need_weigh_ins: int = adaptive.MIN_WEIGH_INS
    need_span_days: int = adaptive.MIN_WEIGHT_SPAN_DAYS
    window_days: int = adaptive.WINDOW_DAYS
    # Measured maintenance and the formula estimate it replaces, both without the goal factor.
    tdee: float | None
    formula_tdee: float


class MeOut(BaseModel):
    id: int
    username: str | None
    first_name: str | None
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
    activity_adjust: bool
    adaptive_target: bool
    remind_meals: bool
    remind_weight: bool
    photo_eval_consent: bool
    photo_storage: bool
    adaptive: AdaptiveOut | None
    base_target: MacrosOut | None
    features: dict[str, bool]
    analyses_left: int
    free_history_days: int


class LanguageIn(BaseModel):
    language: Language


class SettingsIn(BaseModel):
    activity_adjust: bool | None = None
    adaptive_target: bool | None = None
    remind_meals: bool | None = None
    remind_weight: bool | None = None
    photo_eval_consent: bool | None = None


class PlanOut(BaseModel):
    provider: Literal["stars", "tribute"]
    code: str
    days: int
    link: str | None
    web_link: str | None
    amount: int | None
    currency: str | None


class StarsInvoiceOut(BaseModel):
    link: str


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


class RefineMealIn(BaseModel):
    text: str = Field(min_length=2, max_length=300)


class MealPatchIn(BaseModel):
    scale: float = Field(ge=0.25, le=5)


class MealItemPatchIn(BaseModel):
    grams: float = Field(ge=1, le=3000)


class ManualMealIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    grams: float = Field(ge=1, le=3000)
    kcal: float = Field(ge=0, le=900)
    protein: float = Field(ge=0, le=100)
    fat: float = Field(ge=0, le=100)
    carbs: float = Field(ge=0, le=100)
    # Saves the label under this barcode so the next scan finds it.
    barcode: str | None = Field(default=None, pattern=r"^\d{8,14}$")

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("empty title")
        return value.strip()


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    kcal: float
    protein: float
    fat: float
    carbs: float
    serving_g: float | None


class BarcodeOut(BaseModel):
    code: str
    product: ProductOut | None


class MealHistoryOut(BaseModel):
    meal_id: int
    title: str
    source: str
    times: int
    last_eaten: datetime
    totals: MacrosOut


class WeightIn(BaseModel):
    weight_kg: float = Field(ge=30, le=300)


class WeightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    weight_kg: float


class StatsDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    eaten: MacrosOut
    steps: int
    water_ml: int
    sets: int


class StatsOut(BaseModel):
    days: list[StatsDayOut]
    target: MacrosOut | None
    water_target_ml: int | None
    limited: bool


class StepsIn(BaseModel):
    steps: int = Field(ge=0, le=100_000)


class WaterIn(BaseModel):
    delta_ml: int = Field(ge=-2000, le=2000)


class WaterOut(BaseModel):
    water_ml: int


def macros_out(m: Macros | None) -> MacrosOut | None:
    return None if m is None else MacrosOut.model_validate(m)
