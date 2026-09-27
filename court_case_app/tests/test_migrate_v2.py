# -*- coding: utf-8 -*-
"""
Тесты миграции v1 -> v2 (stage16a1c, D1b).

Создаёт старую БД (v1) в tempfile, запускает migrate_db_v2.migrate
и проверяет результат.

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_migrate_v2.py
"""

import os
import sqlite3
import sys
import tempfile

# court_case_app (для `from database import db`)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# корень проекта (для `import migrate_db_v2`) — fix_15
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import migrate_db_v2
from database import db

FAILED = 0
PASSED = 0


def check(name: str, actual, expected):
    global FAILED, PASSED
    ok = actual == expected
    if ok:
        PASSED += 1
        print(f"  OK   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось: {expected!r}\n       получено:  {actual!r}")


# --- Старая схема v1 (фрагмент: только то, что мигрируется) ----------------

V1_SCHEMA = """
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    claim_type TEXT NOT NULL DEFAULT 'по иску'
);
CREATE TABLE retention_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    code TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    result_text TEXT
);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE case_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plaintiff_key TEXT NOT NULL,
    plaintiff_label TEXT NOT NULL,
    category TEXT NOT NULL,
    is_organization INTEGER NOT NULL DEFAULT 0,
    UNIQUE(plaintiff_key, category)
);
CREATE TABLE court_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    номер TEXT NOT NULL UNIQUE,
    судья TEXT NOT NULL DEFAULT '',
    дата_утверждения TEXT NOT NULL DEFAULT '',
    дата_акта TEXT NOT NULL DEFAULT '',
    номер_акта TEXT NOT NULL DEFAULT '',
    секретарь TEXT NOT NULL DEFAULT '',
    дата_подписи TEXT NOT NULL DEFAULT '',
    протокол_эк_дата TEXT NOT NULL DEFAULT '',
    протокол_эк_номер TEXT NOT NULL DEFAULT '',
    is_incomplete INTEGER NOT NULL DEFAULT 0
);
"""


def make_v1_db(path):
    """Создаёт БД v1 с типовыми данными."""
    conn = sqlite3.connect(path)
    conn.executescript(V1_SCHEMA)
    # Настройки: реквизиты + служебное
    conn.executemany(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        [
            ("судебный_участок", "9"),
            ("судья", "О. А. Левошина"),
            ("секретарь", "А.М. Намаюшка"),
            ("дата_утверждения", "«___» 20__ года"),
            ("дата_акта", "«__» 20__ г."),
            ("номер_акта", "1"),
            ("дата_подписи", "«__» 20__ г."),
            ("протокол_эк_дата", "«__» 20__ г."),
            ("протокол_эк_номер", "1"),
            ("auto_fix_categories", "1"),
        ])
    # Одна запись court_areas
    conn.execute(
        "INSERT INTO court_areas ("
        "номер, судья, секретарь, дата_утверждения, дата_акта, "
        "номер_акта, дата_подписи, протокол_эк_дата, "
        "протокол_эк_номер, is_incomplete) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
        ("9", "О. А. Левошина", "А.М. Намаюшка",
         "«___» 20__ года", "«__» 20__ г.", "1",
         "«__» 20__ г.", "«__» 20__ г.", "1"))
    conn.commit()
    conn.close()


def main():
    tmp = tempfile.mkdtemp(prefix="migrate_v2_")
    db_path = os.path.join(tmp, "app.db")
    make_v1_db(db_path)

    print("[1] До миграции: схема v1")
    conn = sqlite3.connect(db_path)
    check("_detect_version = v1", migrate_db_v2._detect_version(conn), "v1")
    conn.close()

    print("\n[2] Миграция")
    report = migrate_db_v2.migrate(db_path)
    check("status = ok", report["status"], "ok")
    check("backup создан", os.path.exists(report["backup"]), True)
    check("court_areas_migrated = 1", report["court_areas_migrated"], 1)
    check("years_created = 1", report["years_created"], 1)
    check("settings_deleted = 9", report["settings_deleted"], 9)

    print("\n[3] После миграции: схема v2")
    conn = db.init_db(db_path)
    check("schema_version = v2", db.get_schema_version(conn), "v2")

    print("\n[4] Участок перенесён")
    areas = db.list_court_areas(conn)
    check("1 участок", len(areas), 1)
    check("номер = '9'", areas[0]["номер"], "9")
    check("name пустое (новые поля)", areas[0]["name"], "")
    check("address пустое", areas[0]["address"], "")

    print("\n[5] Год 2019 с реквизитами")
    aid = areas[0]["id"]
    years = db.list_court_years(conn, aid)
    check("1 год", len(years), 1)
    check("year = 2019", years[0]["year"], 2019)
    check("судья", years[0]["судья"], "О. А. Левошина")
    check("секретарь", years[0]["секретарь"], "А.М. Намаюшка")
    check("номер_акта", years[0]["номер_акта"], "1")
    check("is_closed = False", years[0]["is_closed"], False)
    check("is_incomplete = False", years[0]["is_incomplete"], False)

    print("\n[6] Legacy-ключи settings удалены")
    settings = db.get_settings(conn)
    for legacy in ("судебный_участок", "судья", "секретарь",
                   "дата_акта", "номер_акта", "протокол_эк_дата"):
        check(f"Нет '{legacy}'", legacy in settings, False)
    check("auto_fix_categories остался",
          settings.get("auto_fix_categories"), "1")
    check("schema_version = v2",
          settings.get("schema_version"), "v2")

    print("\n[7] Повторная миграция: схема уже v2")
    report2 = migrate_db_v2.migrate(db_path)
    check("status = already_v2", report2["status"], "already_v2")
    check("backup не создан", report2["backup"], None)

    print("\n[8] Пустой файл: status = empty")
    nonexist = os.path.join(tmp, "nope.db")
    report3 = migrate_db_v2.migrate(nonexist)
    check("status = empty", report3["status"], "empty")

    print("\n[9] Несколько участков")
    db_path2 = os.path.join(tmp, "two.db")
    make_v1_db(db_path2)
    # Добавим второй участок
    c = sqlite3.connect(db_path2)
    c.execute(
        "INSERT INTO court_areas (номер, судья, is_incomplete) "
        "VALUES (?, ?, 1)", ("5", "Другой Судья"))
    c.commit()
    c.close()
    report4 = migrate_db_v2.migrate(db_path2)
    check("Перенесено 2 участка", report4["court_areas_migrated"], 2)
    check("Создано 2 года", report4["years_created"], 2)
    conn2 = db.init_db(db_path2)
    check("В БД 2 участка", len(db.list_court_areas(conn2)), 2)
    conn2.close()

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
