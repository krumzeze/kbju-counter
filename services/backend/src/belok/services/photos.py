import asyncio
import hashlib
import hmac
import io
import logging
import re
import time
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from belok import images
from belok.config import Settings

log = logging.getLogger(__name__)

MAX_SIDE = 800
QUALITY = 75
URL_WINDOW = 24 * 3600
KEY_RE = re.compile(r"^meals/\d+/[0-9a-f]{32}\.webp$")

StorageError = (BotoCoreError, ClientError)


def make_thumbnail(image: bytes) -> bytes:
    """Downscale to WebP, honoring EXIF rotation and dropping all metadata (GPS included)."""
    img = images.decode(image, MAX_SIDE)
    out = io.BytesIO()
    img.save(out, "WEBP", quality=QUALITY, method=4)
    return out.getvalue()


def meal_key(user_id: int) -> str:
    return f"meals/{user_id}/{uuid.uuid4().hex}.webp"


def eval_key(user_id: int, meal_id: int) -> str:
    return f"eval/{user_id}/{meal_id}.webp"


class PhotoStore:
    def __init__(self, client, bucket: str, secret: bytes) -> None:
        self._client = client
        self._bucket = bucket
        self._secret = secret

    @classmethod
    def from_settings(cls, settings: Settings) -> "PhotoStore | None":
        if not settings.photos_enabled:
            return None
        client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.r2_secret_access_key.get_secret_value(),
            region_name="auto",
            config=Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 2}),
        )
        return cls(client, settings.r2_bucket, settings.api_secret.get_secret_value().encode())

    async def put(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType="image/webp",
        )

    async def get(self, key: str) -> bytes | None:
        try:
            obj = await asyncio.to_thread(self._client.get_object, Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                return None
            raise
        return await asyncio.to_thread(obj["Body"].read)

    async def copy(self, src: str, dst: str) -> None:
        await asyncio.to_thread(
            self._client.copy_object,
            Bucket=self._bucket,
            Key=dst,
            CopySource={"Bucket": self._bucket, "Key": src},
        )

    async def delete(self, *keys: str) -> None:
        if keys:
            await asyncio.to_thread(
                self._client.delete_objects,
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
            )

    async def delete_prefix(self, prefix: str) -> None:
        def run() -> None:
            pages = self._client.get_paginator("list_objects_v2").paginate(
                Bucket=self._bucket, Prefix=prefix
            )
            for page in pages:
                keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
                if keys:
                    self._client.delete_objects(
                        Bucket=self._bucket, Delete={"Objects": keys, "Quiet": True}
                    )

        await asyncio.to_thread(run)

    async def delete_quietly(self, *keys: str) -> None:
        try:
            await self.delete(*keys)
        except StorageError:
            log.warning("failed to delete photos %s", keys, exc_info=True)

    def url(self, key: str, now: float | None = None) -> str:
        """A link that stays the same for a day, so browsers can cache the image."""
        now = time.time() if now is None else now
        exp = (int(now) // URL_WINDOW + 2) * URL_WINDOW
        return f"/api/photos/{key}?exp={exp}&sig={self._sign(key, exp)}"

    def verify(self, key: str, exp: int, sig: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return exp > now and hmac.compare_digest(sig, self._sign(key, exp))

    def _sign(self, key: str, exp: int) -> str:
        msg = f"photo:{key}:{exp}".encode()
        return hmac.new(self._secret, msg, hashlib.sha256).hexdigest()[:32]
