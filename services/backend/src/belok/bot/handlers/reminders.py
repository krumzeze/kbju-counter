from aiogram import F, Router
from aiogram.types import CallbackQuery

from belok.bot.texts import t
from belok.db.models import User
from belok.i18n import Language

router = Router(name="reminders")

PREFS = {"meals": "remind_meals", "weight": "remind_weight"}


@router.callback_query(F.data.startswith("remind_off:"))
async def stop_reminders(callback: CallbackQuery, user: User, lang: Language) -> None:
    field = PREFS.get(callback.data.removeprefix("remind_off:"))
    if field is not None:
        setattr(user, field, False)
    await callback.answer(t(lang, "remind_stopped"), show_alert=True)
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)
