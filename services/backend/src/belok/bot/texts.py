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
        "Основные функции бесплатны, Premium можно попробовать {trial}.",
        EN: "Belok counts your calories and tracks your workouts.\n\n"
        "Log what you eat and keep an eye on your macros: your daily target is built around "
        "your goal, whether that's losing weight, gaining or staying in shape. Log your "
        "workouts and watch your progress and weight change over time.\n\n"
        "Core features are free, and you can try Premium for {trial}.",
    },
    "welcome": {
        RU: "Привет! Я Белок: считаю калории по фото, веду тренировки и вес.\n\n"
        "Всё работает в приложении, открой его кнопкой ниже. А прямо здесь можно:\n"
        "🎙 рассказать голосовым, что было на тарелке, а граммы поправить в ответе;\n"
        "📊 /day: закрепить карточку дня, она обновляется сама после каждой записи.\n\n"
        '<a href="{privacy_url}">Политика конфиденциальности</a>',
        EN: "Hi! I'm Belok: I count calories from photos and track your workouts and weight.\n\n"
        "Everything lives in the app, open it with the button below. Right here you can:\n"
        "🎙 tell me in a voice message what you ate and adjust the grams in my reply;\n"
        "📊 /day: pin a day card that updates itself after every entry.\n\n"
        '<a href="{privacy_url}">Privacy policy</a>',
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
    "stars_title": {RU: "Белок Premium", EN: "Belok Premium"},
    "stars_description": {
        RU: "Распознавание еды по фото и описанию, адаптивная норма и вся история прогресса "
        "на {period}.",
        EN: "Food recognition from photos and text, adaptive target and full progress history "
        "for {period}.",
    },
    "stars_label": {RU: "Premium на {period}", EN: "Premium for {period}"},
    "stars_unavailable": {
        RU: "Оплата сейчас недоступна, попробуй позже.",
        EN: "Payments are unavailable right now, please try again later.",
    },
    "support_ask": {
        RU: "Напиши свой вопрос одним сообщением, и я передам его команде. Ответ придёт сюда.",
        EN: "Write your question in one message and I'll pass it to the team. "
        "The reply will come here.",
    },
    "paysupport_ask": {
        RU: "Проблема с оплатой? Опиши её одним сообщением: что покупал и что пошло не так. "
        "Ответ придёт сюда.",
        EN: "Having trouble with a payment? Describe it in one message: what you bought "
        "and what went wrong. The reply will come here.",
    },
    "paysupport_payments": {RU: "Твои последние платежи:", EN: "Your recent payments:"},
    "support_sent": {
        RU: "Отправил, ответим здесь как можно скорее.",
        EN: "Sent. We'll reply here as soon as we can.",
    },
    "support_too_many": {
        RU: "Слишком много сообщений за сутки, подожди немного.",
        EN: "Too many messages today, please wait a little.",
    },
    "support_reply": {
        RU: "💬 <b>Ответ поддержки</b>\n\n{text}",
        EN: "💬 <b>Support reply</b>\n\n{text}",
    },
    "free_limit": {
        RU: "Бесплатные распознавания на сегодня закончились. С Premium их больше, "
        "а вручную добавлять еду можно без ограничений.",
        EN: "You've used today's free recognitions. Premium gives you more, "
        "and manual logging is always unlimited.",
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
    "voice_widget_caption": {
        RU: "🎙 <i>«{heard}»</i>\n<b>{title}</b>: {kcal:.0f} ккал. "
        "Граммы можно поправить прямо здесь.",
        EN: "🎙 <i>“{heard}”</i>\n<b>{title}</b>: {kcal:.0f} kcal. "
        "You can adjust the grams right here.",
    },
    "day_card_caption": {
        RU: "📊 Твой день: калории, БЖУ, вода и шаги. "
        "Карточка обновляется сама после каждой записи.",
        EN: "📊 Your day: calories, macros, water and steps. "
        "The card updates itself after every entry.",
    },
    "recipe_approved": {
        RU: "✅ Рецепт «{title}» опубликован в каталоге. Спасибо!",
        EN: "✅ Your recipe “{title}” is now in the catalog. Thank you!",
    },
    "recipe_rejected": {
        RU: "↩️ Рецепт «{title}» пока не опубликовали: {reason}\n\nПоправь его и отправь снова.",
        EN: "↩️ Your recipe “{title}” wasn't published yet: {reason}\n\nFix it and submit again.",
    },
    "cook_caption": {
        RU: "🍳 <b>{title}</b>\nОтмечай шаги по ходу готовки, а в конце добавь блюдо в дневник.",
        EN: "🍳 <b>{title}</b>\nTick off the steps as you cook, then log the dish.",
    },
    "open_recipe": {RU: "Открыть рецепт", EN: "Open the recipe"},
    "day_card_button": {RU: "📊 Карточка дня", EN: "📊 Day card"},
    "cmd_day": {RU: "Карточка дня в чате", EN: "Day card in the chat"},
    "cmd_support": {RU: "Написать в поддержку", EN: "Contact support"},
    "cmd_paysupport": {RU: "Вопрос по оплате", EN: "Payment question"},
    "cmd_privacy": {RU: "Политика конфиденциальности", EN: "Privacy policy"},
    "day_card_unavailable": {
        RU: "Карточка дня сейчас недоступна, загляни в приложение.",
        EN: "The day card is unavailable right now, check the app.",
    },
    "log_meal": {RU: "Записать еду", EN: "Log food"},
    "log_weight": {RU: "Записать вес", EN: "Log weight"},
    "remind_stop": {RU: "Не напоминать", EN: "Stop reminding"},
    "remind_stopped": {
        RU: "Больше не напоминаю. Включить снова можно в профиле.",
        EN: "Reminders are off. You can turn them back on in your profile.",
    },
    "privacy": {
        RU: "Политика конфиденциальности: {url}",
        EN: "Privacy policy (in Russian): {url}",
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
