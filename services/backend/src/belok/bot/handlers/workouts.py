from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import User
from belok.domain.workouts import (
    WorkoutParseError,
    estimated_1rm,
    normalize_exercise,
    parse_workout,
)
from belok.services.repo import add_sets, exercise_history, get_or_create_exercise, list_exercises
from belok.timeutil import local_today

router = Router(name="workouts")

GYM_USAGE = (
    "Формат: /gym упражнение вес x повторы\n"
    "Например: /gym жим лежа 80x8 80x8 75x10\n"
    "Одинаковые подходы: /gym присед 100x5x3"
)


@router.message(Command("gym"))
async def cmd_gym(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    try:
        name, sets = parse_workout(command.args or "")
    except WorkoutParseError:
        await message.answer(GYM_USAGE)
        return
    exercise = await get_or_create_exercise(session, user.id, name)
    await add_sets(session, user.id, exercise, local_today(user.timezone), sets)
    best = max(estimated_1rm(s.weight_kg, s.reps) for s in sets)
    await message.answer(
        f"Записал: <b>{escape(name)}</b>, подходов: {len(sets)}\n"
        f"Расчётный максимум на 1 раз: ~{best:.1f} кг"
    )


@router.message(Command("progress"))
async def cmd_progress(
    message: Message, command: CommandObject, session: AsyncSession, user: User
) -> None:
    exercises = await list_exercises(session, user.id)
    if not command.args:
        if not exercises:
            await message.answer("Пока нет упражнений.\n\n" + GYM_USAGE)
            return
        await message.answer(
            "Твои упражнения:\n"
            + "\n".join(f"• {escape(e)}" for e in exercises)
            + "\n\nПример: /progress "
            + escape(exercises[0])
        )
        return

    name = normalize_exercise(command.args)
    history = await exercise_history(session, user.id, name, limit=10)
    if not history:
        await message.answer(f"Нет записей по «{escape(name)}». Посмотри список: /progress")
        return

    lines = [f"<b>{escape(name)}</b>, последние тренировки:"]
    for day, sets in history:
        top = max(sets, key=lambda s: estimated_1rm(s.weight_kg, s.reps))
        e1rm = estimated_1rm(top.weight_kg, top.reps)
        lines.append(
            f"{day:%d.%m}: {top.weight_kg:g}×{top.reps} (~{e1rm:.1f} кг), подходов {len(sets)}"
        )
    first = max(estimated_1rm(s.weight_kg, s.reps) for s in history[0][1])
    last = max(estimated_1rm(s.weight_kg, s.reps) for s in history[-1][1])
    lines.append(f"\nРасчётный максимум: {last - first:+.1f} кг")
    await message.answer("\n".join(lines))
