from belok.catalog import Group, catalog, find_by_name


def test_catalog_entries_are_complete():
    items = catalog().values()
    assert len(items) > 500
    for x in items:
        assert x.name["en"] and x.instructions["en"] and x.images > 0
        assert set(x.name) == set(x.instructions)
        if "ru" in x.instructions:
            assert len(x.instructions["ru"]) == len(x.instructions["en"])


def test_every_group_has_exercises():
    groups = {x.group for x in catalog().values()}
    assert groups == set(Group)


def test_find_by_name_is_case_insensitive():
    item = find_by_name("barbell bench press - medium grip")
    assert item is not None and item.group == Group.CHEST
    assert find_by_name("no such exercise") is None
