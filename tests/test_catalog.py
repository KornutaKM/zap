from app.catalog import CATALOG, get_children, get_node

def test_root_has_main_groups():
    titles = {node.title for node in get_children("root")}
    assert "ТО и фильтры" in titles
    assert "Тормозная система" in titles
    assert "Подвеска и рулевое" in titles

def test_leaf_has_search_query():
    node = get_node("front_pads")
    assert node is not None
    assert node.children == ()
    assert node.query == "передние тормозные колодки"

def test_every_child_exists_and_has_correct_parent():
    for node in CATALOG.values():
        for child_id in node.children:
            assert child_id in CATALOG
            assert CATALOG[child_id].parent == node.id
