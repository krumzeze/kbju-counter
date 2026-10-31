import pytest

from belok.bot.texts import STRINGS
from belok.i18n import Language, guess_language


def test_every_string_has_all_languages():
    for key, variants in STRINGS.items():
        assert set(variants) == set(Language), key


@pytest.mark.parametrize(
    ("code", "expected"),
    [("ru", Language.RU), ("uk", Language.RU), ("en-US", Language.EN), (None, Language.EN)],
)
def test_guess_language(code, expected):
    assert guess_language(code) == expected
