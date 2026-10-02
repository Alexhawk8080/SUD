# fix_49a_01
import sqlite3
from court_case_app.core.inventory_editor.model import Doc
from court_case_app.core.inventory_editor.repository import (
    list_docs, replace_docs, add_case, delete_case, delete_row,
)


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE processing_inventory_rows ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " inventory_id INTEGER,"
        " row_index INTEGER,"
        " sequence_number INTEGER,"
        " title TEXT,"
        " prefix TEXT,"
        " case_number INTEGER,"
        " year INTEGER,"
        " pages_count INTEGER,"
        " sheet_numbers TEXT)"
    )
    return conn


def test_list_empty():
    conn = _db()
    assert list_docs(conn, 1) == []


def test_replace_and_list():
    conn = _db()
    docs = [Doc("X", "2", 105, 2019, 1), Doc("Y", "2", 105, 2019, 2)]
    replace_docs(conn, 1, docs)
    out = list_docs(conn, 1)
    assert len(out) == 2
    assert out[0].case_number == 105
    assert out[1].pages_count == 2


def test_add_case_in_order():
    conn = _db()
    replace_docs(conn, 1, [Doc("X", "2", 105, 2019, 1)])
    add_case(conn, 1, prefix="2", case_number=107, year=2019,
             doc_titles=["Z"])
    add_case(conn, 1, prefix="2", case_number=106, year=2019,
             doc_titles=["Y"])
    nums = [d.case_number for d in list_docs(conn, 1)]
    assert nums == [105, 106, 107]


def test_delete_case():
    conn = _db()
    replace_docs(conn, 1, [Doc("X", "2", 105, 2019, 1),
                           Doc("Y", "2", 106, 2019, 1)])
    n = delete_case(conn, 1, 2019, 105)
    assert n == 1
    assert len(list_docs(conn, 1)) == 1


def test_delete_row():
    conn = _db()
    replace_docs(conn, 1, [Doc("X", "2", 105, 2019, 1),
                           Doc("Y", "2", 105, 2019, 1)])
    docs = list_docs(conn, 1)
    delete_row(conn, 1, docs[0].row_id)
    assert len(list_docs(conn, 1)) == 1
