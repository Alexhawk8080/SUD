# -*- coding: utf-8 -*-
"""
Smoke-тест создания участка и года из сайдбара (stage16d6f, D6f).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_sidebar_create.py
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
    tmp = tempfile.mkdtemp(prefix="ui_sb_create_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] HTML сайдбара содержит элементы создания")
    r = client.get("/")
    check("HTTP 200", r.status_code, 200)
    html = r.get_data(as_text=True)
    check("btn + Участок",
          'id="sidebar-add-area"' in html, True)
    check("модалка",
          'id="sidebar-modal"' in html, True)
    check("заголовок модалки",
          'id="sidebar-modal-title"' in html, True)
    check("тело модалки",
          'id="sidebar-modal-body"' in html, True)
    check("кнопка OK",
          'id="sidebar-modal-ok"' in html, True)
    check("кнопка Cancel",
          'id="sidebar-modal-cancel"' in html, True)
    check("error-box модалки",
          'id="sidebar-modal-error"' in html, True)

    print("\n[2] JS содержит функции создания")
    r = client.get("/static/js/db_tree.js")
    check("200", r.status_code, 200)
    js = r.get_data(as_text=True)
    check("openAreaModal", "function openAreaModal" in js, True)
    check("openYearModal", "function openYearModal" in js, True)
    check("submitArea", "function submitArea" in js, True)
    check("submitYear", "function submitYear" in js, True)
    check("closeModal", "function closeModal" in js, True)
    check("POST /api/court_areas", "/api/court_areas" in js, True)
    check("POST /api/court_areas/<id>/years",
          "/years" in js, True)
    check("POST /copy_refs", "/copy_refs" in js, True)
    check("кнопка data-area-add", "data-area-add" in js, True)

    print("\n[3] CSS: стили модалки и кнопки «+»")
    r = client.get("/static/css/sidebar.css")
    check("200", r.status_code, 200)
    css = r.get_data(as_text=True)
    check(".tree-area-add", ".tree-area-add" in css, True)
    check(".sidebar-action-btn", ".sidebar-action-btn" in css, True)
    check(".modal-sm", ".modal-sm" in css, True)

    print("\n[4] Полный цикл через API (что делает UI)")
    # 1. Создаём участок
    r = client.post("/api/court_areas", json={"номер": "9"})
    check("участок создан", r.status_code, 200)
    aid = r.get_json()["id"]

    # 2. Создаём год 2019 с реквизитами
    r = client.post(f"/api/court_areas/{aid}/years", json={
        "year": 2019, "судья": "Судья 2019", "секретарь": "Сек 2019",
        "номер_акта": "1", "дата_утверждения": "—",
        "дата_акта": "—", "дата_подписи": "—",
        "протокол_эк_дата": "—", "протокол_эк_номер": "1"
    })
    check("год 2019 создан", r.status_code, 200)
    yid1 = r.get_json()["id"]

    # 3. Создаём год 2020 пустым, потом copy_refs из 2019
    r = client.post(f"/api/court_areas/{aid}/years", json={
        "year": 2020, "судья": "", "секретарь": "",
        "номер_акта": "", "дата_утверждения": "",
        "дата_акта": "", "дата_подписи": "",
        "протокол_эк_дата": "", "протокол_эк_номер": ""
    })
    check("год 2020 создан", r.status_code, 200)
    yid2 = r.get_json()["id"]

    r = client.post(f"/api/court_areas/{aid}/copy_refs", json={
        "from_year": 2019, "to_year": 2020})
    check("copy_refs 200", r.status_code, 200)

    r = client.get(f"/api/court_years/{yid2}")
    j = r.get_json()
    check("судья скопирован", j["судья"], "Судья 2019")
    check("секретарь скопирован", j["секретарь"], "Сек 2019")

    print("\n[5] /api/db_tree показывает оба года")
    r = client.get("/api/db_tree")
    j = r.get_json()
    check("1 участок", len(j["areas"]), 1)
    check("2 года", j["areas"][0]["years_count"], 2)
    years = sorted(y["year"] for y in j["areas"][0]["years"])
    check("годы 2019, 2020", years, [2019, 2020])

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
