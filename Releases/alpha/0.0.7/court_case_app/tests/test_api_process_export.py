# -*- coding: utf-8 -*-
"""
Тесты API обработки и экспорта (stage16d5c, D5c).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_api_process_export.py
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


def make_xlsx(path, n=3, year=2020):
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
    tmp = tempfile.mkdtemp(prefix="api_pex_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    # Подготовка: участок + год + файл
    r = client.post("/api/court_areas", json={"номер": "9"})
    area_id = r.get_json()["id"]
    r = client.post(f"/api/court_areas/{area_id}/years",
                    json={**year_data("20"), "year": 2020})
    year_id = r.get_json()["id"]

    xlsx = os.path.join(tmp, "источник.xlsx")
    make_xlsx(xlsx, n=3)
    with open(xlsx, "rb") as f:
        data = {"file": (io.BytesIO(f.read()), "источник.xlsx"),
                "header_row": "1"}
        client.post(f"/api/court_years/{year_id}/source_files",
                    data=data, content_type="multipart/form-data")

    print("[1] process: базовый")
    r = client.post(f"/api/court_years/{year_id}/process",
                    json={"case_type": "civil"})
    check("HTTP 200", r.status_code, 200)
    j = r.get_json()
    check("ok = True", j.get("ok"), True)
    check("result_id > 0", j.get("result_id", 0) > 0, True)
    check("record_count = 3", j.get("record_count"), 3)
    check("target_year = 2020", j.get("target_year"), 2020)
    rid = j["result_id"]

    print("\n[2] results: список года")
    r = client.get(f"/api/court_years/{year_id}/results")
    check("HTTP 200", r.status_code, 200)
    results = r.get_json()
    check("1 результат (civil)", len(results), 1)
    check("case_type = civil", results[0]["case_type"], "civil")
    check("record_count = 3", results[0]["record_count"], 3)

    print("\n[3] result: детали + rows")
    r = client.get(f"/api/results/{rid}")
    check("HTTP 200", r.status_code, 200)
    j = r.get_json()
    check("rows есть", "rows" in j, True)
    check("3 строки", len(j["rows"]), 3)
    check("case_number row[0]", j["rows"][0]["case_number"], "2-1/2020")

    print("\n[4] Повторная обработка перезаписывает")
    r = client.post(f"/api/court_years/{year_id}/process",
                    json={"case_type": "civil"})
    rid2 = r.get_json()["result_id"]
    check("Новый id", rid2 != rid, True)
    check("Старый недоступен", client.get(f"/api/results/{rid}").status_code, 404)

    print("\n[5] process с process_alimony (перезаписывает результат)")
    r = client.post(f"/api/court_years/{year_id}/process",
                    json={"case_type": "civil", "process_alimony": True})
    check("HTTP 200", r.status_code, 200)
    # Перезапись: запоминаем актуальный result_id для последующих блоков
    rid2 = r.get_json()["result_id"]

    print("\n[6] export в Word")
    r = client.post(f"/api/results/{rid2}/export",
                    json={"output_format": "word"})
    check("HTTP 200", r.status_code, 200)
    cd = r.headers.get("Content-Disposition", "")
    check("attachment", "attachment" in cd, True)
    check("PK (docx)", r.data[:2], b"PK")
    # Content-Disposition URL-кодирует не-ASCII — декодируем
    from urllib.parse import unquote
    cd_decoded = unquote(cd)
    check("'9' в имени", "9" in cd_decoded, True)

    print("\n[7] export в Excel")
    r = client.post(f"/api/results/{rid2}/export",
                    json={"output_format": "excel"})
    check("HTTP 200", r.status_code, 200)
    check("PK (xlsx)", r.data[:2], b"PK")

    print("\n[8] export с columns")
    r = client.post(f"/api/results/{rid2}/export",
                    json={"output_format": "excel",
                          "columns": ["sequential", "title", "retention"]})
    check("HTTP 200", r.status_code, 200)

    print("\n[9] admin-ветка (нет дел типа admin)")
    r = client.post(f"/api/court_years/{year_id}/process",
                    json={"case_type": "admin"})
    check("400 (нет дел admin)", r.status_code, 400)

    print("\n[10] Валидация")
    r = client.post(f"/api/court_years/{year_id}/process",
                    json={"case_type": "unknown"})
    check("Неверный case_type -> 400", r.status_code, 400)

    r = client.post("/api/court_years/99999/process",
                    json={"case_type": "civil"})
    check("Несуществующий год -> 404", r.status_code, 404)

    r = client.get("/api/results/99999")
    check("Несуществующий result_id -> 404", r.status_code, 404)

    r = client.post(f"/api/results/{rid2}/export",
                    json={"output_format": "pdf"})
    check("Неверный output_format -> 400", r.status_code, 400)

    print("\n[11] DELETE результата")
    r = client.delete(f"/api/results/{rid2}")
    check("HTTP 200", r.status_code, 200)
    r = client.get(f"/api/results/{rid2}")
    check("После удаления 404", r.status_code, 404)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
