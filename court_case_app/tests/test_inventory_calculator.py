# fix_49a_01
from court_case_app.core.inventory_editor.model import Doc
from court_case_app.core.inventory_editor.calculator import compute_derived


def test_first_row_uses_case_number_as_E():
    docs = [Doc("X", "2", 105, 2019, 1)]
    d = compute_derived(docs)
    assert d[0] == {"A": 1, "B": 1, "E": 105, "I": 1, "J": None,
                    "case_number": 105}


def test_first_row_case_one():
    docs = [Doc("X", "2", 1, 2019, 1)]
    d = compute_derived(docs)
    assert d[0]["E"] == 1


def test_increment_continuous():
    docs = [Doc("X", "2", 105, 2019, 1), Doc("Y", "2", 106, 2019, 1)]
    d = compute_derived(docs)
    assert d[1]["E"] == 1
    assert d[1]["I"] == 2
    assert d[1]["B"] == 2


def test_increment_zero_same_case():
    docs = [Doc("X", "2", 105, 2019, 1), Doc("Y", "2", 105, 2019, 1)]
    d = compute_derived(docs)
    assert d[1]["E"] == 0


def test_pages_multi():
    docs = [Doc("X", "2", 105, 2019, 3)]
    d = compute_derived(docs)
    assert d[0]["J"] == 3


def test_skip_number():
    docs = [Doc("X", "2", 105, 2019, 1), Doc("Y", "2", 108, 2019, 1)]
    d = compute_derived(docs)
    assert d[1]["E"] == 3


def test_volume_break_at_150():
    docs = [
        Doc("X", "2", 105, 2019, 149),
        Doc("Y", "2", 106, 2019, 1),
        Doc("Z", "2", 107, 2019, 1),
    ]
    d = compute_derived(docs)
    assert d[0]["J"] == 149
    assert d[1]["A"] == 1
    assert d[1]["I"] == 150
    assert d[2]["A"] == 2
    assert d[2]["I"] == 1
