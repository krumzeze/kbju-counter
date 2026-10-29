import base64
import time
from dataclasses import dataclass

from anthropic import AnthropicError, AsyncAnthropic
from pydantic import BaseModel, Field, ValidationError

SYSTEM_PROMPT = """You estimate the nutritional content of meals.
Identify each distinct food item. Estimate its portion weight in grams from visual cues \
(plate and utensil size, typical servings) or from the user's description, then estimate \
calories, protein, fat and carbohydrates for that portion.
Write the title and item names in Russian. If there is no food, return an empty items list."""

# USD per million input and output tokens.
PRICES = {"claude-haiku-5-5": (0.10, 0.50)}


class FoodItem(BaseModel):
    name: str = Field(max_length=255)
    grams: float = Field(ge=0)
    kcal: float = Field(ge=0)
    protein: float = Field(ge=0)
    fat: float = Field(ge=0)
    carbs: float = Field(ge=0)


class FoodAnalysis(BaseModel):
    title: str = Field(default="Приём пищи", max_length=255)
    items: list[FoodItem] = Field(default_factory=list)


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

    async def from_photo(self, image: bytes, caption: str | None = None) -> AnalysisResult:
        content: list[dict] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.standard_b64encode(image).decode(),
                },
            }
        ]
        if caption:
            content.append({"type": "text", "text": f"User note: {caption}"})
        return await self._complete(content)

    async def from_text(self, text: str) -> AnalysisResult:
        return await self._complete([{"type": "text", "text": text}])

    async def _complete(self, content: list[dict]) -> AnalysisResult:
        started = time.monotonic()
        try:
            response = await self._client.messages.parse(
                model=self.model,
                max_tokens=8000,
                system=SYSTEM_PROMPT,
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
            cost_usd=_cost(response.model, usage.input_tokens, usage.output_tokens),
            latency_ms=_elapsed_ms(started),
        )


def _cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    prices = PRICES.get(model)
    if prices is None:
        return None
    return (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
