import pytest

from belok.bot.texts import COMMANDS, STRINGS
from belok.i18n import Language, guess_language


@pytest.mark.parametrize("table", [STRINGS, COMMANDS])
def test_every_string_has_all_languages(table):
    for key, variants in table.items():
        assert set(variants) == set(Language), key


@pytest.mark.parametrize(
    ("code", "expected"),
    [("ru", Language.RU), ("uk", Language.RU), ("en-US", Language.EN), (None, Language.EN)],
)
def test_guess_language(code, expected):
    assert guess_language(code) == expected
