from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import LabeledPrice

from belok.bot.texts import days_count, t
from belok.i18n import Language

CURRENCY = "XTR"
PAYLOAD_PREFIX = "stars:"


@dataclass(frozen=True, slots=True)
class StarsPlan:
    days: int
    stars: int

    @property
    def code(self) -> str:
        return f"stars-{self.days}"

    @property
    def payload(self) -> str:
        return f"{PAYLOAD_PREFIX}{self.days}:{self.stars}"


def parse_plans(spec: str) -> list[StarsPlan]:
    plans = []
    for item in spec.split(","):
        days, _, stars = item.strip().partition(":")
        if days.isdigit() and stars.isdigit() and int(days) > 0 and int(stars) > 0:
            plans.append(StarsPlan(days=int(days), stars=int(stars)))
    return plans


def plan_for_payload(plans: list[StarsPlan], payload: str, amount: int) -> StarsPlan | None:
    """Matches an invoice payload against current plans, so a stale price is rejected."""
    for plan in plans:
        if plan.payload == payload and plan.stars == amount:
            return plan
    return None


async def invoice_link(bot: Bot, plan: StarsPlan, lang: Language) -> str:
    period = days_count(lang, plan.days)
    return await bot.create_invoice_link(
        title=t(lang, "stars_title"),
        description=t(lang, "stars_description", period=period),
        payload=plan.payload,
        currency=CURRENCY,
        prices=[LabeledPrice(label=t(lang, "stars_label", period=period), amount=plan.stars)],
    )
