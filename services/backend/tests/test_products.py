from io import BytesIO

import pytest
import zxingcpp
from PIL import Image

from belok.i18n import Language
from belok.services.products import _decode, parse_off_product


def barcode_png(code: str) -> bytes:
    view = memoryview(zxingcpp.create_barcode(code, zxingcpp.BarcodeFormat.EAN13).to_image(scale=4))
    bars = Image.frombytes("L", (view.shape[1], view.shape[0]), bytes(view))
    canvas = Image.new("L", (bars.width + 80, bars.height + 80), 255)
    canvas.paste(bars, (40, 40))
    buffer = BytesIO()
    canvas.save(buffer, "PNG")
    return buffer.getvalue()


def test_decodes_ean13_from_photo():
    assert _decode(barcode_png("4600000000008")) == "4600000000008"


def test_photo_without_barcode():
    buffer = BytesIO()
    Image.new("RGB", (200, 200), "white").save(buffer, "JPEG")
    assert _decode(buffer.getvalue()) is None
    assert _decode(b"not an image") is None


def test_parses_open_food_facts_product():
    data = {
        "status": 1,
        "product": {
            "product_name": "Kefir",
            "product_name_ru": "Кефир 2.5%",
            "brands": "Простоквашино, Danone",
            "serving_quantity": "250",
            "nutriments": {
                "energy-kcal_100g": 53,
                "proteins_100g": "2.9",
                "fat_100g": 2.5,
                "carbohydrates_100g": 4,
            },
        },
    }
    info = parse_off_product(data, Language.RU)
    assert info.name == "Кефир 2.5%, Простоквашино"
    assert (info.kcal, info.protein, info.fat, info.carbs) == (53, 2.9, 2.5, 4)
    assert info.serving_g == 250
    assert parse_off_product(data, Language.EN).name == "Kefir, Простоквашино"


def test_kilojoules_are_converted_and_missing_energy_rejected():
    data = {"product": {"product_name": "Bar", "nutriments": {"energy_100g": 2092}}}
    assert parse_off_product(data, Language.EN).kcal == pytest.approx(500)
    assert parse_off_product({"product": {"product_name": "Bar"}}, Language.EN) is None
