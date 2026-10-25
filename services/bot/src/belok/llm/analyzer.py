import base64
import time
from dataclasses import dataclass

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field, ValidationError

SYSTEM_PROMPT = """You estimate the nutritional content of meals.
Identify each distinct food item. Estimate its portion weight in grams from visual cues \
(plate and utensil size, typical servings) or from the user's description, then estimate \
calories, protein, fat and carbohydrates for that portion.
Write the title and item names in Russian. If there is no food, return an empty items list.
Respond with JSON only, in exactly this shape:
{"title": "short meal name", "items": [{"name": "...", "grams": 0, "kcal": 0, \
"protein": 0, "fat": 0, "carbs": 0}]}"""


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
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60, max_retries=2)
        self.model = model

    async def from_photo(self, image: bytes, caption: str | None = None) -> AnalysisResult:
        encoded = base64.b64encode(image).decode()
        content: list[dict] = [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
        ]
        if caption:
            content.append({"type": "text", "text": f"User note: {caption}"})
        return await self._complete(content)

    async def from_text(self, text: str) -> AnalysisResult:
        return await self._complete([{"type": "text", "text": text}])

    async def _complete(self, content: list[dict]) -> AnalysisResult:
        started = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                response_format={"type": "json_object"},
                extra_body={"usage": {"include": True}},
            )
            analysis = FoodAnalysis.model_validate_json(response.choices[0].message.content or "")
        except (OpenAIError, ValidationError, IndexError) as exc:
            raise AnalysisError(self.model, _elapsed_ms(started)) from exc

        usage = response.usage
        return AnalysisResult(
            analysis=analysis,
            model=response.model or self.model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            # OpenRouter reports the charged price as a non-standard "cost" field.
            cost_usd=(usage.model_extra or {}).get("cost") if usage else None,
            latency_ms=_elapsed_ms(started),
        )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
