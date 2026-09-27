# -*- coding: utf-8 -*-
"""
Тесты вынесения CRUD source_files/cases в database.cases (stage16d2, D2).

Проверяет:
    * прямой импорт `from database.cases import ...`;
    * обратную совместимость через `db.save_source_file(...)`;
    * что функции идентичны (модуль — тот же объект).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_cases_module.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import db
from database import cases as cases_mod

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


def year_data(s="1"):
    return {
        "судья": f"Судья{s}", "секретарь": f"Сек{s}",
        "дата_утверждения": "—", "дата_акта": "—",
        "номер_акта": s, "дата_подписи": "—",
        "протокол_эк_дата": "—", "протокол_эк_номер": s,
    }


def main():
    tmp = tempfile.mkdtemp(prefix="cases_mod_")
    db_path = os.path.join(tmp, "app.db")
    conn = db.init_db(db_path)
    aid = db.add_court_area(conn, {"номер": "9"})
    yid = db.add_court_year(conn, aid, 2020, year_data("20"))

    print("[1] Обратная совместимость через db.*")
    sfid = db.save_source_file(conn, yid, "x.xlsx", b"BLOB-1")
    check("db.save_source_file работает", sfid > 0, True)
    check("db.list_source_files работает",
          len(db.list_source_files(conn, yid)), 1)
    check("db.get_source_file_content",
          db.get_source_file_content(conn, sfid), b"BLOB-1")
    check("db.count_source_files", db.count_source_files(conn, yid), 1)

    print("\n[2] Прямой доступ через database.cases.*")
    sfid2 = cases_mod.save_source_file(conn, yid, "x2.xlsx", b"BLOB-2")
    check("cases_mod.save_source_file работает", sfid2 > 0, True)
    check("cases_mod.list_source_files",
          len(cases_mod.list_source_files(conn, yid)), 2)

    print("\n[3] Ре-экспорт в db ссылается на те же функции")
    check("db.save_source_file is cases_mod.save_source_file",
          db.save_source_file is cases_mod.save_source_file, True)
    check("db.list_cases is cases_mod.list_cases",
          db.list_cases is cases_mod.list_cases, True)
    check("db.add_cases_bulk is cases_mod.add_cases_bulk",
          db.add_cases_bulk is cases_mod.add_cases_bulk, True)

    print("\n[4] Работа с cases: одинаковый результат")
    n = db.add_cases_bulk(conn, sfid2, [{
        "case_type": "civil", "row_index": 1,
        "case_number": "2-1/2020", "is_valid": True,
    }])
    check("add_cases_bulk = 1", n, 1)
    check("list_cases через db",
          len(db.list_cases(conn, source_file_id=sfid2)), 1)
    check("list_cases через cases_mod",
          len(cases_mod.list_cases(conn, source_file_id=sfid2)), 1)

    print("\n[5] case_types_in_year")
    check("['civil']", db.case_types_in_year(conn, yid), ["civil"])

    print("\n[6] Валидация")
    try:
        db.save_source_file(conn, 99999, "x.xlsx", b"x")
        check("Несуществующий год -> ValueError", "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий год -> ValueError", True, True)

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
