# -*- coding: utf-8 -*-
"""
Тесты сохранения исходного файла в БД (stage16d4a, D4a).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_db_pipeline_source.py
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openpyxl import Workbook

from core.db_pipeline import save_year_source_from_xlsx
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
    return {"судья": f"Судья{s}", "секретарь": f"Сек{s}",
            "дата_утверждения": "—", "дата_акта": "—",
            "номер_акта": s, "дата_подписи": "—",
            "протокол_эк_дата": "—", "протокол_эк_номер": s}


def make_source_xlsx(path, cases):
    """
    cases — список dict:
        date, case_number, applicants, respondents, category,
        opis_number, unit_number, note, end_date
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Дела"
    ws.append(["Дата", "№ дела", "Заявители", "Ответчики", "Категория",
               "№ описи", "№ ед.хр.", "Примечание", "Дата окончания"])
    for c in cases:
        ws.append([
            c.get("date"), c.get("case_number"),
            c.get("applicants"), c.get("respondents"),
            c.get("category"),
            c.get("opis_number"), c.get("unit_number"),
            c.get("note"), c.get("end_date"),
        ])
    wb.save(path)


def main():
    tmp = tempfile.mkdtemp(prefix="db_pipe_a_")
    db_path = os.path.join(tmp, "app.db")
    conn = db.init_db(db_path)
    aid = db.add_court_area(conn, {"номер": "9"})
    yid = db.add_court_year(conn, aid, 2020, year_data("20"))

    xlsx = os.path.join(tmp, "источник.xlsx")
    make_source_xlsx(xlsx, [
        {   # валидное дело
            "date": datetime(2020, 1, 10),
            "case_number": "2-1/2020",
            "applicants": "Тестов Тест Тестович",
            "respondents": "Тестова Теста Тестовна",
            "category": "Исковое заявление о расторжении брака",
            "opis_number": 1, "unit_number": 1, "note": "",
            "end_date": datetime(2020, 2, 10),
        },
        {   # алиментное
            "date": datetime(2020, 1, 11),
            "case_number": "2-2/2020",
            "applicants": "Иванова Ирина Ивановна",
            "respondents": "Иванов Иван Иванович",
            "category": "О взыскании алиментов",
            "opis_number": 1, "unit_number": 2, "note": "",
            "end_date": datetime(2020, 2, 11),
        },
        {   # проблемная категория (пустая)
            "date": datetime(2020, 1, 12),
            "case_number": "2-3/2020",
            "applicants": "Петров Пётр Петрович",
            "respondents": "ООО Ромашка",
            "category": "",
            "opis_number": 1, "unit_number": 3, "note": "разобрать",
            "end_date": datetime(2020, 2, 12),
        },
        {   # неверный год
            "date": datetime(2020, 1, 13),
            "case_number": "2-4/2019",
            "applicants": "Сидоров С.С.",
            "respondents": "Петров П.П.",
            "category": "О защите прав потребителей",
            "opis_number": 1, "unit_number": 4, "note": "",
            "end_date": datetime(2020, 2, 13),
        },
    ])

    print("[1] save_year_source_from_xlsx: базовая проверка")
    result = save_year_source_from_xlsx(
        conn, yid, xlsx, "источник.xlsx",
        sheet_name="Дела", header_row=1)
    check("source_file_id > 0", result["source_file_id"] > 0, True)
    check("row_count = 4", result["row_count"], 4)
    check("valid_count = 3 (год 2020)", result["valid_count"], 3)
    check("alimony_count = 1", result["alimony_count"], 1)
    check("problematic_count = 1 (пустая категория)", result["problematic_count"], 1)
    check("mapping непустой", bool(result["mapping"]), True)

    print("\n[2] Запись source_files создана")
    sf = db.get_source_file(conn, result["source_file_id"])
    check("filename", sf["filename"], "источник.xlsx")
    check("file_kind", sf["file_kind"], "source")
    check("version = 1", sf["version"], 1)
    check("is_current = True", sf["is_current"], True)
    check("row_count = 4", sf["row_count"], 4)
    check("sheet_name = 'Дела'", sf["sheet_name"], "Дела")
    check("header_row = 1", sf["header_row"], 1)
    # В mapping роли называются как в excel_reader: date, case_number, ...
    check("mapping хранится (case_number)",
          "case_number" in sf["mapping"], True)
    check("mapping содержит date",
          "date" in sf["mapping"], True)

    print("\n[3] BLOB сохранён")
    blob = db.get_source_file_content(conn, result["source_file_id"])
    check("BLOB не пустой", len(blob) > 0, True)
    check("BLOB = исходный файл",
          blob, open(xlsx, "rb").read())

    print("\n[4] Дела сохранены")
    cases = db.list_cases(conn, source_file_id=result["source_file_id"])
    check("4 дела", len(cases), 4)
    c1 = cases[0]
    check("case_number", c1["case_number"], "2-1/2020")
    check("date = '10.01.2020'", c1["date"], "10.01.2020")
    check("end_date = '10.02.2020'", c1["end_date"], "10.02.2020")
    check("is_valid = True", c1["is_valid"], True)
    check("is_alimony = False", c1["is_alimony"], False)
    check("is_problematic = False", c1["is_problematic"], False)
    check("skip_reason пустой", c1["skip_reason"], "")
    check("case_type = 'civil'", c1["case_type"], "civil")

    print("\n[5] Алиментное дело помечено")
    alim = [c for c in cases if c["case_number"] == "2-2/2020"][0]
    check("is_alimony = True", alim["is_alimony"], True)
    check("skip_reason про алименты", "алимент" in alim["skip_reason"], True)
    check("is_valid = True (номер валиден)", alim["is_valid"], True)

    print("\n[6] Проблемная категория")
    prob = [c for c in cases if c["case_number"] == "2-3/2020"][0]
    check("is_problematic = True", prob["is_problematic"], True)
    check("note = 'разобрать'", prob["note"], "разобрать")

    print("\n[7] Неверный год помечен")
    bad = [c for c in cases if c["case_number"] == "2-4/2019"][0]
    check("is_valid = False", bad["is_valid"], False)
    check("skip_reason непустой", bool(bad["skip_reason"]), True)

    print("\n[8] Вторая версия файла")
    xlsx2 = os.path.join(tmp, "источник2.xlsx")
    make_source_xlsx(xlsx2, [
        {"date": datetime(2020, 3, 1), "case_number": "2-5/2020",
         "applicants": "X", "respondents": "Y",
         "category": "О защите прав потребителей",
         "opis_number": 1, "unit_number": 5, "note": "",
         "end_date": None},
    ])
    result2 = save_year_source_from_xlsx(
        conn, yid, xlsx2, "источник2.xlsx", header_row=1)
    sf2 = db.get_source_file(conn, result2["source_file_id"])
    check("version = 2", sf2["version"], 2)
    check("v2 is_current", sf2["is_current"], True)
    check("v1 больше не current",
          db.get_source_file(conn, result["source_file_id"])["is_current"],
          False)
    # Проверяем: дела обеих версий в БД (историю не удаляем)
    check("Всего source_files = 2",
          db.count_source_files(conn, yid), 2)

    print("\n[9] Валидация")
    try:
        save_year_source_from_xlsx(conn, 99999, xlsx, "x.xlsx")
        check("Несуществующий год -> ValueError", "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий год -> ValueError", True, True)

    try:
        save_year_source_from_xlsx(conn, yid, os.path.join(tmp, "нет.xlsx"),
                                   "нет.xlsx")
        check("Несуществующий файл -> ValueError", "нет ошибки", "ValueError")
    except ValueError:
        check("Несуществующий файл -> ValueError", True, True)

    print("\n[10] Пустой файл (только заголовки)")
    xlsx3 = os.path.join(tmp, "пусто.xlsx")
    make_source_xlsx(xlsx3, [])
    r3 = save_year_source_from_xlsx(conn, yid, xlsx3, "пусто.xlsx",
                                     header_row=1)
    check("row_count = 0", r3["row_count"], 0)
    check("source_file создан", r3["source_file_id"] > 0, True)

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
