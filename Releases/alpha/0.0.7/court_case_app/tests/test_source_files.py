# -*- coding: utf-8 -*-
"""
Тесты source_files (stage16a1b, D1a2).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_source_files.py
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


def main():
    tmp = tempfile.mkdtemp(prefix="sf_")
    db_path = os.path.join(tmp, "app.db")

    print("[1] Подготовка: участок + год")
    conn = db.init_db(db_path)
    aid = db.add_court_area(conn, {"номер": "9"})
    yid = db.add_court_year(conn, aid, 2020, year_data("20"))
    check("Год создан", yid > 0, True)

    print("\n[2] Список пуст")
    check("Пусто", db.list_source_files(conn, yid), [])
    check("count = 0", db.count_source_files(conn, yid), 0)

    print("\n[3] save_source_file v1")
    sf1 = db.save_source_file(
        conn, yid, "файл1.xlsx", b"BLOB-1",
        file_kind="source", sheet_name="Результат обработки",
        header_row=3, mapping={"title": 2, "dates": 3}, row_count=10)
    check("id получен", sf1 > 0, True)
    rec1 = db.get_source_file(conn, sf1)
    check("version = 1", rec1["version"], 1)
    check("is_current = True", rec1["is_current"], True)
    check("file_kind = source", rec1["file_kind"], "source")
    check("row_count = 10", rec1["row_count"], 10)
    check("mapping прочитан", rec1["mapping"], {"title": 2, "dates": 3})
    check("sheet_name", rec1["sheet_name"], "Результат обработки")
    check("header_row", rec1["header_row"], 3)

    print("\n[4] get_source_file_content")
    content = db.get_source_file_content(conn, sf1)
    check("BLOB", content, b"BLOB-1")
    check("Несуществующий -> None",
          db.get_source_file_content(conn, 9999), None)

    print("\n[5] save_source_file v2 (тот же kind)")
    sf2 = db.save_source_file(
        conn, yid, "файл1_v2.xlsx", b"BLOB-2",
        file_kind="source", row_count=12)
    rec1 = db.get_source_file(conn, sf1)
    rec2 = db.get_source_file(conn, sf2)
    check("v2 = 2", rec2["version"], 2)
    check("v2 is_current", rec2["is_current"], True)
    check("v1 больше не current", rec1["is_current"], False)

    print("\n[6] Отдельная ветка file_kind='processed'")
    sf3 = db.save_source_file(
        conn, yid, "результат.docx", b"BLOB-3",
        file_kind="processed")
    check("processed version = 1", db.get_source_file(conn, sf3)["version"], 1)
    check("source v2 всё ещё current",
          db.get_source_file(conn, sf2)["is_current"], True)
    check("Всего 3 записи", db.count_source_files(conn, yid), 3)

    print("\n[7] get_current_source_file")
    cur = db.get_current_source_file(conn, yid, file_kind="source")
    check("current source = v2", cur["id"], sf2)
    cur_p = db.get_current_source_file(conn, yid, file_kind="processed")
    check("current processed = v1", cur_p["id"], sf3)

    print("\n[8] list_source_files сортировка")
    files = db.list_source_files(conn, yid)
    check("3 записи", len(files), 3)
    # Сортировка: court_year_id, file_kind, version DESC
    # 'processed' < 'source' лексикографически
    check("Первый — processed v1", files[0]["id"], sf3)
    check("Второй — source v2", files[1]["id"], sf2)
    check("Третий — source v1", files[2]["id"], sf1)

    files_src = db.list_source_files(conn, yid, file_kind="source")
    check("Только source — 2", len(files_src), 2)

    print("\n[9] set_current_source_file")
    ok = db.set_current_source_file(conn, sf1)
    check("set_current ok", ok, True)
    check("v1 current", db.get_source_file(conn, sf1)["is_current"], True)
    check("v2 не current", db.get_source_file(conn, sf2)["is_current"], False)
    check("processed не тронут",
          db.get_source_file(conn, sf3)["is_current"], True)

    print("\n[10] delete_source_file")
    db.delete_source_file(conn, sf2)
    check("Всего 2", db.count_source_files(conn, yid), 2)
    check("Удалённый -> None", db.get_source_file(conn, sf2), None)

    print("\n[11] Валидация")
    try:
        db.save_source_file(conn, yid, "x.xlsx", b"x",
                            file_kind="unknown")
        check("Неверный file_kind -> ValueError", "нет ошибки", "ValueError")
    except ValueError:
        check("Неверный file_kind -> ValueError", True, True)

    try:
        db.save_source_file(conn, 99999, "x.xlsx", b"x")
        check("Несуществующий год -> ValueError", "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий год -> ValueError", True, True)

    print("\n[12] Каскадное удаление при удалении года")
    tmp_yid = db.add_court_year(conn, aid, 2021, year_data("21"))
    sf_tmp = db.save_source_file(conn, tmp_yid, "tmp.xlsx", b"x")
    check("Файл создан", db.get_source_file(conn, sf_tmp) is not None, True)
    db.delete_court_year(conn, tmp_yid)
    check("После удаления года файла нет",
          db.get_source_file(conn, sf_tmp), None)

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
