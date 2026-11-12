"""Chat widgets: live day card, meal editing and one-tap logging inside the bot chat."""

import json
import logging
import zlib
from contextlib import suppress
from datetime import date, time, timedelta
from html import escape
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from belok.bot.texts import t
from belok.db.models import Meal, Recipe, User
from belok.domain.nutrition import water_target_ml
from belok.i18n import Language
from belok.services import features
from belok.services.features import Feature
from belok.services.meals import copy_meal, meal_history, resize_item
from belok.services.recipes import RecipeError, get_visible, to_meal
from belok.services.repo import (
    add_water,
    day_summary,
    get_meal,
    latest_weight,
    recent_weights,
    upsert_weight,
)
from belok.timeutil import local_today
from belok.widgets import html
from belok.widgets.api import AnswerWidgetQuery, EditMessageWidgetData, SendWidget, WidgetQuery

log = logging.getLogger(__name__)

MAX_STATE_BYTES = 1024
MAX_ITEMS = 8
MAX_GRAMS = 3000
STEP_GOAL = 10_000
QUICK_MEALS = 3
WEIGHT_HISTORY = 14
USUAL_DAYS = 28


async def enabled(session: AsyncSession) -> bool:
    return await features.enabled(session, Feature.WIDGETS)


def _lang(user: User) -> str:
    return (user.language or Language.RU).value


def _short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _dump(state: dict[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False, separators=(",", ":"))


def _fit(state: dict[str, Any], shrink) -> str:
    """Serialize the state, shortening names until it fits the widget data limit."""
    for limit in (28, 22, 16, 12, 8):
        data = _dump(shrink(state, limit))
        if len(data.encode()) <= MAX_STATE_BYTES:
            return data
    raise ValueError("widget state too large")


def app_markup(user: User, webapp_url: str | None) -> InlineKeyboardMarkup | None:
    if not webapp_url:
        return None
    button = InlineKeyboardButton(
        text=t(user.language or Language.RU, "open_app"), web_app=WebAppInfo(url=webapp_url)
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def _items(meal: Meal) -> list:
    return sorted(meal.items, key=lambda i: i.id)


async def meal_state(session: AsyncSession, user: User, meal: Meal) -> str:
    summary = await day_summary(session, user, meal.day)
    totals = meal.totals()
    s = meal.scale
    state = {
        "l": _lang(user),
        "id": meal.id,
        "t": meal.title,
        "i": [
            [
                i.name,
                round(i.grams * s),
                *(round(v * s, 1) for v in (i.kcal, i.protein, i.fat, i.carbs)),
            ]
            for i in _items(meal)
        ],
        "e": round(summary.eaten.kcal - totals.kcal),
        "K": round(summary.target.macros.kcal) if summary.target else 0,
    }

    def shrink(st: dict[str, Any], limit: int) -> dict[str, Any]:
        items = [[_short(i[0], limit), *i[1:]] for i in st["i"]]
        return {**st, "t": _short(st["t"], limit + 12), "i": items}

    return _fit(state, shrink)


async def day_state(session: AsyncSession, user: User) -> str:
    today = local_today(user.timezone)
    s = await day_summary(session, user, today)
    target = s.target.macros if s.target else None
    quick = await meal_history(session, user.id, True, QUICK_MEALS)
    last = await session.scalar(
        select(Meal)
        .where(Meal.user_id == user.id, Meal.day == today)
        .order_by(Meal.created_at.desc(), Meal.id.desc())
        .limit(1)
    )
    state = {
        "l": _lang(user),
        "d": today.isoformat(),
        "k": round(s.eaten.kcal),
        "p": round(s.eaten.protein),
        "f": round(s.eaten.fat),
        "c": round(s.eaten.carbs),
        "K": round(target.kcal) if target else 0,
        "P": round(target.protein) if target else 0,
        "F": round(target.fat) if target else 0,
        "C": round(target.carbs) if target else 0,
        "w": s.water_ml,
        "W": water_target_ml(s.weight_kg) if s.weight_kg else 0,
        "s": s.steps,
        "S": STEP_GOAL,
        "q": [[m.id, m.title, round(m.totals().kcal)] for m, _ in quick],
        "u": last.title if last else None,
    }

    def shrink(st: dict[str, Any], limit: int) -> dict[str, Any]:
        quick = [[m[0], _short(m[1], limit), m[2]] for m in st["q"]]
        return {**st, "q": quick, "u": _short(st["u"], limit + 8) if st["u"] else None}

    return _fit(state, shrink)


async def weight_state(session: AsyncSession, user: User) -> str:
    today = local_today(user.timezone)
    weights = await recent_weights(session, user.id, WEIGHT_HISTORY + 1)
    logged = next((w.weight_kg for w in weights if w.day == today), None)
    history = [w.weight_kg for w in sorted(weights, key=lambda w: w.day) if w.day != today]
    return _dump(
        {
            "l": _lang(user),
            "v": await latest_weight(session, user.id),
            "h": history[-WEIGHT_HISTORY:],
            "t": logged,
        }
    )


async def usual_meals(
    session: AsyncSession, user: User, since: time, until: time, today: date
) -> list[Meal]:
    """Meals the user logs most often between these local times."""
    local = func.timezone(user.timezone, Meal.created_at)
    clock = cast(local, Date)
    minute = func.extract("hour", local) * 60 + func.extract("minute", local)
    rows = (
        await session.execute(
            select(func.max(Meal.id))
            .where(
                Meal.user_id == user.id,
                Meal.day >= today - timedelta(days=USUAL_DAYS),
                clock == Meal.day,
                minute >= since.hour * 60 + since.minute,
                minute < until.hour * 60 + until.minute,
            )
            .group_by(func.lower(Meal.title))
            .order_by(func.count().desc(), func.max(Meal.created_at).desc())
            .limit(QUICK_MEALS)
        )
    ).all()
    ids = [r[0] for r in rows]
    meals = {m.id: m for m in await session.scalars(select(Meal).where(Meal.id.in_(ids)))}
    return [meals[i] for i in ids]


def usual_state(user: User, meals: list[Meal]) -> str:
    state = {"l": _lang(user), "q": [[m.id, m.title, round(m.totals().kcal)] for m in meals]}

    def shrink(st: dict[str, Any], limit: int) -> dict[str, Any]:
        return {**st, "q": [[m[0], _short(m[1], limit + 12), m[2]] for m in st["q"]]}

    return _fit(state, shrink)


async def send(
    bot: Bot,
    user: User,
    name: str,
    state: str | None,
    caption: str,
    markup: InlineKeyboardMarkup | None = None,
    quiet: bool = False,
    code: str | None = None,
) -> Message:
    return await bot(
        SendWidget(
            chat_id=user.id,
            html=code or html(name),
            chat_data=state,
            caption=caption,
            parse_mode="HTML",
            allow_queries=True,
            disable_notification=quiet or None,
            reply_markup=markup,
        )
    )


MAX_HTML_BYTES = 32768
MAX_COMPRESSED_BYTES = 4096
COOK_TEXT_LIMITS = (600, 300, 160, 80)


def cook_html(user: User, recipe: Recipe) -> str:
    """The cooking widget with the recipe inlined, steps shortened until it fits."""
    template = html("cook")
    for limit in COOK_TEXT_LIMITS:
        steps = [s["text"] for s in recipe.steps]
        short = [_short(text, limit) for text in steps]
        data = {
            "l": _lang(user),
            "id": recipe.id,
            "t": _short(recipe.title, 80),
            "p": recipe.portions,
            "c": round(recipe.cooked_grams) if recipe.cooked_grams else 0,
            "r": round(recipe.raw_grams()),
            "i": [
                [
                    _short(i.name, 40),
                    round(i.grams),
                    *(round(v, 1) for v in (i.kcal, i.protein, i.fat, i.carbs)),
                ]
                for i in recipe.items
            ],
            "s": short,
            "x": short != steps,
        }
        payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        code = template.replace("/*DATA*/null", payload).encode()
        if len(code) <= MAX_HTML_BYTES and len(zlib.compress(code, 9)) <= MAX_COMPRESSED_BYTES:
            return code.decode()
    raise ValueError("recipe too long for a widget")


async def send_recipe(
    bot: Bot, session: AsyncSession, user: User, recipe: Recipe, webapp_url: str | None
) -> bool:
    if not await enabled(session) or not recipe.items:
        return False
    lang = user.language or Language.RU
    markup = None
    if webapp_url:
        url = f"{webapp_url.rstrip('/')}/recipes/{recipe.id}"
        button = InlineKeyboardButton(text=t(lang, "open_recipe"), web_app=WebAppInfo(url=url))
        markup = InlineKeyboardMarkup(inline_keyboard=[[button]])
    try:
        code = cook_html(user, recipe)
        caption = t(lang, "cook_caption", title=escape(recipe.title))
        await send(bot, user, "cook", None, caption, markup, code=code)
    except (TelegramAPIError, ValueError):
        log.warning("cook widget for %s failed", user.id, exc_info=True)
        return False
    return True


async def send_meal(
    bot: Bot, session: AsyncSession, user: User, meal: Meal, caption: str, webapp_url: str | None
) -> bool:
    """Send a recognized meal as an editable widget; False when the caller should send text."""
    if len(meal.items) > MAX_ITEMS or not await enabled(session):
        return False
    try:
        state = await meal_state(session, user, meal)
        await send(bot, user, "meal", state, caption, app_markup(user, webapp_url))
    except (TelegramBadRequest, ValueError):
        log.warning("meal widget for %s failed", user.id, exc_info=True)
        return False
    return True


async def send_day_card(
    bot: Bot, session: AsyncSession, user: User, webapp_url: str | None
) -> bool:
    """Send a fresh day card, pin it and retire the previous one."""
    if not await enabled(session):
        return False
    lang = user.language or Language.RU
    try:
        message = await send(
            bot,
            user,
            "day",
            await day_state(session, user),
            t(lang, "day_card_caption"),
            app_markup(user, webapp_url),
            quiet=True,
        )
    except (TelegramBadRequest, ValueError):
        log.warning("day card for %s failed", user.id, exc_info=True)
        return False
    previous, user.day_card_message_id = user.day_card_message_id, message.message_id
    await session.commit()
    with suppress(TelegramAPIError):
        await bot.pin_chat_message(user.id, message.message_id, disable_notification=True)
    if previous:
        with suppress(TelegramAPIError):
            await bot.unpin_chat_message(user.id, message_id=previous)
        with suppress(TelegramAPIError):
            await bot.delete_message(user.id, previous)
    return True


async def _edit(bot: Bot, chat_id: int, message_id: int, state: str) -> bool:
    """Replace widget data; False when the message is gone."""
    try:
        await bot(EditMessageWidgetData(chat_id=chat_id, message_id=message_id, chat_data=state))
    except TelegramBadRequest as exc:
        if "not modified" in exc.message:
            return True
        log.info("widget %s/%s not editable: %s", chat_id, message_id, exc.message)
        return False
    return True


async def refresh_day_card(bot: Bot, session: AsyncSession, user: User) -> None:
    if user.day_card_message_id is None:
        return
    try:
        state = await day_state(session, user)
        if not await _edit(bot, user.id, user.day_card_message_id, state):
            user.day_card_message_id = None
            await session.commit()
    except (TelegramAPIError, ValueError):
        log.warning("day card refresh for %s failed", user.id, exc_info=True)


async def _save_meal(session: AsyncSession, user: User, arg: str) -> Meal | None | bool:
    """Apply edited grams; returns the meal, None when it was deleted, False when invalid."""
    meal_id, _, raw = arg.partition(":")
    try:
        grams = [int(g) for g in raw.split(",")]
        meal = await get_meal(session, user.id, int(meal_id))
    except ValueError:
        return False
    items = _items(meal) if meal else []
    if meal is None or len(grams) != len(items) or any(not 0 <= g <= MAX_GRAMS for g in grams):
        return False
    if not any(grams):
        await session.delete(meal)
        return None
    for item, g in zip(items, grams, strict=True):
        if g == 0:
            meal.items.remove(item)
        elif g != round(item.grams * meal.scale):
            resize_item(meal, item, g)
    return meal


async def _cook(session: AsyncSession, user: User, arg: str, today: date) -> bool:
    """c:<id>:p:<servings>[:<grams>] or c:<id>:g:<grams eaten>:<cooked>[:<grams>]"""
    parts = arg.split(":")
    try:
        recipe = await get_visible(session, user, int(parts[0]))
        mode = parts[1]
        amount = float(parts[2])
        cooked = float(parts[3]) if mode == "g" else None
        rest = parts[4:] if mode == "g" else parts[3:]
        if mode not in ("p", "g") or len(rest) > 1:
            return False
        grams = [float(g) for g in rest[0].split(",")] if rest else [i.grams for i in recipe.items]
        if any(not 0 <= g <= 10000 for g in grams) or not 0 < amount <= 20000:
            return False
        meal = to_meal(
            recipe,
            user,
            today,
            grams,
            amount if mode == "p" else None,
            amount if mode == "g" else None,
            cooked if cooked and cooked > 0 else None,
        )
    except (ValueError, IndexError, RecipeError):
        return False
    session.add(meal)
    return True


async def _apply(session: AsyncSession, user: User, kind: str, arg: str) -> Meal | None | bool:
    today = local_today(user.timezone)
    if kind == "c":
        return await _cook(session, user, arg, today)
    if kind == "s":
        return await _save_meal(session, user, arg)
    if kind == "r" and arg.isdigit():
        meal = await get_meal(session, user.id, int(arg))
        if meal is None:
            return False
        session.add(copy_meal(meal, today))
        return True
    if kind == "w" and arg.isdigit() and 0 < int(arg) <= 1000:
        await add_water(session, user.id, today, int(arg))
        return True
    if kind == "u":
        last = await session.scalar(
            select(Meal)
            .where(Meal.user_id == user.id, Meal.day == today)
            .order_by(Meal.created_at.desc(), Meal.id.desc())
            .limit(1)
        )
        if last is None:
            return False
        await session.delete(last)
        return True
    if kind == "wt":
        try:
            weight = float(arg)
        except ValueError:
            return False
        if not 20 <= weight <= 400:
            return False
        await upsert_weight(session, user.id, today, round(weight, 1))
        return True
    return False


async def answer_query(
    bot: Bot, session: AsyncSession, user: User | None, query: WidgetQuery
) -> None:
    kind, _, arg = query.data.partition(":")
    result: Meal | None | bool = False
    if user is not None and not user.is_blocked:
        result = await _apply(session, user, kind, arg)
    ok = result is not False
    if ok:
        await session.commit()
    await bot(AnswerWidgetQuery(widget_query_id=query.id, data="ok" if ok else "error"))
    if not ok or user is None:
        return
    if kind == "s" and query.message_id is not None:
        state = (
            await meal_state(session, user, result)
            if isinstance(result, Meal)
            else _dump({"l": _lang(user), "x": 1})
        )
        with suppress(TelegramAPIError):
            await _edit(bot, user.id, query.message_id, state)
    await refresh_day_card(bot, session, user)
