from datetime import datetime

from belok.db.models import Payment, User
from belok.i18n import Language
from belok.services.access import access_until

RU, EN = Language.RU, Language.EN

STRINGS: dict[str, dict[Language, str]] = {
    "welcome": {
        RU: "Привет! Я Белок: считаю калории по фото, веду тренировки и вес.\n\n"
        "Всё работает в приложении, открой его кнопкой ниже.",
        EN: "Hi! I'm Belok: I count calories from photos and track your workouts and weight.\n\n"
        "Everything lives in the app, open it with the button below.",
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
