from enum import StrEnum


class Language(StrEnum):
    RU = "ru"
    EN = "en"


RUSSIAN_SPEAKING = {"ru", "uk", "be", "kk", "uz", "ky"}


def guess_language(code: str | None) -> Language:
    """Fallback until the user picks a language, from Telegram's language_code."""
    if code and code.split("-")[0].lower() in RUSSIAN_SPEAKING:
        return Language.RU
    return Language.EN
