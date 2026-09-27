# -*- coding: utf-8 -*-
"""
Тесты API source_files и cases (stage16d5b, D5b).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_api_files_cases.py
"""

import io
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openpyxl import Workbook

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


def make_xlsx(path, n=2, year=2020):
    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "№ дела", "Заявители", "Ответчики", "Категория",
               "№ описи", "№ ед.хр.", "Примечание", "Дата окончания"])
    for i in range(n):
        ws.append([datetime(year, 1, 10 + i), f"2-{i+1}/{year}",
                   f"Истец {i+1}", f"Ответчик {i+1}",
                   "Исковое заявление о расторжении брака",
                   1, i + 1, "", datetime(year, 2, 10 + i)])
    wb.save(path)


def main():
    tmp = tempfile.mkdtemp(prefix="api_files_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    # Подготовка
    r = client.post("/api/court_areas", json={"номер": "9"})
    area_id = r.get_json()["id"]
    r = client.post(f"/api/court_areas/{area_id}/years",
                    json={**year_data("20"), "year": 2020})
    year_id = r.get_json()["id"]

    print("[1] Пустой список файлов")
    r = client.get(f"/api/court_years/{year_id}/source_files")
    check("HTTP 200", r.status_code, 200)
    check("[]", r.get_json(), [])

    print("\n[2] Загрузка файла через POST")
    xlsx = os.path.join(tmp, "источник.xlsx")
    make_xlsx(xlsx, n=3)
    with open(xlsx, "rb") as f:
        data = {
            "file": (io.BytesIO(f.read()), "источник.xlsx"),
            "file_kind": "source",
            "case_type": "civil",
            "header_row": "1",
        }
        r = client.post(f"/api/court_years/{year_id}/source_files",
                        data=data, content_type="multipart/form-data")
    check("HTTP 200", r.status_code, 200)
    j = r.get_json()
    check("ok = True", j.get("ok"), True)
    check("source_file_id > 0", j.get("source_file_id", 0) > 0, True)
    check("row_count = 3", j.get("row_count"), 3)
    check("valid_count = 3", j.get("valid_count"), 3)
    sfid = j["source_file_id"]

    print("\n[3] Список файлов после загрузки")
    r = client.get(f"/api/court_years/{year_id}/source_files")
    files = r.get_json()
    check("1 файл", len(files), 1)
    check("filename", files[0]["filename"], "источник.xlsx")
    check("version = 1", files[0]["version"], 1)
    check("is_current = True", files[0]["is_current"], True)
    check("file_kind = source", files[0]["file_kind"], "source")

    print("\n[4] Фильтр по file_kind")
    r = client.get(f"/api/court_years/{year_id}/source_files?file_kind=source")
    check("source — 1", len(r.get_json()), 1)
    r = client.get(f"/api/court_years/{year_id}/source_files?file_kind=processed")
    check("processed — 0", len(r.get_json()), 0)

    print("\n[5] Метаданные файла")
    r = client.get(f"/api/source_files/{sfid}")
    check("HTTP 200", r.status_code, 200)
    check("filename", r.get_json()["filename"], "источник.xlsx")

    print("\n[6] Скачивание BLOB")
    r = client.get(f"/api/source_files/{sfid}/content")
    check("HTTP 200", r.status_code, 200)
    check("PK (zip-xlsx)", r.data[:2], b"PK")
    cd = r.headers.get("Content-Disposition", "")
    check("attachment", "attachment" in cd, True)

    print("\n[7] Дела файла")
    r = client.get(f"/api/source_files/{sfid}/cases")
    cases = r.get_json()
    check("3 дела", len(cases), 3)
    check("первое — 2-1/2020", cases[0]["case_number"], "2-1/2020")
    check("case_type = civil", cases[0]["case_type"], "civil")
    r = client.get(f"/api/source_files/{sfid}/cases?case_type=admin")
    check("admin — 0", r.get_json(), [])

    print("\n[8] Вторая версия файла")
    xlsx2 = os.path.join(tmp, "источник_v2.xlsx")
    make_xlsx(xlsx2, n=2)
    with open(xlsx2, "rb") as f:
        data = {"file": (io.BytesIO(f.read()), "источник_v2.xlsx"),
                "header_row": "1"}
        r = client.post(f"/api/court_years/{year_id}/source_files",
                        data=data, content_type="multipart/form-data")
    sfid2 = r.get_json()["source_file_id"]
    r = client.get(f"/api/court_years/{year_id}/source_files")
    files = r.get_json()
    check("2 файла", len(files), 2)
    # Свежая — первая (ORDER BY version DESC)
    check("v2 — current", files[0]["is_current"], True)
    check("v2 version", files[0]["version"], 2)

    print("\n[9] set_current: вернуть v1")
    r = client.post(f"/api/source_files/{sfid}/set_current")
    check("HTTP 200", r.status_code, 200)
    r = client.get(f"/api/source_files/{sfid}")
    check("v1 current", r.get_json()["is_current"], True)
    r = client.get(f"/api/source_files/{sfid2}")
    check("v2 не current", r.get_json()["is_current"], False)

    print("\n[10] Валидация")
    with open(xlsx, "rb") as f:
        data = {"file": (io.BytesIO(f.read()), "источник.docx")}
        r = client.post(f"/api/court_years/{year_id}/source_files",
                        data=data, content_type="multipart/form-data")
    check("Не .xlsx -> 400", r.status_code, 400)

    with open(xlsx, "rb") as f:
        data = {"file": (io.BytesIO(f.read()), "x.xlsx"),
                "file_kind": "unknown"}
        r = client.post(f"/api/court_years/{year_id}/source_files",
                        data=data, content_type="multipart/form-data")
    check("Неверный file_kind -> 400", r.status_code, 400)

    r = client.post("/api/court_years/99999/source_files",
                    data={"file": (io.BytesIO(b"x"), "x.xlsx")},
                    content_type="multipart/form-data")
    check("Несуществующий год -> 404", r.status_code, 404)

    print("\n[11] DELETE файла")
    r = client.delete(f"/api/source_files/{sfid2}")
    check("HTTP 200", r.status_code, 200)
    r = client.get(f"/api/source_files/{sfid2}")
    check("После удаления 404", r.status_code, 404)
    r = client.get(f"/api/source_files/{sfid2}/cases")
    check("Дела удалённого файла 404", r.status_code, 404)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
