# -*- coding: utf-8 -*-
"""
Тесты D7: обзорная сводка года, роутинг разделов, заглушка «Опись».

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_year_d7.py
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openpyxl import Workbook

from core.db_pipeline import process_year, save_year_source_from_xlsx
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


def make_source_xlsx(path, year="2020", case_type="civil"):
    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "№ дела", "Заявители", "Ответчики", "Категория",
               "№ описи", "№ ед.хр.", "Примечание", "Дата окончания"])
    if case_type == "civil":
        ws.append([datetime(int(year), 1, 10), f"2-1/{year}",
                   "Тестов Т.Т.", "Тестова Т.Т.",
                   "Исковое заявление о расторжении брака",
                   1, 1, "", datetime(int(year), 2, 10)])
        ws.append([datetime(int(year), 1, 11), f"2-2/{year}",
                   "Алимова А.А.", "Алимов А.А.",
                   "О взыскании алиментов",
                   1, 2, "", datetime(int(year), 2, 11)])
    else:
        ws.append([datetime(int(year), 1, 10), f"5-1/{year}",
                   "Гусейнов Р.А.", "",
                   "ст. 15.6 ч. 1",
                   1, 1, "", datetime(int(year), 2, 10)])
    wb.save(path)


def main():
    tmp = tempfile.mkdtemp(prefix="ui_d7_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] Роуты разделов (D7a)")
    for url in ("/db/year/1",
                "/db/year/1/refs",
                "/db/year/1/civil/files",
                "/db/year/1/civil/cases",
                "/db/year/1/civil/inventory",
                "/db/year/1/civil/process",
                "/db/year/1/civil/result",
                "/db/year/1/admin/files",
                "/db/year/1/admin/inventory"):
        r = client.get(url)
        check(f"GET {url} 200", r.status_code, 200)

    print("\n[2] Валидация URL")
    check("неверный case_type -> 404",
          client.get("/db/year/1/xxx/files").status_code, 404)
    check("неверный section -> 404",
          client.get("/db/year/1/civil/xxx").status_code, 404)
    check("только case_type без section -> 404",
          client.get("/db/year/1/civil").status_code, 404)

    print("\n[3] Заглушка «Опись» в HTML")
    r = client.get("/db/year/1/civil/inventory")
    html = r.get_data(as_text=True)
    check("раздел inventory", 'id="view-inventory"' in html, True)
    check("заметка заглушки", 'id="inventory-stub-note"' in html, True)

    print("\n[4] /api/court_years/<id>/summary — пустой год")
    r = client.post("/api/court_areas", json={"номер": "9"})
    aid = r.get_json()["id"]
    r = client.post(f"/api/court_areas/{aid}/years",
                    json={**year_data("20"), "year": 2020})
    yid = r.get_json()["id"]

    r = client.get(f"/api/court_years/{yid}/summary")
    check("HTTP 200", r.status_code, 200)
    j = r.get_json()
    check("year есть", "year" in j, True)
    check("types есть", "types" in j, True)
    check("civil в types", "civil" in j["types"], True)
    check("admin в types", "admin" in j["types"], True)
    check("civil cases_count = 0", j["types"]["civil"]["cases_count"], 0)
    check("admin cases_count = 0", j["types"]["admin"]["cases_count"], 0)
    check("civil result_id = None", j["types"]["civil"]["result_id"], None)

    print("\n[5] summary после загрузки civil-файла")
    conn = app_module.get_db()
    try:
        xlsx = os.path.join(tmp, "civil.xlsx")
        make_source_xlsx(xlsx, "2020", "civil")
        save_year_source_from_xlsx(
            conn, yid, xlsx, "civil.xlsx",
            sheet_name="Sheet", header_row=1, case_type="civil")
    finally:
        conn.close()

    r = client.get(f"/api/court_years/{yid}/summary")
    j = r.get_json()
    civil = j["types"]["civil"]
    admin = j["types"]["admin"]
    check("civil files_count = 1", civil["files_count"], 1)
    check("civil source_files_count = 1", civil["source_files_count"], 1)
    check("civil cases_count = 2", civil["cases_count"], 2)
    check("civil valid_count = 2", civil["valid_count"], 2)
    check("civil alimony_count = 1", civil["alimony_count"], 1)
    check("admin files_count = 0", admin["files_count"], 0)
    check("admin cases_count = 0", admin["cases_count"], 0)

    print("\n[6] summary после process_year (civil)")
    conn = app_module.get_db()
    try:
        result = process_year(conn, yid, case_type="civil",
                              process_alimony=True, court_area_id=aid)
    finally:
        conn.close()
    r = client.get(f"/api/court_years/{yid}/summary")
    civil = r.get_json()["types"]["civil"]
    check("civil result_id не None", civil["result_id"], result["result_id"])
    check("civil result_is_stale = False", civil["result_is_stale"], False)
    check("civil result_record_count > 0",
          civil["result_record_count"] > 0, True)

    print("\n[7] /api/db_tree — блок types (D7a)")
    r = client.get("/api/db_tree")
    y = r.get_json()["areas"][0]["years"][0]
    check("types в году", "types" in y, True)
    check("types.civil есть", "civil" in y["types"], True)
    check("types.admin есть", "admin" in y["types"], True)
    check("обратная совместимость files_count",
          y["files_count"], y["types"]["civil"]["files_count"] +
          y["types"]["admin"]["files_count"])
    check("обратная совместимость cases_count",
          y["cases_count"], y["types"]["civil"]["cases_count"] +
          y["types"]["admin"]["cases_count"])

    print("\n[8] summary для несуществующего года -> 404")
    check("404", client.get("/api/court_years/99999/summary").status_code, 404)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
