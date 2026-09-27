# -*- coding: utf-8 -*-
"""
Тесты участков и годов (stage16a1a, схема v2).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_court_areas.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import db

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


def year_data(suffix="1"):
    return {
        "судья": f"Судья{suffix}", "секретарь": f"Секретарь{suffix}",
        "дата_утверждения": "«___» 20__", "дата_акта": "«__» 20__",
        "номер_акта": suffix, "дата_подписи": "«__» 20__",
        "протокол_эк_дата": "«__» 20__", "протокол_эк_номер": suffix,
    }


def main():
    tmp = tempfile.mkdtemp(prefix="areas_v2_")
    db_path = os.path.join(tmp, "app.db")

    print("[1] Схема v3, пустые участки")
    conn = db.init_db(db_path)
    check("schema_version = v3", db.get_schema_version(conn), "v3")
    check("Участков нет", db.list_court_areas(conn), [])
    settings = db.get_settings(conn)
    check("auto_fix_categories есть", settings.get("auto_fix_categories"), "1")
    check("category_snapshot_limit есть",
          settings.get("category_snapshot_limit"), "5")
    check("Старых реквизитных ключей нет",
          "судья" in settings, False)
    check("Старых реквизитных ключей нет (судебный_участок)",
          "судебный_участок" in settings, False)

    print("\n[2] CRUD участков")
    aid = db.add_court_area(conn, {
        "номер": "9", "name": "СУ №9", "address": "г. Оренбург",
        "note": "основной"})
    check("Участок добавлен", len(db.list_court_areas(conn)), 1)
    rec = db.get_court_area(conn, aid)
    check("Номер = 9", rec["номер"], "9")
    check("Name = СУ №9", rec["name"], "СУ №9")
    check("Address = г. Оренбург", rec["address"], "г. Оренбург")

    print("\n[3] CRUD годов")
    check("Годов нет", db.list_court_years(conn, aid), [])
    y2019 = db.add_court_year(conn, aid, 2019, year_data("19"))
    y2020 = db.add_court_year(conn, aid, 2020, year_data("20"))
    years = db.list_court_years(conn, aid)
    check("Два года", len(years), 2)
    check("Первый 2019", years[0]["year"], 2019)
    check("Второй 2020", years[1]["year"], 2020)

    r2019 = db.court_year_for(conn, aid, 2019)
    check("court_year_for 2019 найден", r2019["id"], y2019)
    check("судья 2019", r2019["судья"], "Судья19")
    check("Год 2030 не найден", db.court_year_for(conn, aid, 2030), None)

    print("\n[4] is_incomplete / is_closed")
    # Пустой год (все поля пустые) — is_incomplete=1
    empty = db.add_court_year(conn, aid, 2021, {})
    check("is_incomplete=1", db.get_court_year(conn, empty)["is_incomplete"], True)
    # Закрытый год
    db.update_court_year(conn, y2019, {**year_data("19"), "is_closed": True})
    check("is_closed=1", db.get_court_year(conn, y2019)["is_closed"], True)

    print("\n[5] court_area_settings_dict")
    d2019 = db.court_area_settings_dict(conn, aid, year=2019)
    check("9 ключей", len(d2019), 9)
    check("судебный_участок=9", d2019.get("судебный_участок"), "9")
    check("судья 2019", d2019.get("судья"), "Судья19")

    d2020 = db.court_area_settings_dict(conn, aid, year=2020)
    check("судья 2020", d2020.get("судья"), "Судья20")

    d_last = db.court_area_settings_dict(conn, aid)  # последний год
    check("Последний год — 2021 (пустой)", d_last.get("судья"), "")

    check("Несуществующий id -> {}",
          db.court_area_settings_dict(conn, 99999), {})
    check("Несуществующий год -> {}",
          db.court_area_settings_dict(conn, aid, year=1900), {})

    print("\n[6] Уникальность: (участок, год)")
    try:
        db.add_court_year(conn, aid, 2019, year_data("x"))
        check("Дубликат года -> ошибка", "не поднялось", "IntegrityError")
    except Exception as exc:  # noqa: BLE001
        check("Дубликат года -> ошибка", "UNIQUE" in str(exc).upper(), True)

    print("\n[7] Удаление участка -> каскад годов")
    tmp_area = db.add_court_area(conn, {"номер": "5"})
    db.add_court_year(conn, tmp_area, 2020, year_data("5"))
    check("У 5-го года 1 год",
          len(db.list_court_years(conn, tmp_area)), 1)
    db.delete_court_area(conn, tmp_area)
    check("После удаления участка годов нет",
          db.list_court_years(conn, tmp_area), [])

    print("\n[8] Обновление участка")
    db.update_court_area(conn, aid, {
        "номер": "9", "name": "СУ №9 (новый)",
        "address": "г. Оренбург", "note": ""})
    check("Name обновлён",
          db.get_court_area(conn, aid)["name"], "СУ №9 (новый)")

    print("\n[9] Сортировка участков")
    db.add_court_area(conn, {"номер": "1"})
    db.add_court_area(conn, {"номер": "10"})
    nums = [a["номер"] for a in db.list_court_areas(conn)]
    check("Порядок: 1, 9, 10", nums, ["1", "9", "10"])

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
