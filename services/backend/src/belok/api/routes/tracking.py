from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from belok.api.deps import ActiveUser, SessionDep, SettingsDep
from belok.api.schemas import (
    StatsDayOut,
    StatsOut,
    StepsIn,
    WaterIn,
    WaterOut,
    WeightIn,
    WeightOut,
    macros_out,
)
from belok.services.access import history_start
from belok.services.repo import (
    add_water,
    daily_stats,
    day_summary,
    recent_weights,
    upsert_steps,
    upsert_weight,
)
from belok.timeutil import local_today

router = APIRouter(tags=["tracking"])

EDITABLE_DAYS = 7


def _editable_day(user: ActiveUser, day: date | None) -> date:
    today = local_today(user.timezone)
    if day is None:
        return today
    if not today - timedelta(days=EDITABLE_DAYS - 1) <= day <= today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "day_not_editable")
    return day


@router.get("/weights")
async def list_weights(
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=365)] = 90,
) -> list[WeightOut]:
    weights = await recent_weights(session, user.id, limit)
    start = history_start(user, local_today(user.timezone), settings.free_history_days)
    return [WeightOut.model_validate(w) for w in reversed(weights) if not start or w.day >= start]


@router.get("/stats")
async def get_stats(
    user: ActiveUser,
    session: SessionDep,
    settings: SettingsDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> StatsOut:
    today = local_today(user.timezone)
    start = today - timedelta(days=days - 1)
    allowed = history_start(user, today, settings.free_history_days)
    limited = allowed is not None and allowed > start
    if limited:
        start = allowed
    summary = await day_summary(session, user, today)
    days_out = await daily_stats(session, user.id, start, today)
    return StatsOut(
        days=[StatsDayOut.model_validate(d) for d in days_out],
        target=macros_out(summary.target.macros) if summary.target else None,
        limited=limited,
    )


@router.put("/weights/today", status_code=status.HTTP_204_NO_CONTENT)
async def put_weight(body: WeightIn, user: ActiveUser, session: SessionDep) -> None:
    await upsert_weight(session, user.id, local_today(user.timezone), body.weight_kg)
    await session.commit()


@router.put("/steps/today", status_code=status.HTTP_204_NO_CONTENT)
async def put_steps(
    body: StepsIn,
    user: ActiveUser,
    session: SessionDep,
    day: Annotated[date | None, Query()] = None,
) -> None:
    await upsert_steps(session, user.id, _editable_day(user, day), body.steps)
    await session.commit()


@router.post("/water/today")
async def post_water(
    body: WaterIn,
    user: ActiveUser,
    session: SessionDep,
    day: Annotated[date | None, Query()] = None,
) -> WaterOut:
    total = await add_water(session, user.id, _editable_day(user, day), body.delta_ml)
    await session.commit()
    return WaterOut(water_ml=total)
