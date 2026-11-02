from datetime import datetime

from belok.db.models import Payment, User
from belok.i18n import Language
from belok.services.access import access_until

RU, EN = Language.RU, Language.EN

STRINGS: dict[str, dict[Language, str]] = {
    "bot_name": {RU: "Белок", EN: "Belok"},
    "bot_short_description": {
        RU: "Подсчёт калорий и дневник тренировок в одном приложении.",
        EN: "Calorie counting and workout tracking in one app.",
    },
    "bot_description": {
        RU: "Белок считает калории и ведёт твои тренировки.\n\n"
        "Записывай, что ешь, и следи за КБЖУ: дневная норма рассчитана под твою цель, "
        "похудеть, набрать или держать форму. Отмечай тренировки и смотри, как растут "
        "результаты и меняется вес.\n\n"
        "{trial} бесплатно.",
        EN: "Belok counts your calories and tracks your workouts.\n\n"
        "Log what you eat and keep an eye on your macros: your daily target is built around "
        "your goal, whether that's losing weight, gaining or staying in shape. Log your "
        "workouts and watch your progress and weight change over time.\n\n"
        "{trial} free.",
    },
    "welcome": {
        RU: "Привет! Я Белок: считаю калории по фото, веду тренировки и вес.\n\n"
        "Всё работает в приложении, открой его кнопкой ниже. А ещё можно просто "
        "отправить мне голосовое о том, что ты съел.",
        EN: "Hi! I'm Belok: I count calories from photos and track your workouts and weight.\n\n"
        "Everything lives in the app, open it with the button below. You can also just "
        "send me a voice message about what you ate.",
    },
    "remind_nothing_today": {
        RU: "🍽 Сегодня ещё нет ни одной записи. Что было на завтрак и обед?",
        EN: "🍽 Nothing logged today yet. What did you have for breakfast and lunch?",
    },
    "remind_lunch": {
        RU: "🍲 Не забудь записать обед, пока помнишь порцию.",
        EN: "🍲 Don't forget to log your lunch while you still remember the portion.",
    },
    "remind_dinner": {
        RU: "🌙 Как прошёл ужин? Запиши его, чтобы день был полным.",
        EN: "🌙 How was dinner? Log it so your day is complete.",
    },
    "remind_weight": {
        RU: "⚖️ Пора взвеситься. Лучше утром, после туалета и до еды: так цифры честнее.",
        EN: "⚖️ Time to weigh in. Morning is best, after the bathroom and before breakfast.",
    },
    "voice_need_profile": {
        RU: "Сначала заполни профиль в приложении, чтобы я знал твою норму.",
        EN: "Fill in your profile in the app first so I know your target.",
    },
    "voice_no_access": {
        RU: "Пробный период закончился. Продлить доступ можно в приложении.",
        EN: "Your free trial has ended. You can extend access in the app.",
    },
    "voice_unavailable": {
        RU: "Голосовые сейчас недоступны. Опиши еду текстом в приложении.",
        EN: "Voice messages are unavailable right now. Describe your meal as text in the app.",
    },
    "voice_too_long": {
        RU: "Слишком длинное голосовое. Уложись в {seconds} секунд.",
        EN: "That voice message is too long. Please keep it under {seconds} seconds.",
    },
    "daily_limit": {
        RU: "На сегодня лимит распознаваний исчерпан. Можно добавить еду вручную в приложении.",
        EN: "You've reached today's recognition limit. You can still add food manually in the app.",
    },
    "voice_failed": {
        RU: "Не получилось распознать, попробуй ещё раз.",
        EN: "Couldn't process that, please try again.",
    },
    "voice_empty": {
        RU: "Не расслышал. Попробуй сказать чуть громче или ближе к телефону.",
        EN: "I couldn't hear anything. Try speaking a bit louder or closer to the phone.",
    },
    "voice_no_food": {
        RU: "Я услышал «{text}», но не нашёл там еды. Расскажи, что и сколько ты съел.",
        EN: 'I heard "{text}" but found no food in it. Tell me what and how much you ate.',
    },
    "voice_totals": {
        RU: "Итого: <b>{kcal:.0f} ккал</b> · Б {p:.0f} · Ж {f:.0f} · У {c:.0f}",
        EN: "Total: <b>{kcal:.0f} kcal</b> · P {p:.0f} · F {f:.0f} · C {c:.0f}",
    },
    "voice_day": {
        RU: "За сегодня: {eaten:.0f} из {target:.0f} ккал",
        EN: "Today: {eaten:.0f} of {target:.0f} kcal",
    },
    "voice_edit_hint": {
        RU: "Поправить порцию можно в приложении.",
        EN: "You can adjust the portion in the app.",
    },
    "log_meal": {RU: "Записать еду", EN: "Log food"},
    "log_weight": {RU: "Записать вес", EN: "Log weight"},
    "remind_stop": {RU: "Не напоминать", EN: "Stop reminding"},
    "remind_stopped": {
        RU: "Больше не напоминаю. Включить снова можно в профиле.",
        EN: "Reminders are off. You can turn them back on in your profile.",
    },
    "app_unavailable": {
        RU: "Приложение скоро будет доступно.",
        EN: "The app will be available soon.",
    },
    "blocked": {RU: "Доступ к боту ограничен.", EN: "Your access to this bot has been restricted."},
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
    "open_app": {RU: "Открыть", EN: "Open"},
    "payment_ok": {
        RU: "✅ Оплата получена, спасибо! Доступ продлён до {date}.",
        EN: "✅ Payment received, thank you! Access extended until {date}.",
    },
    "payment_refunded": {
        RU: "Возврат оформлен, доступ сокращён на {days} дн.",
        EN: "Refund processed, access shortened by {days} days.",
    },
}


def t(lang: Language, key: str, **kwargs: object) -> str:
    return STRINGS[key][lang].format(**kwargs)


def long_date(lang: Language, moment: datetime) -> str:
    return f"{moment:%d.%m.%Y}" if lang == RU else f"{moment:%b %d, %Y}"


def payment_text(lang: Language, user: User, payment: Payment, refunded: bool) -> str:
    if refunded:
        return t(lang, "payment_refunded", days=payment.days)
    return t(lang, "payment_ok", date=long_date(lang, access_until(user)))


def promo_ok(lang: Language, days: int) -> str:
    return t(lang, "promo_ok", days=days, unit="day" if days == 1 else "days")


def days_count(lang: Language, days: int) -> str:
    if lang == EN:
        return f"{days} day" if days == 1 else f"{days} days"
    if days % 10 == 1 and days % 100 != 11:
        return f"{days} день"
    if 2 <= days % 10 <= 4 and not 12 <= days % 100 <= 14:
        return f"{days} дня"
    return f"{days} дней"
