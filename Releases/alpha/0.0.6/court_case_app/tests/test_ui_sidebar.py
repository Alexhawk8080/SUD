# -*- coding: utf-8 -*-
"""
Smoke-тест сайдбара (stage16d6a, D6a).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_sidebar.py
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
    tmp = tempfile.mkdtemp(prefix="ui_sidebar_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] Сайдбар на главных страницах")
    for url in ("/", "/check_page", "/db_page", "/convert_page"):
        r = client.get(url)
        check(f"GET {url} 200", r.status_code, 200)
        html = r.get_data(as_text=True)
        check(f"{url}: sidebar присутствует",
              'id="db-sidebar"' in html, True)
        check(f"{url}: sidebar.css подключён",
              "css/sidebar.css" in html, True)
        check(f"{url}: db_tree.js подключён",
              "js/db_tree.js" in html, True)

    print("\n[2] Страница года-заглушки")
    r = client.get("/db/year/1")
    check("HTTP 200", r.status_code, 200)
    html = r.get_data(as_text=True)
    check("sidebar присутствует", 'id="db-sidebar"' in html, True)
    # D6b: year.html использует динамический заголовок через JS
    check("YEAR_ID = 1 в HTML",
          "window.YEAR_ID = 1" in html, True)
    check("элемент #year-title",
          'id="year-title"' in html, True)
    check("табы года присутствуют",
          'id="year-tabs"' in html, True)
    check("year.html подключён db_tree.js",
          "js/db_tree.js" in html, True)

    print("\n[3] Статика отдаётся")
    r = client.get("/static/css/sidebar.css")
    check("sidebar.css 200", r.status_code, 200)
    css = r.get_data(as_text=True)
    check(".sidebar", ".sidebar" in css, True)
    check(".tree-area-row", ".tree-area-row" in css, True)

    r = client.get("/static/js/db_tree.js")
    check("db_tree.js 200", r.status_code, 200)
    js = r.get_data(as_text=True)
    check("loadTree", "function loadTree" in js, True)
    check("renderTree", "function renderTree" in js, True)
    check("переход на /db/year/", "/db/year/" in js, True)

    print("\n[4] /api/db_tree работает")
    r = client.get("/api/db_tree")
    check("HTTP 200", r.status_code, 200)
    j = r.get_json()
    check("areas ключ", "areas" in j, True)
    check("total_areas", j.get("total_areas"), 0)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
