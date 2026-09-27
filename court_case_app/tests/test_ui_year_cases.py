# -*- coding: utf-8 -*-
"""
Smoke-тест раздела «Дела» на странице года (D7d).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_year_cases.py
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
    tmp = tempfile.mkdtemp(prefix="ui_cases_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] Элементы раздела «Дела» в HTML")
    r = client.get("/db/year/1/civil/cases")
    check("HTTP 200", r.status_code, 200)
    html = r.get_data(as_text=True)
    check("селект cases-source",
          'id="cases-source"' in html, True)
    check("нет селекта cases-type (D7)",
          'id="cases-type"' in html, False)
    check("чекбокс only-valid",
          'id="cases-only-valid"' in html, True)
    check("чекбокс only-problematic",
          'id="cases-only-problematic"' in html, True)
    check("чекбокс only-alimony",
          'id="cases-only-alimony"' in html, True)
    check("cases-table", 'id="cases-table"' in html, True)
    check("cases-info", 'id="cases-info"' in html, True)
    check("cases-error", 'id="cases-error"' in html, True)
    check("cases-empty", 'id="cases-empty"' in html, True)
    # 10 столбцов
    check("заголовок «№ дела»", "№ дела" in html, True)
    check("заголовок «Истец»", "Истец" in html, True)
    check("заголовок «Ответчик»", "Ответчик" in html, True)
    check("заголовок «Статус»", "Статус" in html, True)

    print("\n[2] JS содержит функции таба")
    r = client.get("/static/js/year_page.js")
    check("200", r.status_code, 200)
    js = r.get_data(as_text=True)
    check("initCasesTab", "function initCasesTab" in js, True)
    check("loadCases", "function loadCases" in js, True)
    check("renderCases", "function renderCases" in js, True)
    check("loadSourcesIntoSelect", "function loadSourcesIntoSelect" in js, True)
    check("is_alimony фильтр", "cases-only-alimony" in js, True)
    check("is_problematic фильтр", "cases-only-problematic" in js, True)
    check("is_valid фильтр", "cases-only-valid" in js, True)

    print("\n[3] CSS таба «Дела»")
    r = client.get("/static/css/year_page.css")
    check("200", r.status_code, 200)
    css = r.get_data(as_text=True)
    check("#cases-table", "#cases-table" in css, True)
    check("#cases-empty", "#cases-empty" in css, True)

    print("\n[4] API и данные")
    # Создаём участок + год + файл + дела
    r = client.post("/api/court_areas", json={"номер": "9"})
    aid = r.get_json()["id"]
    r = client.post(f"/api/court_areas/{aid}/years", json={
        "year": 2020, "судья": "Судья", "секретарь": "Сек",
        "номер_акта": "1", "дата_утверждения": "—",
        "дата_акта": "—", "дата_подписи": "—",
        "протокол_эк_дата": "—", "протокол_эк_номер": "1",
    })
    yid = r.get_json()["id"]

    # Загружаем файл через API D5b (multipart)
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
    ws.append([datetime(2020, 1, 11), "2-2/2020",
               "Алимова А.А.", "Алимов А.А.",
               "О взыскании алиментов",
               1, 2, "", datetime(2020, 2, 11)])
    ws.append([datetime(2020, 1, 12), "2-3/2020",
               "Петров П.П.", "Петрова П.П.",
               "",
               1, 3, "пустая категория", datetime(2020, 2, 12)])
    wb.save(buf)
    buf.seek(0)
    r = client.post(f"/api/court_years/{yid}/source_files",
                    data={"file": (buf, "источник.xlsx"),
                          "header_row": "1"},
                    content_type="multipart/form-data")
    check("загрузка файла 200", r.status_code, 200)
    sfid = r.get_json()["source_file_id"]

    # Список файлов
    r = client.get(f"/api/court_years/{yid}/source_files")
    files = r.get_json()
    check("1 файл", len(files), 1)
    check("is_current=True", files[0]["is_current"], True)

    # Дела
    r = client.get(f"/api/source_files/{sfid}/cases?case_type=civil")
    cases = r.get_json()
    check("3 дела civil", len(cases), 3)
    check("2-1 валидное", cases[0]["is_valid"], True)
    check("2-2 алиментное", cases[1]["is_alimony"], True)
    check("2-3 проблемное", cases[2]["is_problematic"], True)

    # Проверим пустой admin
    r = client.get(f"/api/source_files/{sfid}/cases?case_type=admin")
    check("admin — пусто", r.get_json(), [])

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
