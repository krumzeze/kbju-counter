import base64
import time
from dataclasses import dataclass

from anthropic import AnthropicError, AsyncAnthropic
from pydantic import BaseModel, Field, ValidationError

from belok.i18n import Language
from belok.llm import pricing

SYSTEM_PROMPT = """You estimate the nutritional content of meals.
Identify each distinct food item. Estimate its portion weight in grams from visual cues \
(plate and utensil size, typical servings) or from the user's description, then estimate \
calories, protein, fat and carbohydrates for that portion.
Write the title and item names in {language}. If there is no food, return an empty items list.

Ask a clarifying question only when one unknown would change the meal's calories by roughly \
20% or more: foods that look alike but differ in fat or sugar (chicken thigh or breast, \
whole or skim milk, sweetened drink or not), hidden oil, butter or sauce, or a portion the \
description leaves open. Ask at most one question with 2 to 4 short, mutually exclusive \
options in {language}. Base the items on the most likely option. Otherwise leave question null."""

REFINE_NOTE = "Return the full corrected meal, keeping items the correction does not touch. \
Do not ask a question."

LANGUAGE_NAMES = {Language.RU: "Russian", Language.EN: "English"}


class FoodItem(BaseModel):
    name: str = Field(max_length=255)
    grams: float = Field(ge=0)
    kcal: float = Field(ge=0)
    protein: float = Field(ge=0)
    fat: float = Field(ge=0)
    carbs: float = Field(ge=0)


class Clarification(BaseModel):
    text: str = Field(max_length=200)
    options: list[str] = Field(max_length=4)


class FoodAnalysis(BaseModel):
    title: str = Field(default="Meal", max_length=255)
    items: list[FoodItem] = Field(default_factory=list)
    question: Clarification | None = None

    def usable_question(self) -> Clarification | None:
        """The question when it is well formed, trimmed to what the UI can show."""
        q = self.question
        if q is None or not q.text.strip() or not self.items:
            return None
        options = [o.strip()[:60] for o in q.options if o.strip()][:4]
        if len(options) < 2:
            return None
        return Clarification(text=q.text.strip(), options=options)


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    analysis: FoodAnalysis
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None
    latency_ms: int


class AnalysisError(Exception):
    def __init__(self, model: str, latency_ms: int) -> None:
        super().__init__(f"food analysis failed with {model}")
        self.model = model
        self.latency_ms = latency_ms


class FoodAnalyzer:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key, timeout=60, max_retries=2)
        self.model = model

    async def ping(self) -> None:
        await self._client.models.retrieve(self.model, timeout=10)

    async def from_photo(
        self, image: bytes, media_type: str, caption: str | None, language: Language
    ) -> AnalysisResult:
        content: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(image).decode(),
                },
            }
        ]
        if caption:
            content.append({"type": "text", "text": f"User note: {caption}"})
        return await self._complete(content, language)

    async def from_text(self, text: str, language: Language) -> AnalysisResult:
        return await self._complete([{"type": "text", "text": text}], language)

    async def refine(
        self, previous: FoodAnalysis, correction: str, language: Language
    ) -> AnalysisResult:
        text = (
            f"Your previous estimate of this meal: {previous.model_dump_json()}\n"
            f"User correction: {correction}\n{REFINE_NOTE}"
        )
        return await self._complete([{"type": "text", "text": text}], language)

    async def clarify(
        self, previous: FoodAnalysis, question: str, answer: str, language: Language
    ) -> AnalysisResult:
        text = (
            f"Your previous estimate of this meal: {previous.model_dump_json()}\n"
            f"You asked: {question}\nUser answered: {answer}\n{REFINE_NOTE}"
        )
        return await self._complete([{"type": "text", "text": text}], language)

    async def _complete(self, content: list[dict], language: Language) -> AnalysisResult:
        started = time.monotonic()
        try:
            response = await self._client.messages.parse(
                model=self.model,
                max_tokens=8000,
                system=SYSTEM_PROMPT.format(language=LANGUAGE_NAMES[language]),
                messages=[{"role": "user", "content": content}],
                output_format=FoodAnalysis,
            )
        except (AnthropicError, ValidationError) as exc:
            raise AnalysisError(self.model, _elapsed_ms(started)) from exc
        if response.parsed_output is None:
            raise AnalysisError(self.model, _elapsed_ms(started))

        usage = response.usage
        return AnalysisResult(
            analysis=response.parsed_output,
            model=response.model,
            prompt_tokens=usage.input_tokens,
            completion_tokens=usage.output_tokens,
            cost_usd=pricing.cost(response.model, usage),
            latency_ms=_elapsed_ms(started),
        )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
