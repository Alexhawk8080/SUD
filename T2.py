# -*- coding: utf-8 -*-
"""
fix_25_act_filename.py

Меняет формат имени акта по умолчанию на:

    Акт уничтожения {тип дел} {участок}У {год}.docx (.xlsx)

где {тип дел} = "гражданских дел" | "административных дел".

Что патчит:
    1. Создаёт core/filename_utils.py — make_act_filename().
    2. core/db_pipeline.py::export_year_result_to_file
    3. core/pipeline.py::process_rows
    4. app.py::convert_xlsx_to_word_route
    5. app.py::convert_word_to_xlsx_route
    6. Тесты — заменяем проверки "9СУ"/"3СУ" на "9У"/"3У".

Запуск:
    .venv\\Scripts\\python.exe fix_25_act_filename.py
    .venv\\Scripts\\python.exe run_tests.py
    :: перезапустить app.py
"""

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
CORE = BASE / "court_case_app" / "core"
TESTS = BASE / "court_case_app" / "tests"
FILENAME_UTILS = CORE / "filename_utils.py"
DB_PIPELINE = CORE / "db_pipeline.py"
PIPELINE = CORE / "pipeline.py"
APP_PY = BASE / "court_case_app" / "app.py"


# ============================================================================
# 1. core/filename_utils.py
# ============================================================================

UTILS_CONTENT = '''# -*- coding: utf-8 -*-
"""
Формирование имени файла акта.

Формат:
    Акт уничтожения {тип дел} {участок}У {год}.{ext}

Примеры:
    Акт уничтожения гражданских дел 9У 2020.docx
    Акт уничтожения административных дел 5У 2019.xlsx
    Акт уничтожения гражданских дел 2020.docx  (если нет участка)
"""

# Отображаемый родительный падеж типа дел
_CASE_TYPE_LABEL = {
    "civil": "гражданских дел",
    "admin": "административных дел",
}


def make_act_filename(номер, case_type, year, ext) -> str:
    """
    Собирает имя файла акта.

    номер     — номер судебного участка (строка/число; пустое допустимо);
    case_type — 'civil' | 'admin' (или любое другое → по умолчанию civil);
    year      — год дел (число/строка);
    ext       — 'docx' | 'xlsx' (без точки).
    """
    type_part = _CASE_TYPE_LABEL.get(str(case_type or "civil").strip(),
                                     _CASE_TYPE_LABEL["civil"])
    num = str(номер or "").strip()
    parts = ["Акт уничтожения", type_part]
    if num:
        parts.append(f"{num}У")
    parts.append(str(year))
    ext_clean = str(ext or "").lstrip(".").strip()
    return " ".join(parts) + f".{ext_clean}"
'''


# ============================================================================
# 2. Патч db_pipeline.py (export_year_result_to_file)
# ============================================================================

DB_OLD = '''    # Имя файла
    num = str(common.get("судебный_участок") or "").strip()
    base = "Акт уничтожения гражданских дел"
    if num:
        base += f" {num}СУ"
    base += f" {res['target_year']}"

    ext = "docx" if output_format == "word" else "xlsx"
    filename = f"{base}.{ext}"'''

DB_NEW = '''    # Имя файла (единый формат — см. core/filename_utils)
    from core.filename_utils import make_act_filename
    num = str(common.get("судебный_участок") or "").strip()
    ext = "docx" if output_format == "word" else "xlsx"
    filename = make_act_filename(
        num, res.get("case_type"), res["target_year"], ext)'''


# ============================================================================
# 3. Патч pipeline.py (process_rows)
# ============================================================================

PIP_OLD = '''    base = "Акт уничтожения гражданских дел"
    if num:
        base += f" {num}СУ"
    base += f" {target_year}"

    if output_format == "word":
        common_values["год_дел"] = str(target_year)
        filename = f"{base}.docx"'''

PIP_NEW = '''    from core.filename_utils import make_act_filename
    ext = "docx" if output_format == "word" else "xlsx"
    filename = make_act_filename(num, "civil", target_year, ext)

    if output_format == "word":
        common_values["год_дел"] = str(target_year)'''


# ============================================================================
# 4. Патчи app.py (два роута конвертации)
# ============================================================================

APP_OLD_1 = '''    base = "Акт уничтожения гражданских дел"
    if num:
        base += f" {num}СУ"
    base += f" {year}"
    filename = f"{base}.docx"'''

APP_NEW_1 = '''    from core.filename_utils import make_act_filename
    filename = make_act_filename(num, "civil", year, "docx")'''

APP_OLD_2 = '''    base = "Акт уничтожения гражданских дел"
    if num:
        base += f" {num}СУ"
    base += f" {yinfo['year']}"
    filename = f"{base}.xlsx"'''

APP_NEW_2 = '''    from core.filename_utils import make_act_filename
    filename = make_act_filename(num, "civil", yinfo["year"], "xlsx")'''


# ============================================================================
# 5. Патчи тестов
# ============================================================================

TEST_PAIRS = [
    # файл, что_искать, чем_заменить
    ("test_db_pipeline_full.py", '"9СУ"', '"9У"'),
    ("test_db_pipeline_full.py", "'9СУ'", "'9У'"),
    ("test_api_process_export.py", '"9СУ"', '"9У"'),
    ("test_api_process_export.py", "'9СУ'", "'9У'"),
    ("test_api_convert.py", '"3СУ"', '"3У"'),
    ("test_api_convert.py", "'3СУ'", "'3У'"),
    ("test_api_convert.py", '"5СУ"', '"5У"'),
    ("test_api_convert.py", "'5СУ'", "'5У'"),
    ("test_api_word_to_xlsx.py", '"9СУ"', '"9У"'),
    ("test_api_word_to_xlsx.py", "'9СУ'", "'9У'"),
    ("test_pipeline_areas.py", '"3СУ"', '"3У"'),
    ("test_pipeline_areas.py", "'3СУ'", "'3У'"),
    ("test_pipeline_areas.py", '"5СУ"', '"5У"'),
    ("test_pipeline_areas.py", "'5СУ'", "'5У'"),
    ("test_pipeline_areas.py", '"9СУ"', '"9У"'),
    ("test_pipeline_areas.py", "'9СУ'", "'9У'"),
]


def write_utils() -> bool:
    if FILENAME_UTILS.exists():
        print(f"  УЖЕ ЕСТЬ: {FILENAME_UTILS.relative_to(BASE)}")
        return True
    FILENAME_UTILS.write_text(UTILS_CONTENT, encoding="utf-8")
    print(f"  СОЗДАН: {FILENAME_UTILS.relative_to(BASE)}")
    return True


def patch_file(path: Path, old: str, new: str, label: str) -> bool:
    if not path.exists():
        print(f"  НЕ НАЙДЕН: {path.relative_to(BASE)}")
        return False
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if new in text:
            print(f"  УЖЕ: {label}")
            return True
        print(f"  НЕ НАЙДЕН фрагмент ({label}) в {path.relative_to(BASE)}")
        return False
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"  ИЗМЕНЁН ({label}): {path.relative_to(BASE)}")
    return True


def patch_tests() -> int:
    """Патчит строки в тестах: '9СУ' → '9У' и т.п."""
    fixed = 0
    not_found = 0
    for fname, old, new in TEST_PAIRS:
        path = TESTS / fname
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if old in text:
            text = text.replace(old, new)
            path.write_text(text, encoding="utf-8")
            fixed += 1
    return fixed


def main() -> int:
    print("fix_25: формат имени файла акта")
    print("=" * 60)

    print("[1] core/filename_utils.py")
    ok1 = write_utils()

    print("\n[2] db_pipeline.py")
    ok2 = patch_file(DB_PIPELINE, DB_OLD, DB_NEW, "export_year_result_to_file")

    print("\n[3] pipeline.py")
    ok3 = patch_file(PIPELINE, PIP_OLD, PIP_NEW, "process_rows")

    print("\n[4] app.py")
    ok4 = patch_file(APP_PY, APP_OLD_1, APP_NEW_1, "convert xlsx->word")
    ok5 = patch_file(APP_PY, APP_OLD_2, APP_NEW_2, "convert word->xlsx")

    print("\n[5] Тесты — замены '9СУ' → '9У', '3СУ' → '3У'")
    fixed = patch_tests()
    print(f"  Модулей обновлено: {fixed}")

    print()
    if not (ok1 and ok2 and ok3 and ok4 and ok5):
        print("ЧТО-ТО НЕ ПРИМЕНЕНО. Проверьте сообщения выше.")
        return 1
    print("=" * 60)
    print("Готово.")
    print()
    print("Перезапустите сервер:")
    print("  .venv\\Scripts\\python.exe court_case_app\\app.py")
    print()
    print("Проверка:")
    print("  .venv\\Scripts\\python.exe run_tests.py")
    print()
    print("Проверка имени в диалоге сохранения:")
    print("  /db/year/<id> -> «Результат» -> «Скачать Word».")
    print("  Имя должно быть: Акт уничтожения гражданских дел 9У 2020.docx")
    return 0


if __name__ == "__main__":
    sys.exit(main())