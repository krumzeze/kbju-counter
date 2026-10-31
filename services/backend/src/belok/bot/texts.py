from datetime import date, datetime
from html import escape

from belok.config import Settings
from belok.db.models import Meal, Payment, User
from belok.domain.nutrition import Macros
from belok.i18n import Language
from belok.services.access import access_until
from belok.services.repo import DaySummary

RU, EN = Language.RU, Language.EN

STRINGS: dict[str, dict[Language, str]] = {
    "choose_language": {
        RU: "Выбери язык / Choose your language",
        EN: "Выбери язык / Choose your language",
    },
    "language_set": {RU: "Язык: русский", EN: "Language: English"},
    "help": {
        RU: """<b>Что я умею</b>

📸 Пришли фото еды, и я посчитаю КБЖУ. Можно добавить подпись, например «рис 150 г».
✍️ Или опиши текстом: <i>2 яйца, тост с маслом, кофе с молоком</i>

/today: итоги дня и норма
/weight 82.5: записать вес
/steps 8500: записать шаги
/gym жим лежа 80x8 80x8 75x10: записать подходы (можно 100x5x3)
/progress жим лежа: прогресс по упражнению
/profile: изменить анкету
/invite: пригласить друга
/promo КОД: активировать промокод
/language: сменить язык""",
        EN: """<b>What I can do</b>

📸 Send a food photo and I'll count calories and macros. Add a caption like "rice 150 g".
✍️ Or describe it in text: <i>2 eggs, buttered toast, coffee with milk</i>

/today: today's totals and target
/weight 82.5: log your weight
/steps 8500: log your steps
/gym bench press 80x8 80x8 75x10: log sets (or 100x5x3)
/progress bench press: exercise progress
/profile: update your profile
/invite: invite a friend
/promo CODE: redeem a promo code
/language: change language""",
    },
    "profile_required": {
        RU: "Сначала заполни короткую анкету: /start",
        EN: "First, fill in a quick profile: /start",
    },
    "access_expired": {
        RU: "Бесплатный период закончился. Все записи сохранены: "
        "оформи подписку, и всё снова заработает. /subscribe",
        EN: "Your free trial has ended. All your entries are saved: "
        "subscribe and everything works again. /subscribe",
    },
    "blocked": {RU: "Доступ к боту ограничен.", EN: "Your access to this bot has been restricted."},
    "promo_usage": {
        RU: "Напиши промокод после команды, например: /promo BELOK",
        EN: "Add the code after the command, e.g. /promo BELOK",
    },
    "promo_ok": {
        RU: "Промокод активирован: +{days} дн. доступа 🎉",
        EN: "Promo code redeemed: +{days} {unit} of access 🎉",
    },
    "not_found": {RU: "Такого промокода нет", EN: "This promo code doesn't exist"},
    "expired": {RU: "Срок действия промокода истёк", EN: "This promo code has expired"},
    "exhausted": {
        RU: "Промокод уже использовали максимальное число раз",
        EN: "This promo code has reached its usage limit",
    },
    "already_used": {
        RU: "Ты уже активировал этот промокод",
        EN: "You've already redeemed this promo code",
    },
    "new_users_only": {
        RU: "Этот промокод только для новых пользователей",
        EN: "This promo code is for new users only",
    },
    "too_many_attempts": {
        RU: "Слишком много попыток, попробуй через час",
        EN: "Too many attempts, try again in an hour",
    },
    "invites_unavailable": {RU: "Приглашения пока недоступны", EN: "Invites aren't available yet"},
    "invite": {
        RU: "<b>Приглашай друзей</b>\n\n"
        "Друг получит {trial} дней бесплатно вместо {base}, "
        "а ты +{reward} дней доступа за каждую его оплату подписки.\n\n"
        "Твоя ссылка:\n{link}\n\n"
        "Приглашено: {invited} · оплатили: {paid} · заработано дней: {days}",
        EN: "<b>Invite friends</b>\n\n"
        "Your friend gets {trial} free days instead of {base}, "
        "and you get +{reward} days of access for each subscription payment they make.\n\n"
        "Your link:\n{link}\n\n"
        "Invited: {invited} · paid: {paid} · days earned: {days}",
    },
    "welcome": {
        RU: "Привет! Я Белок: считаю калории по фото, слежу за тренировками и весом.\n\n"
        "Чтобы рассчитать твою норму, ответь на пять вопросов. Твой пол?",
        EN: "Hi! I'm Belok: I count calories from photos and track your workouts and weight.\n\n"
        "Answer five quick questions so I can calculate your daily target. What's your sex?",
    },
    "male": {RU: "Мужской", EN: "Male"},
    "female": {RU: "Женский", EN: "Female"},
    "ask_age": {RU: "Сколько тебе лет?", EN: "How old are you?"},
    "bad_age": {RU: "Введи возраст числом, например 25", EN: "Enter your age as a number, e.g. 25"},
    "ask_height": {RU: "Рост в сантиметрах?", EN: "Your height in centimeters?"},
    "bad_height": {
        RU: "Введи рост в сантиметрах, например 178",
        EN: "Enter your height in centimeters, e.g. 178",
    },
    "ask_weight": {RU: "Текущий вес в килограммах?", EN: "Your current weight in kilograms?"},
    "bad_weight": {
        RU: "Введи вес в килограммах, например 74.5",
        EN: "Enter your weight in kilograms, e.g. 74.5",
    },
    "ask_goal": {RU: "Какая цель?", EN: "What's your goal?"},
    "goal_lose": {RU: "Похудеть", EN: "Lose weight"},
    "goal_maintain": {RU: "Держать вес", EN: "Maintain weight"},
    "goal_gain": {RU: "Набрать массу", EN: "Gain muscle"},
    "onboarding_done": {
        RU: "Готово! Твоя базовая норма в день без учёта активности:\n<b>{target}</b>\n\n"
        "Шаги и тренировки будут добавлять к ней калории.",
        EN: "Done! Your base daily target before activity:\n<b>{target}</b>\n\n"
        "Steps and workouts will add calories on top of it.",
    },
    "portion_dec": {RU: "Порция −25%", EN: "Portion −25%"},
    "portion_inc": {RU: "Порция +25%", EN: "Portion +25%"},
    "delete": {RU: "Удалить", EN: "Delete"},
    "deleted": {RU: "Удалено", EN: "Deleted"},
    "entry_not_found": {RU: "Запись не найдена", EN: "Entry not found"},
    "looking_photo": {RU: "Смотрю на фото…", EN: "Looking at the photo…"},
    "counting": {RU: "Считаю…", EN: "Counting…"},
    "text_too_long": {
        RU: "Слишком длинное описание, опиши блюдо короче",
        EN: "That description is too long, please keep it shorter",
    },
    "daily_limit": {
        RU: "На сегодня лимит распознаваний исчерпан, приходи завтра",
        EN: "You've hit today's analysis limit, come back tomorrow",
    },
    "analysis_failed": {
        RU: "Не получилось посчитать, попробуй ещё раз чуть позже",
        EN: "Couldn't analyze that, please try again a bit later",
    },
    "no_food": {
        RU: "Не вижу здесь еды. Попробуй другое фото или опиши текстом",
        EN: "I don't see any food here. Try another photo or describe it",
    },
    "macros": {
        RU: "{kcal} ккал · Б {p} · Ж {f} · У {c}",
        EN: "{kcal} kcal · P {p} · F {f} · C {c}",
    },
    "meal_item": {RU: "• {name}, {grams} г: {kcal} ккал", EN: "• {name}, {grams} g: {kcal} kcal"},
    "total": {RU: "<b>Итого:</b> {macros}", EN: "<b>Total:</b> {macros}"},
    "portion": {RU: "<i>Порция ×{scale:.2f}</i>", EN: "<i>Portion ×{scale:.2f}</i>"},
    "today": {RU: "<b>Сегодня</b>", EN: "<b>Today</b>"},
    "eaten": {RU: "Съедено: {macros}", EN: "Eaten: {macros}"},
    "target": {RU: "Норма: {macros}", EN: "Target: {macros}"},
    "left": {RU: "Осталось: {kcal:.0f} ккал", EN: "Left: {kcal:.0f} kcal"},
    "over": {RU: "Перебор: {kcal:.0f} ккал", EN: "Over: {kcal:.0f} kcal"},
    "protein_progress": {
        RU: "Белок: {eaten:.0f} из {target:.0f} г",
        EN: "Protein: {eaten:.0f} of {target:.0f} g",
    },
    "day_counts": {
        RU: "Приёмов пищи: {meals} · Шаги: {steps} · Подходов: {sets}",
        EN: "Meals: {meals} · Steps: {steps} · Sets: {sets}",
    },
    "weight_line": {RU: "Вес: {kg:.1f} кг", EN: "Weight: {kg:.1f} kg"},
    "weight_entry": {RU: "{day}: {kg:.1f} кг", EN: "{day}: {kg:.1f} kg"},
    "no_weights": {
        RU: "Пока нет записей. Пример: /weight 82.5",
        EN: "No entries yet. Example: /weight 82.5",
    },
    "weight_change": {RU: "Изменение: {delta:+.1f} кг", EN: "Change: {delta:+.1f} kg"},
    "weight_usage": {RU: "Пример: /weight 82.5", EN: "Example: /weight 82.5"},
    "weight_saved": {RU: "Записал вес: {kg:.1f} кг", EN: "Weight logged: {kg:.1f} kg"},
    "steps_usage": {RU: "Пример: /steps 8500", EN: "Example: /steps 8500"},
    "steps_saved": {
        RU: "Записал {steps} шагов, это примерно {kcal:.0f} ккал. "
        "Норма учитывает среднюю активность за 7 дней.",
        EN: "Logged {steps} steps, that's about {kcal:.0f} kcal. "
        "Your target uses average activity over the last 7 days.",
    },
    "gym_usage": {
        RU: "Формат: /gym упражнение вес x повторы\n"
        "Например: /gym жим лежа 80x8 80x8 75x10\n"
        "Одинаковые подходы: /gym присед 100x5x3",
        EN: "Format: /gym exercise weight x reps\n"
        "Example: /gym bench press 80x8 80x8 75x10\n"
        "Identical sets: /gym squat 100x5x3",
    },
    "gym_saved": {
        RU: "Записал: <b>{name}</b>, подходов: {sets}\nРасчётный максимум на 1 раз: ~{best:.1f} кг",
        EN: "Logged: <b>{name}</b>, sets: {sets}\nEstimated 1RM: ~{best:.1f} kg",
    },
    "no_exercises": {RU: "Пока нет упражнений.", EN: "No exercises yet."},
    "your_exercises": {RU: "Твои упражнения:", EN: "Your exercises:"},
    "progress_example": {RU: "Пример: /progress {name}", EN: "Example: /progress {name}"},
    "no_history": {
        RU: "Нет записей по «{name}». Посмотри список: /progress",
        EN: 'No entries for "{name}". See the list: /progress',
    },
    "recent_workouts": {
        RU: "<b>{name}</b>, последние тренировки:",
        EN: "<b>{name}</b>, recent workouts:",
    },
    "workout_line": {
        RU: "{day}: {weight:g}×{reps} (~{e1rm:.1f} кг), подходов {sets}",
        EN: "{day}: {weight:g}×{reps} (~{e1rm:.1f} kg), sets: {sets}",
    },
    "e1rm_change": {
        RU: "Расчётный максимум: {delta:+.1f} кг",
        EN: "Estimated 1RM change: {delta:+.1f} kg",
    },
    "open_app": {RU: "Открыть", EN: "Open"},
    "subscribe": {
        RU: "<b>Подписка «Белок»</b>\n\n"
        "Полный доступ: КБЖУ по фото, трекинг тренировок и аналитика. "
        "Оплата через СБП или звёздами Telegram.\n\n{access}",
        EN: "<b>Belok subscription</b>\n\n"
        "Full access: macros from photos, workout tracking and analytics. "
        "Pay via SBP or Telegram Stars.\n\n{access}",
    },
    "access_until": {RU: "Доступ сейчас до {date}.", EN: "Current access until {date}."},
    "access_none": {RU: "Сейчас доступа нет.", EN: "You don't have access right now."},
    "payments_unavailable": {
        RU: "Оплата пока не подключена, напиши автору.",
        EN: "Payments aren't set up yet, please message the author.",
    },
    "payment_ok": {
        RU: "✅ Оплата получена, спасибо! Доступ продлён до {date}.",
        EN: "✅ Payment received, thank you! Access extended until {date}.",
    },
    "payment_refunded": {
        RU: "Возврат оформлен, доступ сокращён на {days} дн.",
        EN: "Refund processed, access shortened by {days} days.",
    },
    "months": {RU: "{n} мес.", EN: "{n} mo."},
    "year": {RU: "1 год", EN: "1 year"},
    "days": {RU: "{n} дн.", EN: "{n} days"},
}


COMMANDS: dict[str, dict[Language, str]] = {
    "today": {RU: "Итоги дня", EN: "Today's totals"},
    "weight": {RU: "Записать вес", EN: "Log weight"},
    "steps": {RU: "Записать шаги", EN: "Log steps"},
    "gym": {RU: "Записать подходы", EN: "Log sets"},
    "progress": {RU: "Прогресс по упражнению", EN: "Exercise progress"},
    "profile": {RU: "Изменить анкету", EN: "Update profile"},
    "subscribe": {RU: "Подписка", EN: "Subscription"},
    "invite": {RU: "Пригласить друга", EN: "Invite a friend"},
    "promo": {RU: "Активировать промокод", EN: "Redeem a promo code"},
    "language": {RU: "Сменить язык", EN: "Change language"},
    "help": {RU: "Помощь", EN: "Help"},
}


def t(lang: Language, key: str, **kwargs: object) -> str:
    return STRINGS[key][lang].format(**kwargs)


def short_date(lang: Language, day: date) -> str:
    return f"{day:%d.%m}" if lang == RU else f"{day:%b %d}"


CURRENCY_SIGNS = {"RUB": "₽", "EUR": "€", "USD": "$"}


def long_date(lang: Language, moment: datetime) -> str:
    return f"{moment:%d.%m.%Y}" if lang == RU else f"{moment:%b %d, %Y}"


def plan_title(lang: Language, days: int) -> str:
    if days == 365:
        return t(lang, "year")
    if days % 30 == 0:
        return t(lang, "months", n=days // 30)
    return t(lang, "days", n=days)


def plan_button(lang: Language, days: int, amount: int | None, currency: str | None) -> str:
    title = plan_title(lang, days)
    if amount is None or not currency:
        return title
    return f"{title} · {amount / 100:g} {CURRENCY_SIGNS.get(currency, currency)}"


def payment_text(lang: Language, user: User, payment: Payment, refunded: bool) -> str:
    if refunded:
        return t(lang, "payment_refunded", days=payment.days)
    return t(lang, "payment_ok", date=long_date(lang, access_until(user)))


def promo_ok(lang: Language, days: int) -> str:
    return t(lang, "promo_ok", days=days, unit="day" if days == 1 else "days")


def invite(
    lang: Language, link: str, settings: Settings, invited: int, paid: int, days: int
) -> str:
    return t(
        lang,
        "invite",
        trial=settings.referral_trial_days,
        base=settings.trial_days,
        reward=settings.referral_reward_days,
        link=link,
        invited=invited,
        paid=paid,
        days=days,
    )


def macros_line(lang: Language, m: Macros) -> str:
    return t(
        lang,
        "macros",
        kcal=f"{m.kcal:.0f}",
        p=f"{m.protein:.0f}",
        f=f"{m.fat:.0f}",
        c=f"{m.carbs:.0f}",
    )


def meal_card(lang: Language, meal: Meal) -> str:
    lines = [f"<b>{escape(meal.title)}</b>"]
    for item in meal.items:
        lines.append(
            t(
                lang,
                "meal_item",
                name=escape(item.name),
                grams=f"{item.grams * meal.scale:.0f}",
                kcal=f"{item.kcal * meal.scale:.0f}",
            )
        )
    lines.append("")
    lines.append(t(lang, "total", macros=macros_line(lang, meal.totals())))
    if meal.scale != 1:
        lines.append(t(lang, "portion", scale=meal.scale))
    return "\n".join(lines)


def day_card(lang: Language, s: DaySummary) -> str:
    lines = [t(lang, "today"), t(lang, "eaten", macros=macros_line(lang, s.eaten))]
    if s.target is not None:
        left = s.target.kcal - s.eaten.kcal
        lines.append(t(lang, "target", macros=macros_line(lang, s.target)))
        lines.append(t(lang, "left", kcal=left) if left >= 0 else t(lang, "over", kcal=-left))
        lines.append(t(lang, "protein_progress", eaten=s.eaten.protein, target=s.target.protein))
    lines.append("")
    lines.append(t(lang, "day_counts", meals=s.meals, steps=s.steps, sets=s.sets))
    if s.weight_kg is not None:
        lines.append(t(lang, "weight_line", kg=s.weight_kg))
    return "\n".join(lines)
