import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from belok.api.deps import PhotosDep
from belok.services.photos import KEY_RE

router = APIRouter(tags=["photos"])


@router.get("/photos/{key:path}", include_in_schema=False)
async def get_photo(
    key: str,
    photos: PhotosDep,
    exp: Annotated[int, Query()],
    sig: Annotated[str, Query(max_length=64)],
) -> Response:
    if photos is None or not KEY_RE.match(key) or not photos.verify(key, exp, sig):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo_not_found")
    data = await photos.get(key)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "photo_not_found")
    max_age = max(0, exp - int(time.time()))
    return Response(
        data, media_type="image/webp", headers={"Cache-Control": f"private, max-age={max_age}"}
    )
