import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO

import aiohttp
import zxingcpp
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import Product
from belok.i18n import Language
from belok.timeutil import utcnow

log = logging.getLogger(__name__)

CODE_RE = re.compile(r"^\d{8,14}$")
CACHE_TTL = timedelta(days=30)
MAX_DECODE_SIDE = 2000
MAX_KCAL_PER_100G = 900
MAX_MACRO_PER_100G = 100
KJ_PER_KCAL = 4.184


@dataclass(frozen=True, slots=True)
class ProductInfo:
    name: str
    kcal: float
    protein: float
    fat: float
    carbs: float
    serving_g: float | None


def _decode(image: bytes) -> str | None:
    try:
        with Image.open(BytesIO(image)) as raw:
            img = ImageOps.exif_transpose(raw).convert("L")
    except (UnidentifiedImageError, OSError):
        return None
    img.thumbnail((MAX_DECODE_SIDE, MAX_DECODE_SIDE))
    for barcode in zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.EANUPC):
        if CODE_RE.match(barcode.text):
            return barcode.text
    return None


async def decode_barcode(image: bytes) -> str | None:
    return await asyncio.to_thread(_decode, image)


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def parse_off_product(data: dict, language: Language) -> ProductInfo | None:
    product = data.get("product") or {}
    nutriments = product.get("nutriments") or {}
    kcal = _number(nutriments.get("energy-kcal_100g"))
    if kcal is None and (kj := _number(nutriments.get("energy_100g"))) is not None:
        kcal = kj / KJ_PER_KCAL
    name = (
        product.get(f"product_name_{language.value}")
        or product.get("product_name")
        or product.get("generic_name")
        or ""
    ).strip()
    if kcal is None or not name:
        return None
    if brand := (product.get("brands") or "").split(",")[0].strip():
        name = name if brand.lower() in name.lower() else f"{name}, {brand}"

    def macro(key: str) -> float:
        return min(MAX_MACRO_PER_100G, _number(nutriments.get(f"{key}_100g")) or 0.0)

    serving = _number(product.get("serving_quantity"))
    return ProductInfo(
        name=name[:255],
        kcal=min(MAX_KCAL_PER_100G, kcal),
        protein=macro("proteins"),
        fat=macro("fat"),
        carbs=macro("carbohydrates"),
        serving_g=serving if serving and serving <= 3000 else None,
    )


class FoodDatabase:
    """Open Food Facts product lookup."""

    URL = "https://world.openfoodfacts.org/api/v2/product/{code}"
    FIELDS = (
        "product_name,product_name_ru,product_name_en,generic_name,brands,"
        "nutriments,serving_quantity"
    )

    async def lookup(self, code: str, language: Language) -> ProductInfo | None:
        try:
            async with (
                self._http() as http,
                http.get(self.URL.format(code=code), params={"fields": self.FIELDS}) as response,
            ):
                if response.status == 404:
                    return None
                response.raise_for_status()
                data = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError):
            log.warning("open food facts lookup failed for %s", code, exc_info=True)
            return None
        if data.get("status") != 1:
            return None
        return parse_off_product(data, language)

    def _http(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={"User-Agent": "Belok/1.0 (calorie tracker)"},
        )


def _info(product: Product) -> ProductInfo:
    return ProductInfo(
        product.name, product.kcal, product.protein, product.fat, product.carbs, product.serving_g
    )


async def find_product(
    session: AsyncSession, food_db: FoodDatabase, user_id: int, code: str, language: Language
) -> ProductInfo | None:
    """The user's own label wins over the shared cache, which is refreshed after CACHE_TTL."""
    own = await session.scalar(
        select(Product).where(Product.code == code, Product.user_id == user_id)
    )
    if own is not None:
        return _info(own)
    shared = await session.scalar(
        select(Product).where(Product.code == code, Product.user_id.is_(None))
    )
    if shared is not None and utcnow() - shared.updated_at < CACHE_TTL:
        return _info(shared)

    found = await food_db.lookup(code, language)
    if found is None:
        return _info(shared) if shared is not None else None
    await _upsert(session, code, None, found)
    return found


async def remember_product(
    session: AsyncSession, user_id: int, code: str, info: ProductInfo
) -> None:
    await _upsert(session, code, user_id, info)


async def _upsert(session: AsyncSession, code: str, user_id: int | None, info: ProductInfo) -> None:
    values = {
        "name": info.name,
        "kcal": info.kcal,
        "protein": info.protein,
        "fat": info.fat,
        "carbs": info.carbs,
        "serving_g": info.serving_g,
        "updated_at": utcnow(),
    }
    stmt = insert(Product).values(code=code, user_id=user_id, **values)
    if user_id is None:
        stmt = stmt.on_conflict_do_update(
            index_elements=["code"], index_where=Product.user_id.is_(None), set_=values
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "user_id"],
            index_where=Product.user_id.is_not(None),
            set_=values,
        )
    await session.execute(stmt)
