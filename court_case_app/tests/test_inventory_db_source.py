# stage_49b
import sqlite3
from court_case_app.core.inventory_editor.db_source import generate_from_cases


def _make_db(with_prefix: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    if with_prefix:
        conn.execute(
            "CREATE TABLE cases (id INTEGER PRIMARY KEY, case_number INTEGER,"
            " year INTEGER, prefix TEXT, title TEXT)"
        )
    else:
        conn.execute(
            "CREATE TABLE cases (id INTEGER PRIMARY KEY, case_number INTEGER,"
            " year INTEGER, title TEXT)"
        )
    return conn


def test_generates_civil():
    conn = _make_db()
    conn.executemany(
        "INSERT INTO cases (case_number, year, prefix, title) VALUES (?,?,?,?)",
        [
            (105, 2019, "2", "Судебный приказ по гражданскому делу"),
            (106, 2019, "2", "Определение по гражданскому делу"),
            (107, 2020, "2", "Судебный приказ по гражданскому делу"),
        ],
    )
    docs = generate_from_cases(conn, year=2019, kind="civil")
    assert [d.case_number for d in docs] == [105, 106]
    assert all(d.year == 2019 for d in docs)


def test_filters_admin_vs_civil():
    conn = _make_db()
    conn.executemany(
        "INSERT INTO cases (case_number, year, prefix, title) VALUES (?,?,?,?)",
        [
            (1, 2019, "5", "Судебный приказ по гражданскому делу"),
            (2, 2019, "5", "Постановление по делу об административном правонарушении"),
        ],
    )
    civil = generate_from_cases(conn, year=2019, kind="civil")
    admin = generate_from_cases(conn, year=2019, kind="admin")
    assert len(civil) == 1 and len(admin) == 1
    assert civil[0].case_number == 1
    assert admin[0].case_number == 2


def test_missing_columns_returns_empty():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE cases (id INTEGER PRIMARY KEY)")
    assert generate_from_cases(conn, 2019, "civil") == []


def test_without_prefix_column():
    conn = _make_db(with_prefix=False)
    conn.execute(
        "INSERT INTO cases (case_number, year, title) VALUES (1, 2019,"
        " 'Судебный приказ по гражданскому делу')"
    )
    docs = generate_from_cases(conn, 2019, "civil")
    assert len(docs) == 1 and docs[0].prefix == ""
