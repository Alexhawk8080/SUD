# -*- coding: utf-8 -*-
"""
Тесты схемы v2 (stage16a1a).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_db_schema_v2.py
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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


def main():
    tmp = tempfile.mkdtemp(prefix="schema_v2_")
    db_path = os.path.join(tmp, "app.db")

    print("[1] schema_version")
    conn = db.init_db(db_path)
    check("v3", db.get_schema_version(conn), "v3")
    check("settings.schema_version = 'v3'",
          conn.execute("SELECT value FROM settings WHERE key='schema_version'")
          .fetchone()[0], "v3")

    print("\n[2] Все таблицы v2 созданы")
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("organizations", "retention_rules", "settings",
              "case_categories", "court_areas", "court_years"):
        check(f"Таблица {t}", t in names, True)

    print("\n[3] Структура court_areas (v2)")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(court_areas)")]
    check("id", "id" in cols, True)
    check("номер", "номер" in cols, True)
    check("name", "name" in cols, True)
    check("address", "address" in cols, True)
    check("note", "note" in cols, True)
    check("created_at", "created_at" in cols, True)
    # Старые реквизитные поля ушли
    for old in ("судья", "секретарь", "дата_акта", "протокол_эк_дата"):
        check(f"Нет старого поля '{old}'", old in cols, False)

    print("\n[4] Структура court_years")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(court_years)")]
    for f in ("id", "court_area_id", "year", "судья", "секретарь",
              "дата_утверждения", "дата_акта", "номер_акта",
              "дата_подписи", "протокол_эк_дата", "протокол_эк_номер",
              "note", "is_incomplete", "is_closed", "created_at",
              "updated_at"):
        check(f"Поле '{f}'", f in cols, True)

    print("\n[5] DEFAULT_SETTINGS — только служебные")
    settings = db.get_settings(conn)
    check("auto_fix_categories=1",
          settings.get("auto_fix_categories"), "1")
    check("category_snapshot_limit=5",
          settings.get("category_snapshot_limit"), "5")
    for legacy in ("судебный_участок", "судья", "секретарь",
                   "дата_акта", "номер_акта", "протокол_эк_дата"):
        check(f"Нет legacy-ключа '{legacy}'", legacy in settings, False)

    print("\n[6] Unique index (court_area_id, year)")
    aid = db.add_court_area(conn, {"номер": "9"})
    db.add_court_year(conn, aid, 2020, {})
    try:
        db.add_court_year(conn, aid, 2020, {})
        check("UNIQUE сработал", "нет ошибки", "IntegrityError")
    except sqlite3.IntegrityError:
        check("UNIQUE сработал", True, True)

    print("\n[7] Foreign key ON DELETE CASCADE")
    check("PRAGMA foreign_keys = ON",
          conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
    # Удаление участка удаляет его годы
    db.delete_court_area(conn, aid)
    check("Годы удалены каскадом",
          conn.execute("SELECT COUNT(*) FROM court_years").fetchone()[0], 0)

    print("\n[8] Повторный init_db не задваивает")
    conn.close()
    conn = db.init_db(db_path)
    orgs = db.list_organizations(conn)
    check("ООО одно", sum(1 for o in orgs if o["name"] == "ООО"), 1)
    check("schema_version всё ещё v3",
          db.get_schema_version(conn), "v3")
    conn.close()

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
