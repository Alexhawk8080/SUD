# -*- coding: utf-8 -*-
"""
Smoke-тест UI конвертации (stage12d, под-этап B4).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_convert_smoke.py
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
    tmp = tempfile.mkdtemp(prefix="ui_conv_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] GET /convert_page")
    r = client.get("/convert_page")
    check("HTTP 200", r.status_code, 200)
    html = r.get_data(as_text=True)
    check("Заголовок про Excel -> Word", "Excel -> Word" in html, True)
    check("drop-zone", 'id="drop-zone"' in html, True)
    check("селект листа", 'id="conv-sheet"' in html, True)
    check("поле года", 'id="conv-year"' in html, True)
    check("селект участка", 'id="conv-court-area"' in html, True)
    check("кнопка 'convert-btn'", 'id="convert-btn"' in html, True)
    check("модалка конфликта", 'id="conflict-modal"' in html, True)
    check("3 кнопки модалки",
          all(x in html for x in ('id="conflict-replace"',
                                  'id="conflict-copy"',
                                  'id="conflict-cancel"')), True)
    check("радио Word -> Excel активно (без disabled)",
          'value="word_to_xlsx" disabled' in html, False)
    check("радио Word -> Excel присутствует",
          'value="word_to_xlsx"' in html, True)
    check("блок w2x-extra (restore-gaps)",
          'id="restore-gaps"' in html, True)
    check("карточка attention",
          'id="attention-card"' in html, True)
    check("таблица attention-table",
          'id="attention-table"' in html, True)
    check("drop-hint для смены текста",
          'id="drop-hint"' in html, True)
    check("блок реквизитов 'conv-ca-номер'",
          'id="conv-ca-номер"' in html, True)
    check("кнопка 'conv-save-area'",
          'id="conv-save-area"' in html, True)
    check("кнопка 'conv-create-area'",
          'id="conv-create-area"' in html, True)

    print("\n[2] Статика")
    r = client.get("/static/js/main.js")
    check("main.js 200", r.status_code, 200)
    js = r.get_data(as_text=True)
    check("initConvertPage", "App.initConvertPage = function" in js, True)
    check("showConflictDialog", "function showConflictDialog" in js, True)
    check("runInspect", "function runInspect" in js, True)
    check("runConvert", "function runConvert" in js, True)
    check("doConvert", "function doConvert" in js, True)
    check("вызов initConvertPage в DOMContentLoaded",
          "App.initConvertPage();" in js, True)

    r = client.get("/static/css/style.css")
    check("style.css 200", r.status_code, 200)
    check(".modal", ".modal" in r.get_data(as_text=True), True)

    print("\n[3] Страница в навигации (ссылка /convert_page)")
    r = client.get("/")
    check("На главной есть ссылка на /convert_page",
          "/convert_page" in r.get_data(as_text=True), True)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
