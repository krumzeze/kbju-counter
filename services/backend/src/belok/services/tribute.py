import base64
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, replace

import aiohttp

from belok.config import Settings

log = logging.getLogger(__name__)

API_URL = "https://tribute.tg/api/v1"
WEB_LINK = "https://web.tribute.tg/p/{code}"
CACHE_SECONDS = 600


@dataclass(frozen=True, slots=True)
class Plan:
    code: str
    days: int
    link: str
    web_link: str
    product_id: int | None = None
    amount: int | None = None
    currency: str | None = None


def parse_plans(spec: str) -> list[Plan]:
    plans = []
    for item in spec.split(","):
        code, _, days = item.strip().partition(":")
        if code and days.isdigit():
            web = WEB_LINK.format(code=code)
            plans.append(Plan(code=code, days=int(days), link=web, web_link=web))
    return plans


def signature_valid(body: bytes, signature: str | None, api_key: str) -> bool:
    if not signature:
        return False
    digest = hmac.new(api_key.encode(), body, hashlib.sha256)
    expected = (digest.hexdigest(), base64.b64encode(digest.digest()).decode())
    return any(hmac.compare_digest(signature.strip(), e) for e in expected)


def _code(product: dict) -> str | None:
    link = product.get("webLink") or product.get("web_link")
    return link.rstrip("/").rsplit("/", 1)[-1] if isinstance(link, str) else None


def _items(data: object) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "items", "products", "rows"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


class TributeCatalog:
    """Configured plans enriched with ids and prices from the Tribute products API."""

    @classmethod
    def from_settings(cls, settings: Settings) -> "TributeCatalog":
        key = settings.tribute_api_key
        return cls(key.get_secret_value() if key else None, settings.tribute_plans)

    def __init__(self, api_key: str | None, spec: str) -> None:
        self._api_key = api_key
        self._base = parse_plans(spec)
        self._plans = self._base
        self._loaded_at = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self._api_key and self._base)

    @property
    def api_key(self) -> str | None:
        return self._api_key

    async def plans(self, force: bool = False) -> list[Plan]:
        if self._api_key and (force or time.monotonic() - self._loaded_at > CACHE_SECONDS):
            try:
                self._plans = self._merge(await self._fetch())
                self._loaded_at = time.monotonic()
            except (aiohttp.ClientError, TimeoutError, ValueError):
                log.warning("failed to load Tribute products", exc_info=True)
        return self._plans

    async def plan_for_product(self, product_id: int) -> Plan | None:
        for force in (False, True):
            for plan in await self.plans(force):
                if plan.product_id == product_id:
                    return plan
        return None

    async def _fetch(self) -> list[dict]:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.get(
                f"{API_URL}/products",
                params={"type": "digital", "size": 100},
                headers={"Api-Key": self._api_key},
            ) as response:
                response.raise_for_status()
                return _items(await response.json())

    def _merge(self, products: list[dict]) -> list[Plan]:
        by_code = {_code(p): p for p in products}
        merged = []
        for plan in self._base:
            product = by_code.get(plan.code)
            if product is None:
                merged.append(plan)
                continue
            merged.append(
                replace(
                    plan,
                    product_id=product.get("id"),
                    amount=product.get("amount"),
                    currency=str(product.get("currency") or "").upper() or None,
                    link=product.get("link") or plan.link,
                )
            )
        return merged
