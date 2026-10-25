from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot import texts
from belok.db.models import User
from belok.domain.nutrition import steps_kcal
from belok.services.repo import (
    day_summary,
    latest_weight,
    recent_weights,
    upsert_steps,
    upsert_weight,
)
from belok.timeutil import local_today

router = Router(name="tracking")


@router.message(Command("weight"))
async def cmd_weight(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    if not command.args:
        weights = await recent_weights(session, user.id, 10)
        if not weights:
            await message.answer("Пока нет записей. Пример: /weight 82.5")
            return
        lines = [f"{w.day:%d.%m}: {w.weight_kg:.1f} кг" for w in reversed(weights)]
        delta = weights[0].weight_kg - weights[-1].weight_kg
        lines.append(f"\nИзменение: {delta:+.1f} кг")
        await message.answer("\n".join(lines))
        return
    try:
        weight = float(command.args.replace(",", "."))
    except ValueError:
        weight = 0
    if not 30 <= weight <= 300:
        await message.answer("Пример: /weight 82.5")
        return
    await upsert_weight(session, user.id, local_today(user.timezone), weight)
    await message.answer(f"Записал вес: {weight:.1f} кг")


@router.message(Command("steps"))
async def cmd_steps(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    raw = (command.args or "").replace(" ", "")
    if not raw.isdigit() or int(raw) > 100_000:
        await message.answer("Пример: /steps 8500")
        return
    steps = int(raw)
    await upsert_steps(session, user.id, local_today(user.timezone), steps)
    weight = await latest_weight(session, user.id) or 70
    await message.answer(
        f"Записал {steps} шагов, это примерно +{steps_kcal(steps, weight):.0f} ккал к норме"
    )


@router.message(Command("today"))
async def cmd_today(message: Message, session: AsyncSession, user: User) -> None:
    summary = await day_summary(session, user, local_today(user.timezone))
    await message.answer(texts.day_card(summary))
