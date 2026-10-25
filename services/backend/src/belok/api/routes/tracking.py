from typing import Annotated

from fastapi import APIRouter, Query, status

from belok.api.deps import ActiveUser, SessionDep
from belok.api.schemas import StepsIn, WeightIn, WeightOut
from belok.services.repo import recent_weights, upsert_steps, upsert_weight
from belok.timeutil import local_today

router = APIRouter(tags=["tracking"])


@router.get("/weights")
async def list_weights(
    user: ActiveUser, session: SessionDep, limit: Annotated[int, Query(ge=1, le=365)] = 90
) -> list[WeightOut]:
    weights = await recent_weights(session, user.id, limit)
    return [WeightOut.model_validate(w) for w in reversed(weights)]


@router.put("/weights/today", status_code=status.HTTP_204_NO_CONTENT)
async def put_weight(body: WeightIn, user: ActiveUser, session: SessionDep) -> None:
    await upsert_weight(session, user.id, local_today(user.timezone), body.weight_kg)
    await session.commit()


@router.put("/steps/today", status_code=status.HTTP_204_NO_CONTENT)
async def put_steps(body: StepsIn, user: ActiveUser, session: SessionDep) -> None:
    await upsert_steps(session, user.id, local_today(user.timezone), body.steps)
    await session.commit()
