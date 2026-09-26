# -*- coding: utf-8 -*-
"""
Тесты справочника судебных участков (stage11a).

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


def make_area(номер="3", судья="Иванов И. И."):
    """Полностью заполненная запись."""
    return {
        "номер": номер, "судья": судья,
        "дата_утверждения": "«___» ______________ 20__ года",
        "дата_акта": "«__» ____________ 20__ г.",
        "номер_акта": "1",
        "секретарь": "Петрова П. П.",
        "дата_подписи": "«__» ____________ 20__ г.",
        "протокол_эк_дата": "«__» ____________ 20__ г.",
        "протокол_эк_номер": "1",
    }


def main():
    tmp = tempfile.mkdtemp(prefix="areas_")
    db_path = os.path.join(tmp, "app.db")

    print("[1] Схема и миграция из settings")
    conn = db.init_db(db_path)
    areas = db.list_court_areas(conn)
    check("Миграция создала запись", len(areas), 1)
    a0 = areas[0]
    check("Номер из settings (судебный_участок='3')", a0["номер"], "3")
    check("Судья перенесён", a0["судья"], "О. А. Левошина")
    check("Секретарь перенесён", a0["секретарь"], "А.М. Намаюшка")
    check("is_incomplete=0 (всё заполнено)", a0["is_incomplete"], False)

    print("\n[2] Двойное чтение: settings не тронуты")
    settings = db.get_settings(conn)
    check("settings.судебный_участок на месте", settings.get("судебный_участок"), "3")
    check("settings.судья на месте", settings.get("судья"), "О. А. Левошина")

    print("\n[3] Повторная инициализация не дублирует")
    conn.close()
    conn = db.init_db(db_path)
    areas = db.list_court_areas(conn)
    check("По-прежнему одна запись", len(areas), 1)

    print("\n[4] CRUD: добавление")
    new_id = db.add_court_area(conn, make_area(номер="5", судья="Сидоров С. С."))
    check("Запись добавлена", len(db.list_court_areas(conn)), 2)
    rec5 = db.get_court_area(conn, new_id)
    check("Номер = 5", rec5["номер"], "5")
    check("Судья = Сидоров С. С.", rec5["судья"], "Сидоров С. С.")
    check("is_incomplete=0", rec5["is_incomplete"], False)

    print("\n[5] Поиск по номеру")
    found = db.court_area_for_number(conn, "5")
    check("Найдено по номеру", found["id"], new_id)
    check("Не найдено по чужому номеру", db.court_area_for_number(conn, "99"), None)
    check("Пустой номер -> None", db.court_area_for_number(conn, ""), None)

    print("\n[6] Обновление")
    new_data = make_area(номер="5", судья="Новиков Н. Н.")
    new_data["секретарь"] = ""  # специально оставляем пустое
    db.update_court_area(conn, new_id, new_data)
    rec5 = db.get_court_area(conn, new_id)
    check("Судья обновлён", rec5["судья"], "Новиков Н. Н.")
    check("is_incomplete=1 (пустой секретарь)", rec5["is_incomplete"], True)

    print("\n[7] Добавление неполной записи")
    incomplete_data = make_area(номер="7")
    incomplete_data["судья"] = ""
    inc_id = db.add_court_area(conn, incomplete_data)
    check("Неполная добавлена", db.get_court_area(conn, inc_id)["is_incomplete"], True)

    print("\n[8] Валидация: пустой номер")
    try:
        db.add_court_area(conn, make_area(номер=""))
        check("Пустой номер -> ValueError", "не поднялось", "ValueError")
    except ValueError:
        check("Пустой номер -> ValueError", True, True)

    print("\n[9] Удаление")
    db.delete_court_area(conn, new_id)
    check("Удаление сработало", db.get_court_area(conn, new_id), None)
    check("Осталось 2 записи", len(db.list_court_areas(conn)), 2)

    print("\n[10] court_area_settings_dict")
    d = db.court_area_settings_dict(conn, inc_id)
    check("Ключ 'судебный_участок'", d.get("судебный_участок"), "7")
    check("Ключ 'судья'", d.get("судья"), "")
    check("9 ключей", len(d), 9)
    check("Нет 'итого'", "итого" in d, False)
    check("Нет 'год_дел'", "год_дел" in d, False)
    check("Пустой id -> {}", db.court_area_settings_dict(conn, 9999), {})

    print("\n[11] Сортировка по номеру")
    db.add_court_area(conn, make_area(номер="1", судья="А."))
    db.add_court_area(conn, make_area(номер="10", судья="Б."))
    nums = [r["номер"] for r in db.list_court_areas(conn)]
    check("Порядок: 1, 3, 7, 10", nums, ["1", "3", "7", "10"])

    conn.close()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
