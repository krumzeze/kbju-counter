"""Build src/belok/data/exercises.json from free-exercise-db (Unlicense).

Russian translations already in the output file are kept; missing ones are produced with
Claude when LLM_API_KEY is set. Usage:

    LLM_API_KEY=... uv run python scripts/build_catalog.py [--source exercises.json]
"""

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path

from anthropic import AsyncAnthropic
from pydantic import BaseModel

COMMIT = "f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5"
SOURCE_URL = (
    f"https://raw.githubusercontent.com/yuhonas/free-exercise-db/{COMMIT}/dist/exercises.json"
)
OUTPUT = Path(__file__).resolve().parents[1] / "src/belok/data/exercises.json"
CATEGORIES = {"strength", "powerlifting", "cardio", "plyometrics"}
BATCH = 8

SYSTEM_PROMPT = """You translate gym exercise names and instructions from English to Russian.
Use the terminology Russian-speaking gym-goers and coaches actually use \
(e.g. "Жим штанги лёжа", "Тяга верхнего блока", "Румынская тяга", "Разведение гантелей"). \
Names must be short and natural, not literal. Keep the number and order of instruction steps. \
Return every input id exactly once."""


class Translation(BaseModel):
    id: str
    name: str
    instructions: list[str]


class Batch(BaseModel):
    items: list[Translation]


def load_source(path: str | None) -> list[dict]:
    if path:
        return json.loads(Path(path).read_text())
    with urllib.request.urlopen(SOURCE_URL, timeout=300) as response:
        return json.load(response)


def select(source: list[dict]) -> list[dict]:
    return [
        x
        for x in source
        if x["category"] in CATEGORIES
        and x["level"] != "expert"
        and x["images"]
        and x["instructions"]
        and x["equipment"] != "foam roll"
    ]


def convert(x: dict, previous: dict | None) -> dict:
    name = {"en": x["name"]}
    instructions = {"en": x["instructions"]}
    if previous and "ru" in previous["name"]:
        name["ru"] = previous["name"]["ru"]
        instructions["ru"] = previous["instructions"]["ru"]
    return {
        "id": x["id"],
        "name": name,
        "instructions": instructions,
        "primary": x["primaryMuscles"],
        "secondary": x["secondaryMuscles"],
        "equipment": x["equipment"] or "body only",
        "category": x["category"],
        "level": x["level"],
        "mechanic": x["mechanic"],
        "force": x["force"],
        "images": len(x["images"]),
    }


async def translate(client: AsyncAnthropic, model: str, batch: list[dict]) -> list[Translation]:
    payload = [
        {"id": x["id"], "name": x["name"]["en"], "instructions": x["instructions"]["en"]}
        for x in batch
    ]
    response = await client.messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        output_format=Batch,
    )
    return response.parsed_output.items if response.parsed_output else []


async def fill_translations(catalog: list[dict], api_key: str, model: str) -> None:
    client = AsyncAnthropic(api_key=api_key, timeout=180, max_retries=3)
    pending = [x for x in catalog if "ru" not in x["name"]]
    by_id = {x["id"]: x for x in pending}
    semaphore = asyncio.Semaphore(4)

    async def run(batch: list[dict]) -> None:
        async with semaphore:
            try:
                items = await translate(client, model, batch)
            except Exception as exc:  # noqa: BLE001
                print(f"batch failed: {exc}", file=sys.stderr)
                return
        for t in items:
            x = by_id.get(t.id)
            if x and len(t.instructions) == len(x["instructions"]["en"]):
                x["name"]["ru"] = t.name
                x["instructions"]["ru"] = t.instructions
        done = sum("ru" in x["name"] for x in pending)
        print(f"translated {done}/{len(pending)}", file=sys.stderr)
        write(catalog)

    await asyncio.gather(*(run(pending[i : i + BATCH]) for i in range(0, len(pending), BATCH)))


def write(catalog: list[dict]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="local copy of dist/exercises.json")
    args = parser.parse_args()

    previous = {}
    if OUTPUT.exists():
        previous = {x["id"]: x for x in json.loads(OUTPUT.read_text())}
    catalog = [convert(x, previous.get(x["id"])) for x in select(load_source(args.source))]
    catalog.sort(key=lambda x: x["name"]["en"])
    write(catalog)

    api_key = os.environ.get("LLM_API_KEY")
    if api_key:
        model = os.environ.get("LLM_MODEL", "claude-haiku-5-5")
        asyncio.run(fill_translations(catalog, api_key, model))
    missing = sum("ru" not in x["name"] for x in catalog)
    print(f"{len(catalog)} exercises, {missing} without Russian translation", file=sys.stderr)


if __name__ == "__main__":
    main()
