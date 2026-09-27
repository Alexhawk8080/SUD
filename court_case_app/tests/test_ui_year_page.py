# -*- coding: utf-8 -*-
"""
Smoke-тест страницы года (D7: обзорная сводка + разделы).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_year_page.py
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
    tmp = tempfile.mkdtemp(prefix="ui_year_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] GET /db/year/1")
    r = client.get("/db/year/1")
    check("HTTP 200", r.status_code, 200)
    html = r.get_data(as_text=True)
    check("year_page.css подключён",
          "css/year_page.css" in html, True)
    check("year_page.js подключён",
          "js/year_page.js" in html, True)
    check("YEAR_ID = 1", "window.YEAR_ID = 1" in html, True)
    check("обзорная сводка", 'id="view-overview"' in html, True)
    check("раздел refs", 'id="view-refs"' in html, True)
    check("раздел files", 'id="view-files"' in html, True)
    check("раздел cases", 'id="view-cases"' in html, True)
    check("раздел inventory", 'id="view-inventory"' in html, True)
    check("раздел process", 'id="view-process"' in html, True)
    check("раздел result", 'id="view-result"' in html, True)
    check("сетка сводки", 'id="overview-grid"' in html, True)
    check("хлебные крошки", 'id="year-breadcrumb"' in html, True)
    check("форма refs", 'id="refs-form"' in html, True)
    check("поле судья", 'id="ref-судья"' in html, True)
    check("поле секретарь", 'id="ref-секретарь"' in html, True)
    check("поле note", 'id="ref-note"' in html, True)
    check("is_closed", 'id="ref-is_closed"' in html, True)
    check("кнопка unlock", 'id="refs-unlock"' in html, True)
    check("флаг incomplete", 'id="flag-incomplete"' in html, True)
    check("флаг closed", 'id="flag-closed"' in html, True)
    check("sidebar присутствует", 'id="db-sidebar"' in html, True)

    print("\n[1b] Роуты разделов (D7)")
    for url in ("/db/year/1/refs",
                "/db/year/1/civil/files",
                "/db/year/1/civil/cases",
                "/db/year/1/civil/inventory",
                "/db/year/1/civil/process",
                "/db/year/1/civil/result",
                "/db/year/1/admin/files"):
        r = client.get(url)
        check(f"GET {url} 200", r.status_code, 200)
    check("неверный case_type -> 404",
          client.get("/db/year/1/xxx/files").status_code, 404)
    check("неверный section -> 404",
          client.get("/db/year/1/civil/xxx").status_code, 404)

    print("\n[2] Статика")
    r = client.get("/static/css/year_page.css")
    check("year_page.css 200", r.status_code, 200)
    css = r.get_data(as_text=True)
    check(".summary-grid в css", ".summary-grid" in css, True)
    check(".breadcrumb в css", ".breadcrumb" in css, True)
    check(".year-header", ".year-header" in css, True)

    r = client.get("/static/js/year_page.js")
    check("year_page.js 200", r.status_code, 200)
    js = r.get_data(as_text=True)
    check("parseRoute", "function parseRoute" in js, True)
    check("renderRoute", "function renderRoute" in js, True)
    check("loadOverview", "function loadOverview" in js, True)
    check("loadYear", "function loadYear" in js, True)
    check("saveRefs", "function saveRefs" in js, True)
    check("unlockYear", "function unlockYear" in js, True)
    check("pushState", "pushState" in js, True)

    print("\n[3] Жизненный цикл года: создать + GET")
    r = client.post("/api/court_areas", json={"номер": "9"})
    aid = r.get_json()["id"]
    r = client.post(f"/api/court_areas/{aid}/years", json={
        "year": 2020, "судья": "Судья", "секретарь": "Сек",
        "номер_акта": "1", "дата_утверждения": "—",
        "дата_акта": "—", "дата_подписи": "—",
        "протокол_эк_дата": "—", "протокол_эк_номер": "1",
    })
    yid = r.get_json()["id"]
    r = client.get("/db/year/" + str(yid))
    check("HTTP 200 для реального года", r.status_code, 200)
    check("YEAR_ID отражён", f"window.YEAR_ID = {yid}" in r.get_data(as_text=True), True)

    r = client.get(f"/api/court_years/{yid}")
    j = r.get_json()
    check("судья", j["судья"], "Судья")
    check("is_closed = False", j["is_closed"], False)

    print("\n[4] PUT /api/court_years/<id> — изменение реквизитов")
    r = client.put(f"/api/court_years/{yid}", json={
        "судья": "Новый Судья", "секретарь": "Новый Сек",
        "номер_акта": "2", "дата_утверждения": "—",
        "дата_акта": "—", "дата_подписи": "—",
        "протокол_эк_дата": "—", "протокол_эк_номер": "2",
    })
    check("HTTP 200", r.status_code, 200)
    j = client.get(f"/api/court_years/{yid}").get_json()
    check("судья обновлён", j["судья"], "Новый Судья")

    print("\n[5] is_closed toggle")
    r = client.put(f"/api/court_years/{yid}", json={
        "судья": "Новый Судья", "секретарь": "Новый Сек",
        "номер_акта": "2", "дата_утверждения": "—",
        "дата_акта": "—", "дата_подписи": "—",
        "протокол_эк_дата": "—", "протокол_эк_номер": "2",
        "is_closed": True,
    })
    check("HTTP 200", r.status_code, 200)
    j = client.get(f"/api/court_years/{yid}").get_json()
    check("is_closed = True", j["is_closed"], True)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
