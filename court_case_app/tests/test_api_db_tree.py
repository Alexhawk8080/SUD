# -*- coding: utf-8 -*-
"""
Тесты API /api/db_tree (stage16d5a, D5a).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_api_db_tree.py
"""

import io
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openpyxl import Workbook

from core.db_pipeline import (
    process_year,
    save_year_source_from_xlsx,
)
import app as app_module

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


def make_source_xlsx(path, year="2020"):
    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "№ дела", "Заявители", "Ответчики", "Категория",
               "№ описи", "№ ед.хр.", "Примечание", "Дата окончания"])
    ws.append([datetime(int(year), 1, 10), f"2-1/{year}",
               "Тестов Т.Т.", "Тестова Т.Т.",
               "Исковое заявление о расторжении брака",
               1, 1, "", datetime(int(year), 2, 10)])
    ws.append([datetime(int(year), 1, 11), f"2-2/{year}",
               "Иванов И.И.", "Иванова И.И.",
               "Исковое заявление о защите прав потребителей",
               1, 2, "", datetime(int(year), 2, 11)])
    wb.save(path)


def main():
    tmp = tempfile.mkdtemp(prefix="api_tree_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] Пустое дерево")
    r = client.get("/api/db_tree")
    check("HTTP 200", r.status_code, 200)
    j = r.get_json()
    check("areas = []", j.get("areas"), [])
    check("total_areas = 0", j.get("total_areas"), 0)

    print("\n[2] Участок без годов")
    r = client.post("/api/court_areas", json={"номер": "9"})
    area_id = r.get_json()["id"]
    r = client.get("/api/db_tree")
    j = r.get_json()
    check("1 участок", len(j["areas"]), 1)
    check("участок 9", j["areas"][0]["номер"], "9")
    check("0 годов", j["areas"][0]["years_count"], 0)

    print("\n[3] Участок с годом (пустой)")
    r = client.post(f"/api/court_areas/{area_id}/years",
                    json={**year_data("20"), "year": 2020})
    check("HTTP 200", r.status_code, 200)
    year_id = r.get_json()["id"]
    r = client.get("/api/db_tree")
    y = r.get_json()["areas"][0]["years"][0]
    check("year = 2020", y["year"], 2020)
    check("files_count = 0", y["files_count"], 0)
    check("cases_count = 0", y["cases_count"], 0)
    check("result_id = None", y["result_id"], None)
    check("is_closed = False", y["is_closed"], False)
    check("is_incomplete = False", y["is_incomplete"], False)

    print("\n[4] Загрузка источника через API-less путь")
    conn = app_module.get_db()
    try:
        xlsx = os.path.join(tmp, "источник.xlsx")
        make_source_xlsx(xlsx, "2020")
        save_year_source_from_xlsx(
            conn, year_id, xlsx, "источник.xlsx",
            sheet_name="Sheet", header_row=1)
    finally:
        conn.close()

    r = client.get("/api/db_tree")
    y = r.get_json()["areas"][0]["years"][0]
    check("files_count = 1", y["files_count"], 1)
    check("cases_count = 2", y["cases_count"], 2)

    print("\n[5] После process_year")
    conn = app_module.get_db()
    try:
        result = process_year(conn, year_id, case_type="civil",
                              process_alimony=True, court_area_id=area_id)
    finally:
        conn.close()
    r = client.get("/api/db_tree")
    y = r.get_json()["areas"][0]["years"][0]
    check("result_id не None", y["result_id"], result["result_id"])
    check("result_is_stale = False", y["result_is_stale"], False)

    print("\n[6] is_stale после повторной загрузки файла")
    # Загружаем v2 — результат становится «устаревшим» только по кнопке,
    # но is_stale меняется только при process_year на неактуальном файле.
    # Здесь проверяем базовую связь.
    conn = app_module.get_db()
    try:
        xlsx2 = os.path.join(tmp, "источник2.xlsx")
        make_source_xlsx(xlsx2, "2020")
        save_year_source_from_xlsx(
            conn, year_id, xlsx2, "источник2.xlsx",
            sheet_name="Sheet", header_row=1)
    finally:
        conn.close()
    r = client.get("/api/db_tree")
    y = r.get_json()["areas"][0]["years"][0]
    check("files_count = 2 (v1+v2)", y["files_count"], 2)
    check("cases_count = 4 (2+2)", y["cases_count"], 4)

    print("\n[7] Несколько участков и годов — сортировка")
    r = client.post("/api/court_areas", json={"номер": "5"})
    a5 = r.get_json()["id"]
    client.post(f"/api/court_areas/{a5}/years",
                json={**year_data("19"), "year": 2019})
    r = client.get("/api/db_tree")
    j = r.get_json()
    check("2 участка", len(j["areas"]), 2)
    check("первый — 5", j["areas"][0]["номер"], "5")
    check("второй — 9", j["areas"][1]["номер"], "9")
    check("у 9 — 1 год", j["areas"][1]["years_count"], 1)

    print("\n[8] is_closed / is_incomplete в дереве")
    # Обновляем год 2020 → is_closed = True
    client.put(f"/api/court_years/{year_id}",
               json={**year_data("20"), "year": 2020, "is_closed": True})
    r = client.get("/api/db_tree")
    # Найдём год 2020 у участка 9
    year_2020 = [y for y in r.get_json()["areas"][1]["years"]
                 if y["year"] == 2020][0]
    check("is_closed = True", year_2020["is_closed"], True)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
