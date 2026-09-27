# -*- coding: utf-8 -*-
"""
Тесты API участков и годов (stage16a1a).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_api_court_areas.py
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


def year_payload(s="1"):
    return {
        "year": 2019,
        "судья": f"Судья{s}", "секретарь": f"Сек{s}",
        "дата_утверждения": "«___» 20__",
        "дата_акта": "«__» 20__",
        "номер_акта": s, "дата_подписи": "«__» 20__",
        "протокол_эк_дата": "«__» 20__",
        "протокол_эк_номер": s,
    }


def main():
    tmp = tempfile.mkdtemp(prefix="api_areas_v2_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] Пустой список участков")
    r = client.get("/api/court_areas")
    check("HTTP 200", r.status_code, 200)
    check("Пустой список", r.get_json(), [])

    print("\n[2] POST /api/court_areas")
    r = client.post("/api/court_areas", json={
        "номер": "9", "name": "СУ №9", "address": "Оренбург", "note": ""})
    check("HTTP 200", r.status_code, 200)
    area_id = r.get_json()["id"]
    check("id получен", area_id > 0, True)

    print("\n[3] GET участка")
    r = client.get(f"/api/court_areas/{area_id}")
    check("HTTP 200", r.status_code, 200)
    rec = r.get_json()
    check("номер=9", rec["номер"], "9")
    check("name", rec["name"], "СУ №9")

    print("\n[4] POST года")
    r = client.post(f"/api/court_areas/{area_id}/years", json=year_payload("19"))
    check("HTTP 200", r.status_code, 200)
    year_id = r.get_json()["id"]
    check("id года", year_id > 0, True)

    print("\n[5] Дубликат года -> 400")
    r = client.post(f"/api/court_areas/{area_id}/years", json=year_payload("x"))
    check("HTTP 400", r.status_code, 400)

    print("\n[6] GET списка годов")
    r = client.get(f"/api/court_areas/{area_id}/years")
    check("HTTP 200", r.status_code, 200)
    check("Один год", len(r.get_json()), 1)
    check("year=2019", r.get_json()[0]["year"], 2019)

    print("\n[7] PUT года")
    new_data = {**year_payload("19"), "судья": "Новый Судья",
                "is_closed": True}
    r = client.put(f"/api/court_years/{year_id}", json=new_data)
    check("HTTP 200", r.status_code, 200)
    r = client.get(f"/api/court_years/{year_id}")
    check("судья обновлён", r.get_json()["судья"], "Новый Судья")
    check("is_closed", r.get_json()["is_closed"], True)

    print("\n[8] copy_refs")
    # Создаём 2019 (с реквизитами) и копируем в 2020
    r = client.post(f"/api/court_areas/{area_id}/years", json={
        **year_payload("19"), "year": 2020, "судья": ""})
    y2020 = r.get_json()["id"]
    r = client.post(f"/api/court_areas/{area_id}/copy_refs",
                    json={"from_year": 2019, "to_year": 2020})
    check("HTTP 200", r.status_code, 200)
    r = client.get(f"/api/court_years/{y2020}")
    check("2020 судья скопирован",
          r.get_json()["судья"], "Новый Судья")

    print("\n[9] DELETE года")
    r = client.delete(f"/api/court_years/{year_id}")
    check("HTTP 200", r.status_code, 200)
    r = client.get(f"/api/court_years/{year_id}")
    check("После удаления 404", r.status_code, 404)

    print("\n[10] DELETE участка -> 404 на года")
    r = client.delete(f"/api/court_areas/{area_id}")
    check("HTTP 200", r.status_code, 200)
    r = client.get(f"/api/court_areas/{area_id}/years")
    check("Участок удалён -> 404", r.status_code, 404)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
