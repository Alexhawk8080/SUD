# -*- coding: utf-8 -*-
"""
Тесты cases (stage16a1b, D1a2).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_cases_db.py
"""

import os
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


def year_data(s="1"):
    return {
        "судья": f"Судья{s}", "секретарь": f"Сек{s}",
        "дата_утверждения": "—", "дата_акта": "—",
        "номер_акта": s, "дата_подписи": "—",
        "протокол_эк_дата": "—", "протокол_эк_номер": s,
    }


def make_cases(n, start=1, case_type="civil"):
    out = []
    for i in range(n):
        out.append({
            "case_type": case_type,
            "row_index": i + 1,
            "date": "01.01.2020",
            "case_number": f"2-{start + i}/2020",
            "applicants": f"Истец {i}",
            "respondents": f"Ответчик {i}",
            "category": "о защите прав потребителей",
            "opis_number": "1",
            "unit_number": str(i + 1),
            "note": "",
            "end_date": "01.02.2020",
            "is_problematic": False,
            "is_alimony": False,
            "is_valid": True,
            "skip_reason": "",
        })
    return out


def main():
    tmp = tempfile.mkdtemp(prefix="cases_")
    db_path = os.path.join(tmp, "app.db")

    print("[1] Подготовка: участок + год + файл")
    conn = db.init_db(db_path)
    aid = db.add_court_area(conn, {"номер": "9"})
    yid = db.add_court_year(conn, aid, 2020, year_data("20"))
    sfid = db.save_source_file(conn, yid, "источник.xlsx", b"BLOB")
    check("Файл создан", sfid > 0, True)

    print("\n[2] add_cases_bulk: 5 дел")
    n = db.add_cases_bulk(conn, sfid, make_cases(5))
    check("Вставлено 5", n, 5)
    check("count = 5", db.count_cases_for_source(conn, sfid), 5)

    print("\n[3] list_cases")
    cases = db.list_cases(conn, source_file_id=sfid)
    check("5 записей", len(cases), 5)
    check("Первый row_index = 1", cases[0]["row_index"], 1)
    check("case_number первого", cases[0]["case_number"], "2-1/2020")
    check("case_type = civil", cases[0]["case_type"], "civil")
    check("is_valid = True", cases[0]["is_valid"], True)
    check("is_alimony = False", cases[0]["is_alimony"], False)

    print("\n[4] get_case")
    c1 = db.get_case(conn, cases[0]["id"])
    check("Найден", c1 is not None, True)
    check("case_number", c1["case_number"], "2-1/2020")
    check("Несуществующий -> None", db.get_case(conn, 99999), None)

    print("\n[5] Дела разных типов")
    sfid2 = db.save_source_file(conn, yid, "админ.xlsx", b"X",
                                file_kind="source")
    db.add_cases_bulk(conn, sfid2, make_cases(3, case_type="admin"))
    check("Всего дел в году",
          len(db.list_cases(conn)), 8)
    check("civil — 5",
          len(db.list_cases(conn, case_type="civil")), 5)
    check("admin — 3",
          len(db.list_cases(conn, case_type="admin")), 3)

    print("\n[6] case_types_in_year")
    types = db.case_types_in_year(conn, yid)
    check("Типы = ['admin', 'civil']", types, ["admin", "civil"])

    print("\n[7] Валидация source_file_id")
    try:
        db.add_cases_bulk(conn, 99999, make_cases(1))
        check("Несуществующий source_file_id -> ValueError",
              "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий source_file_id -> ValueError", True, True)

    print("\n[8] add_cases_bulk с пустым списком")
    check("0", db.add_cases_bulk(conn, sfid, []), 0)

    print("\n[9] delete_cases_for_source")
    deleted = db.delete_cases_for_source(conn, sfid2)
    check("Удалено 3", deleted, 3)
    check("Осталось 5 дел",
          len(db.list_cases(conn)), 5)

    print("\n[10] Каскадное удаление дел при удалении файла")
    db.delete_source_file(conn, sfid)
    check("Всего дел 0", len(db.list_cases(conn)), 0)

    print("\n[11] Алиментное дело")
    sf3 = db.save_source_file(conn, yid, "алименты.xlsx", b"X")
    db.add_cases_bulk(conn, sf3, [{
        "case_type": "civil", "row_index": 1,
        "case_number": "2-99/2020",
        "category": "о взыскании алиментов",
        "is_alimony": True, "is_valid": True,
    }])
    c = db.list_cases(conn, source_file_id=sf3)[0]
    check("is_alimony = True", c["is_alimony"], True)

    print("\n[12] Проблемная запись")
    sf4 = db.save_source_file(conn, yid, "проблемные.xlsx", b"X")
    db.add_cases_bulk(conn, sf4, [{
        "case_type": "civil", "row_index": 1,
        "case_number": "2-1/2020",
        "category": "",
        "is_problematic": True, "is_valid": True,
        "skip_reason": "нет категории",
    }])
    c = db.list_cases(conn, source_file_id=sf4)[0]
    check("is_problematic", c["is_problematic"], True)
    check("skip_reason", c["skip_reason"], "нет категории")

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
