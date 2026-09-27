# -*- coding: utf-8 -*-
"""
Smoke-тест разделов «Обработка» и «Результат» (D7d).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_year_process_result.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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


def main():
    tmp = tempfile.mkdtemp(prefix="ui_pr_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] Элементы раздела «Обработка»")
    r = client.get("/db/year/1/civil/process")
    check("HTTP 200", r.status_code, 200)
    html = r.get_data(as_text=True)
    check("process-source", 'id="process-source"' in html, True)
    check("нет селекта process-type (D7)",
          'id="process-type"' in html, False)
    check("process-alimony", 'id="process-alimony"' in html, True)
    check("process-autofix", 'id="process-autofix"' in html, True)
    check("process-btn", 'id="process-btn"' in html, True)
    check("process-error", 'id="process-error"' in html, True)
    check("process-ok", 'id="process-ok"' in html, True)

    print("\n[2] Элементы раздела «Результат»")
    check("нет селекта result-type (D7)",
          'id="result-type"' in html, False)
    check("result-reload", 'id="result-reload"' in html, True)
    check("result-dl-word", 'id="result-dl-word"' in html, True)
    check("result-dl-excel", 'id="result-dl-excel"' in html, True)
    check("result-delete", 'id="result-delete"' in html, True)
    check("result-table", 'id="result-table"' in html, True)
    check("result-info", 'id="result-info"' in html, True)
    check("result-empty", 'id="result-empty"' in html, True)

    print("\n[3] JS содержит функции табов")
    r = client.get("/static/js/year_page.js")
    check("200", r.status_code, 200)
    js = r.get_data(as_text=True)
    check("initProcessTab", "function initProcessTab" in js, True)
    check("runProcess", "function runProcess" in js, True)
    check("loadSourcesIntoProcess", "function loadSourcesIntoProcess" in js, True)
    check("initResultTab", "function initResultTab" in js, True)
    check("loadResult", "function loadResult" in js, True)
    check("renderResult", "function renderResult" in js, True)
    check("exportResult", "function exportResult" in js, True)
    check("deleteResult", "function deleteResult" in js, True)
    check("is_stale в info", "is_stale" in js, True)

    print("\n[4] CSS табов")
    r = client.get("/static/css/year_page.css")
    css = r.get_data(as_text=True)
    check("result-table", "#result-table" in css, True)
    check("process-error", "#process-error" in css, True)

    print("\n[5] Полный цикл через API")
    r = client.post("/api/court_areas", json={"номер": "9"})
    aid = r.get_json()["id"]
    r = client.post(f"/api/court_areas/{aid}/years", json={
        "year": 2020, "судья": "Судья", "секретарь": "Сек",
        "номер_акта": "1", "дата_утверждения": "—",
        "дата_акта": "—", "дата_подписи": "—",
        "протокол_эк_дата": "—", "протокол_эк_номер": "1",
    })
    yid = r.get_json()["id"]

    from io import BytesIO
    from datetime import datetime
    from openpyxl import Workbook
    buf = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "№ дела", "Заявители", "Ответчики", "Категория",
               "№ описи", "№ ед.хр.", "Примечание", "Дата окончания"])
    ws.append([datetime(2020, 1, 10), "2-1/2020",
               "Тестов Т.Т.", "Тестова Т.Т.",
               "Исковое заявление о расторжении брака",
               1, 1, "", datetime(2020, 2, 10)])
    wb.save(buf)
    buf.seek(0)
    client.post(f"/api/court_years/{yid}/source_files",
                data={"file": (buf, "источник.xlsx"), "header_row": "1"},
                content_type="multipart/form-data")

    r = client.post(f"/api/court_years/{yid}/process",
                    json={"case_type": "civil"})
    check("process 200", r.status_code, 200)
    rid = r.get_json()["result_id"]

    r = client.get(f"/api/court_years/{yid}/results")
    check("results — 1", len(r.get_json()), 1)

    r = client.get(f"/api/results/{rid}")
    j = r.get_json()
    check("rows есть", "rows" in j, True)
    check("1 строка", len(j["rows"]), 1)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
