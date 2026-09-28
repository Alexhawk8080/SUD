# stage_41
# -*- coding: utf-8 -*-
"""
Тесты: настройка taxonomy_diff_logging управляет diff_logging в /process.

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_api_settings_diff_logging.py
"""

import io
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openpyxl import Workbook

import app as app_module
from core import taxonomy_diff

FAILED = 0
PASSED = 0


def check(name, actual, expected):
    global FAILED, PASSED
    if actual == expected:
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
                   "Споры, связанные с жилищными отношениями о взыскании "
                   "платы за жилую площадь и коммунальные платежи",
                   1, i + 1, "", datetime(year, 2, 10 + i)])
    wb.save(path)


def _flush_taxonomy_logs():
    import logging
    for name in ("taxonomy_prefix_diff", "taxonomy_retention_diff"):
        for h in logging.getLogger(name).handlers:
            try:
                h.flush()
            except Exception:
                pass


def main():
    tmp = tempfile.mkdtemp(prefix="api_diff_setting_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    # Перенаправляем логи таксономии в temp
    taxonomy_diff.ROOT = Path(tmp)
    taxonomy_diff.reset()

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

    prefix_log = Path(tmp) / "taxonomy_prefix_diff.log"

    print("[1] По умолчанию (setting не задан) — лог не пишется")
    taxonomy_diff.reset()
    r = client.post(f"/api/court_years/{year_id}/process",
                    json={"case_type": "civil"})
    check("HTTP 200", r.status_code, 200)
    _flush_taxonomy_logs()
    check("лог не создан", prefix_log.exists(), False)

    print("\n[2] Включаем taxonomy_diff_logging=1 — лог пишется")
    client.post("/api/settings", json={"taxonomy_diff_logging": "1"})
    taxonomy_diff.reset()
    r = client.post(f"/api/court_years/{year_id}/process",
                    json={"case_type": "civil"})
    check("HTTP 200", r.status_code, 200)
    _flush_taxonomy_logs()
    check("лог создан", prefix_log.exists(), True)
    if prefix_log.exists():
        text = prefix_log.read_text(encoding="utf-8")
        check("в логе есть 'по иску'", "по иску" in text, True)

    print("\n[3] Выключаем (setting='0') — лог не пишется")
    client.post("/api/settings", json={"taxonomy_diff_logging": "0"})
    taxonomy_diff.reset()
    r = client.post(f"/api/court_years/{year_id}/process",
                    json={"case_type": "civil"})
    check("HTTP 200", r.status_code, 200)
    _flush_taxonomy_logs()
    check("лог не создан", prefix_log.exists(), False)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
