from html import escape

from belok.db.models import Meal
from belok.domain.nutrition import Macros
from belok.services.repo import DaySummary

HELP = """<b>Что я умею</b>

📸 Пришли фото еды, и я посчитаю КБЖУ. Можно добавить подпись, например «рис 150 г».
✍️ Или опиши текстом: <i>2 яйца, тост с маслом, кофе с молоком</i>

/today: итоги дня и норма
/weight 82.5: записать вес
/steps 8500: записать шаги
/gym жим лежа 80x8 80x8 75x10: записать подходы (можно 100x5x3)
/progress жим лежа: прогресс по упражнению
/profile: изменить анкету"""

PROFILE_REQUIRED = "Сначала заполни короткую анкету: /start"
ACCESS_EXPIRED = (
    "Бесплатный период закончился. Скоро здесь появится подписка, "
    "а пока напиши автору, чтобы продлить доступ."
)


def macros_line(m: Macros) -> str:
    return f"{m.kcal:.0f} ккал · Б {m.protein:.0f} · Ж {m.fat:.0f} · У {m.carbs:.0f}"


def meal_card(meal: Meal) -> str:
    lines = [f"<b>{escape(meal.title)}</b>"]
    for item in meal.items:
        grams = item.grams * meal.scale
        lines.append(f"• {escape(item.name)}, {grams:.0f} г: {item.kcal * meal.scale:.0f} ккал")
    lines.append("")
    lines.append(f"<b>Итого:</b> {macros_line(meal.totals())}")
    if meal.scale != 1:
        lines.append(f"<i>Порция ×{meal.scale:.2f}</i>")
    return "\n".join(lines)


def day_card(s: DaySummary) -> str:
    lines = ["<b>Сегодня</b>", f"Съедено: {macros_line(s.eaten)}"]
    if s.target is not None:
        left = s.target.kcal - s.eaten.kcal
        lines.append(f"Норма: {macros_line(s.target)}")
        lines.append(f"Осталось: {left:.0f} ккал" if left >= 0 else f"Перебор: {-left:.0f} ккал")
        lines.append(f"Белок: {s.eaten.protein:.0f} из {s.target.protein:.0f} г")
    lines.append("")
    lines.append(f"Приёмов пищи: {s.meals} · Шаги: {s.steps} · Подходов: {s.sets}")
    if s.weight_kg is not None:
        lines.append(f"Вес: {s.weight_kg:.1f} кг")
    return "\n".join(lines)
