from belok.domain.nutrition import Macros
from belok.services.recipes import covers, gap_score

LEFT = Macros(kcal=700, protein=60, fat=15, carbs=80)


def test_high_protein_dish_beats_pasta_for_a_protein_gap():
    chicken = Macros(kcal=450, protein=50, fat=8, carbs=40)
    pasta = Macros(kcal=650, protein=18, fat=12, carbs=95)
    assert gap_score(chicken, LEFT) > gap_score(pasta, LEFT)


def test_dishes_past_whats_left_are_not_suggested():
    assert gap_score(Macros(kcal=800, protein=60, fat=10, carbs=60), LEFT) is None
    assert gap_score(Macros(kcal=500, protein=30, fat=30, carbs=20), LEFT) is None
    assert gap_score(Macros(), LEFT) is None


def test_covers_only_reports_missing_macros():
    left = Macros(kcal=600, protein=50, fat=2, carbs=100)
    portion = Macros(kcal=400, protein=40, fat=6, carbs=120)
    assert covers(portion, left) == {"protein": 80, "carbs": 100}
