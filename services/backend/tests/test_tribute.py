import hashlib
import hmac

from belok.services.tribute import TributeCatalog, parse_plans, signature_valid


def test_parse_plans_skips_malformed_items():
    plans = parse_plans("IMK:30, IMM:90,broken,IMO:x")
    assert [(p.code, p.days) for p in plans] == [("IMK", 30), ("IMM", 90)]
    assert plans[0].link == "https://web.tribute.tg/p/IMK"


def test_signature_accepts_hex_hmac_only_for_the_right_key():
    body = b'{"name":"new_digital_product"}'
    good = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert signature_valid(body, good, "secret")
    assert not signature_valid(body, good, "other")
    assert not signature_valid(body, None, "secret")


class FakeCatalog(TributeCatalog):
    def __init__(self, products: list[dict]) -> None:
        super().__init__("key", "IMK:30,IMM:90")
        self.products = products
        self.fetches = 0

    async def _fetch(self) -> list[dict]:
        self.fetches += 1
        return self.products


async def test_catalog_matches_products_by_web_link():
    catalog = FakeCatalog(
        [
            {
                "id": 7,
                "webLink": "https://web.tribute.tg/p/IMM",
                "link": "https://t.me/tribute/app?startapp=pIMM",
                "amount": 74900,
                "currency": "rub",
            }
        ]
    )
    plans = await catalog.plans()
    assert plans[0].product_id is None
    assert (plans[1].product_id, plans[1].amount, plans[1].currency) == (7, 74900, "RUB")
    assert plans[1].link.startswith("https://t.me/")
    assert plans[1].web_link == "https://web.tribute.tg/p/IMM"
    assert (await catalog.plan_for_product(7)).days == 90
    assert await catalog.plan_for_product(99) is None
