# -*- coding: utf-8 -*-
"""
Тесты processing_results (stage16d3a).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_results_db.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import db
from database import results as results_mod

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
    return {"судья": f"Судья{s}", "секретарь": f"Сек{s}",
            "дата_утверждения": "—", "дата_акта": "—",
            "номер_акта": s, "дата_подписи": "—",
            "протокол_эк_дата": "—", "протокол_эк_номер": s}


def make_records(n=3):
    return [{
        "row_index": i + 1, "sequential": str(i + 1),
        "title": f"Гражданское дело №2-{i+1}/2020 о защите прав",
        "dates": "01.01.2020\n01.02.2020",
        "opis": "1", "unit": str(i + 1), "count": "1",
        "retention": "3 года ЭПК Ст. 208", "note": "",
        "case_number": f"2-{i+1}/2020",
    } for i in range(n)]


def main():
    tmp = tempfile.mkdtemp(prefix="results_")
    db_path = os.path.join(tmp, "app.db")
    conn = db.init_db(db_path)
    aid = db.add_court_area(conn, {"номер": "9"})
    yid = db.add_court_year(conn, aid, 2020, year_data("20"))

    print("[1] Сохранение результата")
    rid = db.save_processing_result(
        conn, yid, "civil", make_records(3),
        stats={"min_case_num": 1, "max_case_num": 3},
        output_format="word", process_alimony=False,
        target_year=2020, court_area_id=aid)
    check("id получен", rid > 0, True)
    rec = db.get_processing_result(conn, rid)
    check("case_type = civil", rec["case_type"], "civil")
    check("record_count = 3", rec["record_count"], 3)
    check("stats прочитан",
          rec["stats"], {"min_case_num": 1, "max_case_num": 3})
    check("output_format = word", rec["output_format"], "word")
    check("is_stale = False", rec["is_stale"], False)
    check("target_year = 2020", rec["target_year"], 2020)

    print("\n[2] Строки результата")
    rows = db.list_result_rows(conn, rid)
    check("3 строки", len(rows), 3)
    check("row[0] case_number", rows[0]["case_number"], "2-1/2020")
    check("row[0] sequential", rows[0]["sequential"], "1")
    check("count_result_rows", db.count_result_rows(conn, rid), 3)

    print("\n[3] Пара (год, тип) — уникальна")
    rid2 = db.save_processing_result(conn, yid, "civil", make_records(5))
    check("Старый id исчез", db.get_processing_result(conn, rid), None)
    check("Новый id есть", db.get_processing_result(conn, rid2) is not None, True)
    check("Строк стало 5", db.count_result_rows(conn, rid2), 5)

    print("\n[4] Второй тип в том же году — отдельно")
    rid_admin = db.save_processing_result(
        conn, yid, "admin", make_records(2))
    check("civil и admin — две записи",
          len(db.list_processing_results(conn, yid)), 2)
    check("admin — 2",
          db.count_result_rows(conn, rid_admin), 2)

    print("\n[5] get_processing_result_by_pair")
    r = db.get_processing_result_by_pair(conn, yid, "civil")
    check("civil найден", r["id"], rid2)
    r = db.get_processing_result_by_pair(conn, yid, "admin")
    check("admin найден", r["id"], rid_admin)
    check("другого года нет",
          db.get_processing_result_by_pair(conn, 99999, "civil"), None)

    print("\n[6] is_stale")
    db.set_result_stale(conn, rid2, True)
    check("is_stale = True",
          db.get_processing_result(conn, rid2)["is_stale"], True)
    db.set_result_stale(conn, rid2, False)
    check("is_stale обратно False",
          db.get_processing_result(conn, rid2)["is_stale"], False)

    print("\n[7] add_result_rows_bulk")
    n = db.add_result_rows_bulk(conn, rid_admin, make_records(2))
    check("добавлено 2", n, 2)
    check("всего 4", db.count_result_rows(conn, rid_admin), 4)

    print("\n[8] Валидация")
    try:
        db.save_processing_result(conn, yid, "unknown", make_records(1))
        check("Неверный case_type -> ValueError", "нет ошибки", "ValueError")
    except ValueError:
        check("Неверный case_type -> ValueError", True, True)
    try:
        db.save_processing_result(conn, 99999, "civil", make_records(1))
        check("Несуществующий год -> ValueError", "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий год -> ValueError", True, True)
    try:
        db.add_result_rows_bulk(conn, 99999, make_records(1))
        check("Несуществующий result_id -> ValueError", "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий result_id -> ValueError", True, True)

    print("\n[9] Каскадное удаление строк")
    db.delete_processing_result(conn, rid2)
    check("count_result_rows = 0", db.count_result_rows(conn, rid2), 0)
    check("get_processing_result = None",
          db.get_processing_result(conn, rid2), None)

    print("\n[10] Каскадное удаление при удалении года")
    db.delete_court_year(conn, yid)
    check("Все результаты года удалены",
          db.list_processing_results(conn, yid), [])

    print("\n[11] Re-export: db и results — те же функции")
    check("save_processing_result",
          db.save_processing_result is results_mod.save_processing_result, True)
    check("list_result_rows",
          db.list_result_rows is results_mod.list_result_rows, True)

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
