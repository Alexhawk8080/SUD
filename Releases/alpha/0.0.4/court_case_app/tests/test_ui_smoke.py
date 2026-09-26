# -*- coding: utf-8 -*-
"""
Smoke-тест UI (stage11e, под-этап A5).

Проверяет, что страницы отдаются и содержат ключевые элементы,
добавленные для справочника участков.

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_smoke.py
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
    tmp = tempfile.mkdtemp(prefix="ui_smoke_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] Страницы отдаются")
    r = client.get("/")
    check("GET / 200", r.status_code, 200)
    check("index: селект 'court-area'",
          'id="court-area"' in r.get_data(as_text=True), True)
    check("index: опция 'Не выбран'",
          "Не выбран" in r.get_data(as_text=True), True)

    r = client.get("/db_page")
    check("GET /db_page 200", r.status_code, 200)
    html = r.get_data(as_text=True)
    check("db: секция 'court-areas-card'", 'id="court-areas-card"' in html, True)
    check("db: таблица 'court-areas-table'",
          'id="court-areas-table"' in html, True)
    check("db: поле 'ca-номер'", 'id="ca-номер"' in html, True)
    check("db: кнопка 'court-area-add'",
          'id="court-area-add"' in html, True)

    r = client.get("/check_page")
    check("GET /check_page 200", r.status_code, 200)

    print("\n[2] Статика отдаётся")
    r = client.get("/static/js/main.js")
    check("main.js 200", r.status_code, 200)
    js = r.get_data(as_text=True)
    check("main.js: loadCourtAreas", "function loadCourtAreas" in js, True)
    check("main.js: checkRefsBeforeProcess",
          "function checkRefsBeforeProcess" in js, True)
    check("main.js: court_area_id", 'formData.append("court_area_id"' in js, True)

    r = client.get("/static/css/style.css")
    check("style.css 200", r.status_code, 200)
    check("style.css: .incomplete",
          ".incomplete" in r.get_data(as_text=True), True)

    print("\n[3] API участков работает")
    r = client.get("/api/court_areas")
    check("GET /api/court_areas 200", r.status_code, 200)
    check("Ответ — список", isinstance(r.get_json(), list), True)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
