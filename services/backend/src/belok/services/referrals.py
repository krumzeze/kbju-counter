from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import ReferralReward, User
from belok.services.access import grant_days
from belok.timeutil import utcnow


async def reward_for_payment(
    session: AsyncSession, payer: User, payment_ref: str, days: int
) -> User | None:
    """Credit the payer's referrer once per payment. Returns the rewarded referrer."""
    if payer.referred_by_id is None:
        return None
    referrer = await session.get(User, payer.referred_by_id, with_for_update=True)
    if referrer is None or referrer.is_blocked:
        return None
    inserted = await session.scalar(
        insert(ReferralReward)
        .values(referrer_id=referrer.id, referred_id=payer.id, payment_ref=payment_ref, days=days)
        .on_conflict_do_nothing(index_elements=["payment_ref"])
        .returning(ReferralReward.id)
    )
    if inserted is None:
        return None
    grant_days(referrer, days, utcnow())
    return referrer


async def referral_stats(session: AsyncSession, user_id: int) -> tuple[int, int, int]:
    """Invited users, those who paid at least once, and total days earned."""
    invited = await session.scalar(
        select(func.count()).select_from(User).where(User.referred_by_id == user_id)
    )
    paid, days = (
        await session.execute(
            select(
                func.count(func.distinct(ReferralReward.referred_id)),
                func.coalesce(func.sum(ReferralReward.days), 0),
            ).where(ReferralReward.referrer_id == user_id)
        )
    ).one()
    return invited, paid, days
