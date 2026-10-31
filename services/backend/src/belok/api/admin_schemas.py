from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from belok.api.schemas import MealOut
from belok.services.admin_users import Segment
from belok.services.promos import CODE_PATTERN, normalize_code


class DayPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    new_users: int
    active_users: int
    analyses: int
    errors: int
    cost_usd: float


class CountOut(BaseModel):
    key: str
    count: int


class DashboardOut(BaseModel):
    users_total: int
    new_today: int
    new_7d: int
    new_30d: int
    dau: int
    wau: int
    mau: int
    statuses: dict[str, int]
    blocked: int
    bot_blocked: int
    funnel: list[CountOut]
    cost_today: float
    cost_month: float
    cost_forecast: float
    avg_cost: float | None
    requests_24h: int
    error_rate_24h: float | None
    no_food_rate_24h: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    referred_users: int
    referral_rewards: int
    promo_redemptions_30d: int
    sources: list[CountOut]
    series: list[DayPointOut]


class UserBriefOut(BaseModel):
    id: int
    username: str | None
    first_name: str | None


class UserRowOut(UserBriefOut):
    created_at: datetime
    last_seen_at: datetime | None
    status: str
    access_until: datetime
    analyses: int
    cost_usd: float
    is_admin: bool
    is_blocked: bool
    bot_blocked: bool


class UserPageOut(BaseModel):
    items: list[UserRowOut]
    total: int


class ActivityDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    meals: int
    sets: int
    steps: int
    analyses: int


class LlmCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    kind: str
    model: str
    ok: bool
    no_food: bool
    cost_usd: float | None
    latency_ms: int


class RedemptionOut(BaseModel):
    code: str
    days: int
    created_at: datetime


class ActionOut(BaseModel):
    id: int
    created_at: datetime
    action: str
    admin: UserBriefOut | None
    target: UserBriefOut | None
    target_user_id: int | None
    details: dict | None


class UserDetailOut(UserRowOut):
    source: str | None
    timezone: str
    sex: str | None
    age: int | None
    height_cm: int | None
    goal: str | None
    weight_kg: float | None
    trial_ends_at: datetime
    subscription_until: datetime | None
    lifetime_access: bool
    daily_limit: int | None
    llm_errors: int
    llm_requests: int
    referred_by: UserBriefOut | None
    invited: int
    invited_paid: int
    referral_days: int
    activity: list[ActivityDayOut]
    meals: list[MealOut]
    llm: list[LlmCallOut]
    redemptions: list[RedemptionOut]
    actions: list[ActionOut]


class UserPatchIn(BaseModel):
    is_blocked: bool | None = None
    is_admin: bool | None = None
    lifetime_access: bool | None = None
    daily_limit: int | None = Field(default=None, ge=0, le=1000)


class GrantIn(BaseModel):
    days: int = Field(ge=1, le=3650)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class PromoIn(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    days: int = Field(ge=1, le=365)
    max_activations: int | None = Field(default=None, ge=1, le=1_000_000)
    expires_at: datetime | None = None
    new_users_only: bool = False
    note: str | None = Field(default=None, max_length=255)

    @field_validator("code")
    @classmethod
    def normalize(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        value = normalize_code(value)
        if not CODE_PATTERN.fullmatch(value):
            raise ValueError("code must be 3-32 characters: A-Z, 0-9, _ or -")
        return value


class PromoPatchIn(BaseModel):
    active: bool | None = None
    max_activations: int | None = Field(default=None, ge=1, le=1_000_000)
    expires_at: datetime | None = None


class PromoOut(BaseModel):
    id: int
    code: str
    days: int
    max_activations: int | None
    activations: int
    expires_at: datetime | None
    new_users_only: bool
    active: bool
    note: str | None
    created_at: datetime
    retained: int
    link: str | None


class BroadcastIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    segment: Segment


class BroadcastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    text: str
    segment: str
    status: str
    total: int
    sent: int
    failed: int
    blocked: int
    started_at: datetime | None
    finished_at: datetime | None


class ReferrerOut(UserBriefOut):
    invited: int
    paid: int
    days: int


class PrefsOut(BaseModel):
    new_users: bool
    payments: bool
    errors: bool
    daily: bool


class PrefsIn(BaseModel):
    new_users: bool | None = None
    payments: bool | None = None
    errors: bool | None = None
    daily: bool | None = None
