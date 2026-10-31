from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot.texts import short_date, t
from belok.db.models import User
from belok.domain.workouts import WorkoutParseError, estimated_1rm, parse_workout
from belok.i18n import Language
from belok.services import workouts as svc

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
    exercise = await svc.exercise_by_text(session, user.id, name)
    workout = await svc.workout_for_bot(session, user)
    await svc.add_parsed_sets(session, workout, exercise, sets)
    best = max(estimated_1rm(s.weight_kg, s.reps) for s in sets)
    title = escape(svc.title(exercise, lang))
    await message.answer(t(lang, "gym_saved", name=title, sets=len(sets), best=best))


@router.message(Command("progress"))
async def cmd_progress(
    message: Message, command: CommandObject, session: AsyncSession, user: User, lang: Language
) -> None:
    if not command.args:
        names = [
            svc.title(s.exercise, lang)
            for s in await svc.list_exercises(session, user.id)
            if s.sets
        ]
        if not names:
            await message.answer(t(lang, "no_exercises") + "\n\n" + t(lang, "gym_usage"))
            return
        await message.answer(
            t(lang, "your_exercises")
            + "\n"
            + "\n".join(f"• {escape(n)}" for n in names)
            + "\n\n"
            + t(lang, "progress_example", name=escape(names[0].lower()))
        )
        return

    exercise = await svc.find_exercise(session, user.id, command.args)
    history = []
    if exercise:
        history = await svc.exercise_history(session, user.id, exercise.id, limit=10)
    if not history:
        await message.answer(t(lang, "no_history", name=escape(command.args)))
        return

    name = svc.title(exercise, lang)

    lines = [t(lang, "recent_workouts", name=escape(name))]
    for day, sets in history:
        sets = [s for s in sets if s.reps]
        if not sets:
            continue
        top = max(sets, key=svc.set_e1rm)
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
    first = max(map(svc.set_e1rm, history[0][1]))
    last = max(map(svc.set_e1rm, history[-1][1]))
    lines.append("\n" + t(lang, "e1rm_change", delta=last - first))
    await message.answer("\n".join(lines))
