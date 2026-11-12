from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from belok.api.schemas import MacrosOut
from belok.db.models import RecipeStatus
from belok.services.photos import KEY_RE


def _strip(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("empty")
    return value


class RecipeItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    grams: float = Field(gt=0, le=10000)
    kcal: float = Field(ge=0, le=100000)
    protein: float = Field(ge=0, le=10000)
    fat: float = Field(ge=0, le=10000)
    carbs: float = Field(ge=0, le=10000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip(value)

    @model_validator(mode="after")
    def per_100g_limits(self) -> "RecipeItemIn":
        if self.kcal / self.grams > 9.5 or max(self.protein, self.fat, self.carbs) > self.grams:
            raise ValueError("implausible_item")
        return self


class StepIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    photo: str | None = Field(default=None, max_length=64)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("photo")
    @classmethod
    def valid_key(cls, value: str | None) -> str | None:
        if value is not None and not KEY_RE.match(value):
            raise ValueError("invalid_photo")
        return value


class RecipeIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    portions: int = Field(ge=1, le=50)
    cooked_grams: float | None = Field(default=None, gt=0, le=50000)
    items: list[RecipeItemIn] = Field(min_length=1, max_length=40)
    steps: list[StepIn] = Field(default_factory=list, max_length=30)
    photo: str | None = Field(default=None, max_length=64)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        return _strip(value)

    @field_validator("photo")
    @classmethod
    def valid_key(cls, value: str | None) -> str | None:
        if value is not None and not KEY_RE.match(value):
            raise ValueError("invalid_photo")
        return value


class RecipeItemOut(BaseModel):
    name: str
    grams: float
    kcal: float
    protein: float
    fat: float
    carbs: float


class StepOut(BaseModel):
    text: str
    photo: str | None
    photo_url: str | None


class RecipeRef(BaseModel):
    id: int
    title: str


class RecipeCardOut(BaseModel):
    id: int
    title: str
    status: RecipeStatus
    portions: int
    per_portion: MacrosOut
    photo_url: str | None
    author_name: str | None
    is_mine: bool
    is_favorite: bool
    favorites: int
    rating: float | None
    ratings: int
    cooked: int


class RecipeOut(RecipeCardOut):
    cooked_grams: float | None
    raw_grams: float
    totals: MacrosOut
    items: list[RecipeItemOut]
    steps: list[StepOut]
    photo: str | None
    reject_reason: str | None
    forked_from: RecipeRef | None
    my_rating: int | None
    can_rate: bool
    created_at: datetime


class AdminRecipeOut(RecipeOut):
    owner_id: int
    owner_name: str | None
    warnings: list[str]


class DiaryIn(BaseModel):
    mode: Literal["portions", "grams"]
    portions: float | None = Field(default=None, gt=0, le=50)
    grams: float | None = Field(default=None, gt=0, le=20000)
    cooked_grams: float | None = Field(default=None, gt=0, le=50000)
    items: list[float] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def amount_for_mode(self) -> "DiaryIn":
        if (self.mode == "portions") != (self.portions is not None):
            raise ValueError("invalid_amount")
        if self.mode == "grams" and self.grams is None:
            raise ValueError("invalid_amount")
        if any(not 0 <= g <= 10000 for g in self.items):
            raise ValueError("invalid_items")
        return self


class PublishIn(BaseModel):
    author_name: str = Field(min_length=1, max_length=64)

    @field_validator("author_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip(value)


class RatingIn(BaseModel):
    stars: int = Field(ge=1, le=5)


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class IngredientsIn(BaseModel):
    text: str = Field(min_length=2, max_length=2000)


class PhotoUploadOut(BaseModel):
    photo: str
    photo_url: str | None
