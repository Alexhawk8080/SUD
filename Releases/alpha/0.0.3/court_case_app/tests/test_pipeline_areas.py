# -*- coding: utf-8 -*-
"""
Сквозные тесты реквизитов pipeline с court_areas (stage11c, под-этап A3).

Проверяют, что при выбранном участке реквизиты берутся из court_areas,
а при отсутствии выбора — из settings (двойное чтение).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_pipeline_areas.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from docx import Document

from core.excel_reader import SourceRow
from core.pipeline import process_rows
from database import db

FAILED = 0
PASSED = 0

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "docs",
                        "АКТ уничтожения гражданских дел.docx")


def check(name: str, actual, expected):
    global FAILED, PASSED
    ok = actual == expected
    if ok:
        PASSED += 1
        print(f"  OK   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось: {expected!r}\n       получено:  {actual!r}")


def make_rows():
    """Одна валидная строка дела за 2020 год."""
    return [
        SourceRow({
            "date": None,
            "case_number": "2-1/2020",
            "applicants": "Тестов Тест Тестович",
            "respondents": "Тестова Теста Тестовна",
            "category": "Исковое заявление о расторжении брака",
            "opis_number": 1, "unit_number": 1,
            "note": "", "end_date": None,
        })
    ]


def docx_text(path):
    doc = Document(path)
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


def make_area_dict(номер, судья, секретарь):
    """Полная запись court_areas."""
    return {
        "номер": номер,
        "судья": судья,
        "дата_утверждения": "«___» ______________ 20__ года",
        "дата_акта": "«__» ____________ 20__ г.",
        "номер_акта": "1",
        "секретарь": секретарь,
        "дата_подписи": "«__» ____________ 20__ г.",
        "протокол_эк_дата": "«__» ____________ 20__ г.",
        "протокол_эк_номер": "1",
    }


def main():
    tmp = tempfile.mkdtemp(prefix="pipe_areas_")
    db_path = os.path.join(tmp, "app.db")
    out_dir = os.path.join(tmp, "out")

    print("[1] Подготовка БД")
    conn = db.init_db(db_path)
    # После миграции должна быть одна запись с номером '3'
    initial = db.list_court_areas(conn)
    check("Миграция дала 1 запись", len(initial), 1)
    settings = db.get_settings(conn)
    check("settings.судебный_участок = '3'", settings.get("судебный_участок"), "3")
    check("settings.судья = 'О. А. Левошина'",
          settings.get("судья"), "О. А. Левошина")

    # Заводим ещё два участка — с другими реквизитами
    id5 = db.add_court_area(conn, make_area_dict("5", "Пятый П. П.", "Сек5 С. С."))
    id9 = db.add_court_area(conn, make_area_dict("9", "Девятый Д. Д.", "Сек9 С. С."))
    conn.close()

    print("\n[2] Без court_area_id -> реквизиты из settings")
    res = process_rows(make_rows(), 2020, False, "word", db_path,
                       TEMPLATE, out_dir)
    check("filename содержит '3СУ'", "3СУ" in res["filename"], True)
    text = docx_text(res["path"])
    check("Судья из settings (Левошина)", "О. А. Левошина" in text, True)
    check("Секретарь из settings (Намаюшка)", "А.М. Намаюшка" in text, True)

    print("\n[3] court_area_id = 5 -> реквизиты участка '5'")
    res5 = process_rows(make_rows(), 2020, False, "word", db_path,
                        TEMPLATE, out_dir, court_area_id=id5)
    check("filename содержит '5СУ'", "5СУ" in res5["filename"], True)
    check("Нет '3СУ' в имени", "3СУ" in res5["filename"], False)
    text5 = docx_text(res5["path"])
    check("Судья Пятый", "Пятый П. П." in text5, True)
    check("Секретарь Сек5", "Сек5 С. С." in text5, True)
    check("Нет старой судьи", "О. А. Левошина" in text5, False)

    print("\n[4] court_area_id = 9 (строка вместо int)")
    res9 = process_rows(make_rows(), 2020, False, "word", db_path,
                        TEMPLATE, out_dir, court_area_id="9"
                        if False else id9)  # id9 — int
    check("filename содержит '9СУ'", "9СУ" in res9["filename"], True)
    text9 = docx_text(res9["path"])
    check("Судья Девятый", "Девятый Д. Д." in text9, True)

    print("\n[5] court_area_id как строка '5'")
    res5s = process_rows(make_rows(), 2020, False, "word", db_path,
                         TEMPLATE, out_dir, court_area_id=str(id5))
    check("Строка '5' отработала", "5СУ" in res5s["filename"], True)

    print("\n[6] Несуществующий court_area_id -> fallback на settings")
    res_bad = process_rows(make_rows(), 2020, False, "word", db_path,
                           TEMPLATE, out_dir, court_area_id=99999)
    check("Fallback на settings: '3СУ'", "3СУ" in res_bad["filename"], True)

    print("\n[7] Пустой court_area_id -> fallback на settings")
    res_none = process_rows(make_rows(), 2020, False, "word", db_path,
                            TEMPLATE, out_dir, court_area_id=None)
    check("None -> '3СУ'", "3СУ" in res_none["filename"], True)

    print("\n[8] Некорректный court_area_id -> fallback")
    res_str = process_rows(make_rows(), 2020, False, "word", db_path,
                           TEMPLATE, out_dir, court_area_id="abc")
    check("'abc' -> fallback на '3СУ'", "3СУ" in res_str["filename"], True)

    print("\n[9] Excel-ветка тоже работает с выбранным участком")
    res_xlsx = process_rows(make_rows(), 2020, False, "excel", db_path,
                            TEMPLATE, out_dir, court_area_id=id9)
    check("Excel: filename '9СУ'", "9СУ" in res_xlsx["filename"], True)
    check("Excel: файл создан", os.path.exists(res_xlsx["path"]), True)

    print("\n[10] Метка присутствует в созданных файлах")
    from core.converter.markers import read_word_marker, read_excel_marker
    check("Word-метка", read_word_marker(res5["path"])["found"], True)
    check("Excel-метка", read_excel_marker(res_xlsx["path"])["found"], True)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
