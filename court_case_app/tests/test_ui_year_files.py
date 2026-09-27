# -*- coding: utf-8 -*-
"""
Smoke-тест раздела «Файлы» на странице года (D7d).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_year_files.py
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
    tmp = tempfile.mkdtemp(prefix="ui_files_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] Элементы раздела «Файлы» в HTML")
    r = client.get("/db/year/1/civil/files")
    check("HTTP 200", r.status_code, 200)
    html = r.get_data(as_text=True)
    check("drop-zone", 'id="files-drop-zone"' in html, True)
    check("file-input", 'id="files-file-input"' in html, True)
    check("kind", 'id="files-kind"' in html, True)
    check("нет селекта case-type (D7)",
          'id="files-case-type"' in html, False)
    check("header-row", 'id="files-header-row"' in html, True)
    check("upload-btn", 'id="files-upload-btn"' in html, True)
    check("files-table", 'id="files-table"' in html, True)
    check("filter all", 'name="files-filter" value="all"' in html, True)
    check("filter source", 'name="files-filter" value="source"' in html, True)
    check("filter processed", 'name="files-filter" value="processed"' in html, True)
    check("files-empty", 'id="files-empty"' in html, True)

    print("\n[2] Статика: JS содержит функции раздела")
    r = client.get("/static/js/year_page.js")
    check("200", r.status_code, 200)
    js = r.get_data(as_text=True)
    check("initFilesTab", "function initFilesTab" in js, True)
    check("loadFiles", "function loadFiles" in js, True)
    check("renderFiles", "function renderFiles" in js, True)
    check("uploadFile", "function uploadFile" in js, True)
    check("setCurrentFile", "function setCurrentFile" in js, True)
    check("deleteFile", "function deleteFile" in js, True)
    check("блокировка по _yearClosed", "window._yearClosed" in js, True)
    check("reload tree после загрузки", "refreshDbTree" in js, True)
    check("case_type из URL (currentCaseType)",
          "currentCaseType" in js, True)

    print("\n[3] Статика: CSS таба «Файлы»")
    r = client.get("/static/css/year_page.css")
    check("200", r.status_code, 200)
    css = r.get_data(as_text=True)
    check("#files-table", "#files-table" in css, True)
    check("#files-empty", "#files-empty" in css, True)

    print("\n[4] Жизненный цикл: загрузка файла через API")
    r = client.post("/api/court_areas", json={"номер": "9"})
    aid = r.get_json()["id"]
    r = client.post(f"/api/court_areas/{aid}/years", json={
        "year": 2020, "судья": "Судья", "секретарь": "Сек",
        "номер_акта": "1", "дата_утверждения": "—",
        "дата_акта": "—", "дата_подписи": "—",
        "протокол_эк_дата": "—", "протокол_эк_номер": "1",
    })
    yid = r.get_json()["id"]

    # Страница года 200
    r = client.get(f"/db/year/{yid}")
    check("GET /db/year/<реальный id>", r.status_code, 200)

    # Загружаем файл через API (без UI, чтобы не городить multipart в
    # браузер-стиле — оно уже покрыто D5b)
    from io import BytesIO
    from datetime import datetime
    from openpyxl import Workbook
    xlsx_io = BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "№ дела", "Заявители", "Ответчики", "Категория",
               "№ описи", "№ ед.хр.", "Примечание", "Дата окончания"])
    ws.append([datetime(2020, 1, 10), "2-1/2020",
               "Тестов Т.Т.", "Тестова Т.Т.",
               "Исковое заявление о расторжении брака",
               1, 1, "", datetime(2020, 2, 10)])
    wb.save(xlsx_io)
    xlsx_io.seek(0)
    r = client.post(f"/api/court_years/{yid}/source_files",
                    data={"file": (xlsx_io, "источник.xlsx"),
                          "header_row": "1"},
                    content_type="multipart/form-data")
    check("Загрузка через API", r.status_code, 200)
    sfid = r.get_json()["source_file_id"]

    # Проверим что в списке есть
    r = client.get(f"/api/court_years/{yid}/source_files")
    files = r.get_json()
    check("1 файл в списке", len(files), 1)
    check("is_current = True", files[0]["is_current"], True)
    check("filename", files[0]["filename"], "источник.xlsx")

    # BLOB доступен
    r = client.get(f"/api/source_files/{sfid}/content")
    check("BLOB 200", r.status_code, 200)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
