# -*- coding: utf-8 -*-
"""
Сквозные тесты pipeline с участками и годами (stage16a1a).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_pipeline_areas.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from docx import Document

from core.excel_reader import SourceRow
from core.pipeline import process_rows
from database import db

FAILED = 0
PASSED = 0

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "docs",
                        "АКТ уничтожения гражданских дел.docx")


def check(name: str, actual, expected):
    global FAILED, PASSED
    ok = actual == expected
    if ok:
        PASSED += 1
        print(f"  OK   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось: {expected!r}\n       получено:  {actual!r}")


def make_rows():
    return [SourceRow({
        "date": None, "case_number": "2-1/2020",
        "applicants": "Тестов Тест Тестович",
        "respondents": "Тестова Теста Тестовна",
        "category": "Исковое заявление о расторжении брака",
        "opis_number": 1, "unit_number": 1,
        "note": "", "end_date": None,
    })]


def year_data(judge, sec):
    return {
        "судья": judge, "секретарь": sec,
        "дата_утверждения": "«___» 20__ года",
        "дата_акта": "«__» 20__ г.", "номер_акта": "1",
        "дата_подписи": "«__» 20__ г.",
        "протокол_эк_дата": "«__» 20__ г.",
        "протокол_эк_номер": "1",
    }


def docx_text(path):
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


def main():
    tmp = tempfile.mkdtemp(prefix="pipe_v2_")
    db_path = os.path.join(tmp, "app.db")
    out_dir = os.path.join(tmp, "out")

    print("[1] Подготовка БД v2")
    conn = db.init_db(db_path)
    check("Участков нет", db.list_court_areas(conn), [])
    aid = db.add_court_area(conn, {"номер": "9", "name": "СУ 9"})
    db.add_court_year(conn, aid, 2019, year_data("Судья19", "Сек19"))
    db.add_court_year(conn, aid, 2020, year_data("Судья20", "Сек20"))
    conn.close()

    print("\n[2] Без court_area_id -> fallback на settings (пустой)")
    res = process_rows(make_rows(), 2020, False, "word", db_path,
                       TEMPLATE, out_dir)
    check("filename без 'СУ'", "СУ" in res["filename"], False)

    print("\n[3] court_area_id и target_year=2020 -> берутся из 2020")
    res = process_rows(make_rows(), 2020, False, "word", db_path,
                       TEMPLATE, out_dir, court_area_id=aid)
    check("filename с 9СУ", "9 CУ" in res["filename"], True)
    text = docx_text(res["path"])
    check("Судья20 в акте", "Судья20" in text, True)
    check("Сек20 в акте", "Сек20" in text, True)

    print("\n[4] target_year=2019 -> берутся реквизиты 2019")
    # 2019 — но в строках нет номера за 2019, поэтому добавлять не будем.
    # Просто проверим, что запрос к settings_dict вернёт 2019.
    conn = db.init_db(db_path)
    d = db.court_area_settings_dict(conn, aid, year=2019)
    check("Судья 2019", d["судья"], "Судья19")
    conn.close()

    print("\n[5] Несуществующий court_area_id -> fallback")
    res = process_rows(make_rows(), 2020, False, "word", db_path,
                       TEMPLATE, out_dir, court_area_id=99999)
    check("Fallback без СУ", "СУ" in res["filename"], False)

    print("\n[6] Метка Word ставится")
    from core.converter.markers import read_word_marker
    check("Метка есть", read_word_marker(res["path"])["found"], True)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
