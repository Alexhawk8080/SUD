# -*- coding: utf-8 -*-
"""
Тесты category_check_snapshots (stage16d3c).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_category_snapshots_db.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import db
from database import category_snapshots as snap_mod

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


def make_problems(n=2):
    return [{
        "case_number": f"2-{i+1}/2020",
        "applicants": f"Истец {i+1}",
        "current_category": "",
        "suggested": "о защите прав потребителей",
        "source": "analog",
        "options": ["о защите прав потребителей", "о взыскании долга"],
    } for i in range(n)]


def main():
    tmp = tempfile.mkdtemp(prefix="snap_")
    db_path = os.path.join(tmp, "app.db")
    conn = db.init_db(db_path)
    aid = db.add_court_area(conn, {"номер": "9"})
    yid = db.add_court_year(conn, aid, 2020, year_data("20"))
    sfid = db.save_source_file(conn, yid, "x.xlsx", b"BLOB")

    print("[1] Лимит по умолчанию")
    check("limit = 5", db.get_snapshot_limit(conn), 5)

    print("\n[2] Снимок: 2 проблемных дела")
    sid = db.save_category_snapshot(
        conn, sfid, make_problems(2),
        stats={"total": 2, "with_analogs": 1,
               "from_dictionary": 0, "no_analog": 1})
    check("id получен", sid > 0, True)
    rec = db.get_category_snapshot(conn, sid)
    check("stats прочитан",
          rec["stats"],
          {"total": 2, "with_analogs": 1,
           "from_dictionary": 0, "no_analog": 1})

    print("\n[3] Проблемы снимка")
    probs = db.list_category_problems(conn, sid)
    check("2 проблемы", len(probs), 2)
    check("case_number", probs[0]["case_number"], "2-1/2020")
    check("source", probs[0]["source"], "analog")
    check("options прочитан",
          probs[0]["options"],
          ["о защите прав потребителей", "о взыскании долга"])

    print("\n[4] Несколько снимков — список")
    for i in range(3):
        db.save_category_snapshot(conn, sfid, make_problems(1),
                                   stats={"total": 1})
    check("4 снимка", len(db.list_category_snapshots(conn, sfid)), 4)

    print("\n[5] Ротация при лимите 3")
    db.set_snapshot_limit(conn, 3)
    check("limit = 3", db.get_snapshot_limit(conn), 3)
    # Ещё один снимок → должно остаться 3
    db.save_category_snapshot(conn, sfid, make_problems(1))
    check("3 снимка после ротации",
          len(db.list_category_snapshots(conn, sfid)), 3)

    print("\n[6] Ротация при лимите 1")
    db.set_snapshot_limit(conn, 1)
    db.save_category_snapshot(conn, sfid, make_problems(1))
    snaps = db.list_category_snapshots(conn, sfid)
    check("1 снимок", len(snaps), 1)

    print("\n[7] delete_category_snapshot")
    sid_last = snaps[0]["id"]
    db.delete_category_snapshot(conn, sid_last)
    check("Снимок исчез",
          db.get_category_snapshot(conn, sid_last), None)
    check("Проблем тоже нет",
          db.list_category_problems(conn, sid_last), [])

    print("\n[8] Валидация")
    try:
        db.save_category_snapshot(conn, 99999, [], {})
        check("Несуществующий file_id -> ValueError",
              "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий file_id -> ValueError", True, True)
    try:
        db.set_snapshot_limit(conn, 0)
        check("limit = 0 -> ValueError", "нет ошибки", "ValueError")
    except ValueError:
        check("limit = 0 -> ValueError", True, True)

    print("\n[9] Каскад: удаление source_file -> снимки уходят")
    sfid2 = db.save_source_file(conn, yid, "y.xlsx", b"BLOB")
    sid2 = db.save_category_snapshot(conn, sfid2, make_problems(1))
    db.delete_source_file(conn, sfid2)
    check("Снимок исчез",
          db.get_category_snapshot(conn, sid2), None)

    print("\n[10] Re-export")
    check("save_category_snapshot",
          db.save_category_snapshot is snap_mod.save_category_snapshot, True)

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
