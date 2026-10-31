from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot import texts
from belok.bot.texts import t
from belok.db.models import User
from belok.domain.nutrition import steps_kcal
from belok.i18n import Language
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
    message: Message, command: CommandObject, session: AsyncSession, user: User, lang: Language
) -> None:
    if not command.args:
        weights = await recent_weights(session, user.id, 10)
        if not weights:
            await message.answer(t(lang, "no_weights"))
            return
        lines = [
            t(lang, "weight_entry", day=texts.short_date(lang, w.day), kg=w.weight_kg)
            for w in reversed(weights)
        ]
        delta = weights[0].weight_kg - weights[-1].weight_kg
        lines.append("\n" + t(lang, "weight_change", delta=delta))
        await message.answer("\n".join(lines))
        return
    try:
        weight = float(command.args.replace(",", "."))
    except ValueError:
        weight = 0
    if not 30 <= weight <= 300:
        await message.answer(t(lang, "weight_usage"))
        return
    await upsert_weight(session, user.id, local_today(user.timezone), weight)
    await message.answer(t(lang, "weight_saved", kg=weight))


@router.message(Command("steps"))
async def cmd_steps(
    message: Message, command: CommandObject, session: AsyncSession, user: User, lang: Language
) -> None:
    raw = (command.args or "").replace(" ", "")
    if not raw.isdigit() or int(raw) > 100_000:
        await message.answer(t(lang, "steps_usage"))
        return
    steps = int(raw)
    await upsert_steps(session, user.id, local_today(user.timezone), steps)
    weight = await latest_weight(session, user.id) or 70
    await message.answer(t(lang, "steps_saved", steps=steps, kcal=steps_kcal(steps, weight)))


@router.message(Command("today"))
async def cmd_today(message: Message, session: AsyncSession, user: User, lang: Language) -> None:
    summary = await day_summary(session, user, local_today(user.timezone))
    await message.answer(texts.day_card(lang, summary))
