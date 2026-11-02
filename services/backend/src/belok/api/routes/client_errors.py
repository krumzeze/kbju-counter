from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from belok.api.deps import BotDep, SessionDep, token_user_id
from belok.services import errors

router = APIRouter(tags=["errors"])


class ClientErrorIn(BaseModel):
    message: str = Field(min_length=1, max_length=errors.MAX_MESSAGE)
    stack: str | None = Field(default=None, max_length=errors.MAX_DETAIL)
    path: str | None = Field(default=None, max_length=256)


@router.post("/client-errors", status_code=status.HTTP_204_NO_CONTENT)
async def post_client_error(
    body: ClientErrorIn,
    session: SessionDep,
    bot: BotDep,
    user_id: Annotated[int | None, Depends(token_user_id)],
) -> Response:
    await errors.record(
        session,
        bot,
        source="web",
        fingerprint=errors.web_fingerprint(body.message),
        message=body.message,
        detail=body.stack,
        path=body.path,
        user_id=user_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
