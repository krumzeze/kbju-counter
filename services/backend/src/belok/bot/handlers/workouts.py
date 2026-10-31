from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot.texts import short_date, t
from belok.db.models import User
from belok.domain.workouts import (
    WorkoutParseError,
    estimated_1rm,
    normalize_exercise,
    parse_workout,
)
from belok.i18n import Language
from belok.services.repo import add_sets, exercise_history, get_or_create_exercise, list_exercises
from belok.timeutil import local_today

router = Router(name="workouts")


@router.message(Command("gym"))
async def cmd_gym(
    message: Message, command: CommandObject, session: AsyncSession, user: User, lang: Language
) -> None:
    try:
        name, sets = parse_workout(command.args or "")
    except WorkoutParseError:
        await message.answer(t(lang, "gym_usage"))
        return
    exercise = await get_or_create_exercise(session, user.id, name)
    await add_sets(session, user.id, exercise, local_today(user.timezone), sets)
    best = max(estimated_1rm(s.weight_kg, s.reps) for s in sets)
    await message.answer(t(lang, "gym_saved", name=escape(name), sets=len(sets), best=best))


@router.message(Command("progress"))
async def cmd_progress(
    message: Message, command: CommandObject, session: AsyncSession, user: User, lang: Language
) -> None:
    exercises = await list_exercises(session, user.id)
    if not command.args:
        if not exercises:
            await message.answer(t(lang, "no_exercises") + "\n\n" + t(lang, "gym_usage"))
            return
        await message.answer(
            t(lang, "your_exercises")
            + "\n"
            + "\n".join(f"• {escape(e)}" for e in exercises)
            + "\n\n"
            + t(lang, "progress_example", name=escape(exercises[0]))
        )
        return

    name = normalize_exercise(command.args)
    history = await exercise_history(session, user.id, name, limit=10)
    if not history:
        await message.answer(t(lang, "no_history", name=escape(name)))
        return

    lines = [t(lang, "recent_workouts", name=escape(name))]
    for day, sets in history:
        top = max(sets, key=lambda s: estimated_1rm(s.weight_kg, s.reps))
        lines.append(
            t(
                lang,
                "workout_line",
                day=short_date(lang, day),
                weight=top.weight_kg,
                reps=top.reps,
                e1rm=estimated_1rm(top.weight_kg, top.reps),
                sets=len(sets),
            )
        )
    first = max(estimated_1rm(s.weight_kg, s.reps) for s in history[0][1])
    last = max(estimated_1rm(s.weight_kg, s.reps) for s in history[-1][1])
    lines.append("\n" + t(lang, "e1rm_change", delta=last - first))
    await message.answer("\n".join(lines))
