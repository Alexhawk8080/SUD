# -*- coding: utf-8 -*-
"""
Тесты processing_inventories (stage16d3b).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_inventories_db.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import db
from database import inventories as inv_mod

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


def make_inv_rows(n=3):
    return [{
        "row_index": i + 1,
        "sequence_number": str(i + 1),
        "title": f"Дело №2-{i+1}/2020 о защите прав",
        "prefix": "2",
        "case_number": str(i + 1),
        "year": "2020",
        "pages_count": str(10 + i),
        "sheet_numbers": f"{i+1}-{i+2}",
    } for i in range(n)]


def main():
    tmp = tempfile.mkdtemp(prefix="inv_")
    db_path = os.path.join(tmp, "app.db")
    conn = db.init_db(db_path)
    aid = db.add_court_area(conn, {"номер": "9"})
    yid = db.add_court_year(conn, aid, 2020, year_data("20"))

    print("[1] Результат + опись")
    rid = db.save_processing_result(conn, yid, "civil", [], target_year=2020)
    inv_id = db.save_processing_inventory(conn, rid, make_inv_rows(3),
                                          note="черновик")
    check("id получен", inv_id > 0, True)
    rec = db.get_processing_inventory(conn, inv_id)
    check("result_id", rec["result_id"], rid)
    check("note", rec["note"], "черновик")

    print("\n[2] Строки описи")
    rows = db.list_inventory_rows(conn, inv_id)
    check("3 строки", len(rows), 3)
    check("sequence_number", rows[0]["sequence_number"], "1")
    check("case_number", rows[0]["case_number"], "1")
    check("prefix", rows[0]["prefix"], "2")
    check("year", rows[0]["year"], "2020")
    check("pages_count", rows[0]["pages_count"], "10")
    check("sheet_numbers", rows[0]["sheet_numbers"], "1-2")
    check("count", db.count_inventory_rows(conn, inv_id), 3)

    print("\n[3] extra_json")
    inv2 = db.save_processing_inventory(conn, rid, [{
        "row_index": 1, "title": "x",
        "extra": {"foo": "bar", "n": 42},
    }])
    # Перезаписали — старый id исчез
    check("Старый id исчез", db.get_processing_inventory(conn, inv_id), None)
    rows2 = db.list_inventory_rows(conn, inv2)
    check("extra прочитан", rows2[0]["extra"], {"foo": "bar", "n": 42})

    print("\n[4] Одна опись на результат")
    check("get_inventory_by_result возвращает актуальный",
          db.get_inventory_by_result(conn, rid)["id"], inv2)
    check("Всего одна опись",
          len(db.list_processing_inventories(conn)), 1)

    print("\n[5] add_inventory_rows_bulk")
    n = db.add_inventory_rows_bulk(conn, inv2, make_inv_rows(2))
    check("добавлено 2", n, 2)
    check("всего 3", db.count_inventory_rows(conn, inv2), 3)

    print("\n[6] Валидация")
    try:
        db.save_processing_inventory(conn, 99999, [])
        check("Несуществующий result_id -> ValueError",
              "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий result_id -> ValueError", True, True)
    try:
        db.add_inventory_rows_bulk(conn, 99999, make_inv_rows(1))
        check("Несуществующий inventory_id -> ValueError",
              "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий inventory_id -> ValueError", True, True)

    print("\n[7] Каскадные удаления")
    db.delete_processing_inventory(conn, inv2)
    check("После удаления описи — нет",
          db.get_processing_inventory(conn, inv2), None)
    check("Строк 0", db.count_inventory_rows(conn, inv2), 0)

    # Удаление результата -> опись уходит
    inv3 = db.save_processing_inventory(conn, rid, make_inv_rows(1))
    db.delete_processing_result(conn, rid)
    check("Описи нет после удаления результата",
          db.get_processing_inventory(conn, inv3), None)

    print("\n[8] Re-export")
    check("save_processing_inventory",
          db.save_processing_inventory is inv_mod.save_processing_inventory,
          True)

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
