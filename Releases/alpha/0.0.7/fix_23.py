# -*- coding: utf-8 -*-
"""
fix_28_import_and_tests.py

Правки:
    1. app.py: добавить import logging / sys / RotatingFileHandler
       (в fix_27 эти импорты не применились — блок импортов в app.py
       имел другой вид).
    2. Обновить проверки в тестах:
         test_db_pipeline_full.py      — '9У' → '9 CУ'
         test_pipeline_areas.py        — '9СУ' / '3СУ' → '9 CУ' / '3 CУ'
       под фактический формат имени акта (Акт уничтожения ... 3 CУ 2020.docx).

Запуск:
    .venv\\Scripts\\python.exe fix_28_import_and_tests.py
    .venv\\Scripts\\python.exe run_tests.py
"""

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
APP_PY = BASE / "court_case_app" / "app.py"
TESTS = BASE / "court_case_app" / "tests"


# ============================================================================
# 1. Добавить импорты в app.py
# ============================================================================

def ensure_imports() -> bool:
    if not APP_PY.exists():
        print(f"НЕ НАЙДЕН: {APP_PY.relative_to(BASE)}")
        return False

    text = APP_PY.read_text(encoding="utf-8")
    changed = []

    # import logging
    if not re.search(r"^import\s+logging\b", text, re.MULTILINE):
        # Вставляем после первого import os / import json / import sys
        anchor = re.search(r"^import\s+\w+\b", text, re.MULTILINE)
        if anchor:
            pos = anchor.end()
            text = text[:pos] + "\nimport logging" + text[pos:]
            changed.append("import logging")
        else:
            print("  НЕ НАЙДЕН блок импортов для вставки import logging")
            return False

    # import sys
    if not re.search(r"^import\s+sys\b", text, re.MULTILINE):
        # вставляем после import logging (он уже есть)
        m = re.search(r"^import\s+logging\b", text, re.MULTILINE)
        if m:
            pos = m.end()
            text = text[:pos] + "\nimport sys" + text[pos:]
            changed.append("import sys")

    # from logging.handlers import RotatingFileHandler
    if "from logging.handlers import RotatingFileHandler" not in text:
        # вставляем после import logging / import sys
        m = re.search(r"^import\s+sys\b", text, re.MULTILINE)
        if not m:
            m = re.search(r"^import\s+logging\b", text, re.MULTILINE)
        if m:
            pos = m.end()
            text = (text[:pos]
                    + "\nfrom logging.handlers import RotatingFileHandler"
                    + text[pos:])
            changed.append("RotatingFileHandler")

    if changed:
        APP_PY.write_text(text, encoding="utf-8")
        print(f"ИЗМЕНЁН: {APP_PY.relative_to(BASE)}")
        for c in changed:
            print(f"         + {c}")
    else:
        print(f"УЖЕ ПРИМЕНЁН: {APP_PY.relative_to(BASE)} (импорты на месте)")
    return True


# ============================================================================
# 2. Правки в тестах: формат имени файла '9 CУ'
# ============================================================================

TEST_FIXES = [
    # (имя файла, список пар (old_substr, new_substr))
    ("test_db_pipeline_full.py", [
        ('"9У"', '"9 CУ"'),
        ("'9У'", "'9 CУ'"),
    ]),
    ("test_pipeline_areas.py", [
        ('"9СУ"', '"9 CУ"'),
        ("'9СУ'", "'9 CУ'"),
        ('"3СУ"', '"3 CУ"'),
        ("'3СУ'", "'3 CУ'"),
        ('"5СУ"', '"5 CУ"'),
        ("'5СУ'", "'5 CУ'"),
        ('"9У"', '"9 CУ"'),
        ("'9У'", "'9 CУ'"),
        ('"3У"', '"3 CУ"'),
        ("'3У'", "'3 CУ'"),
        ('"5У"', '"5 CУ"'),
        ("'5У'", "'5 CУ'"),
    ]),
    ("test_api_process_export.py", [
        ('"9У"', '"9 CУ"'),
        ("'9У'", "'9 CУ'"),
    ]),
    ("test_api_word_to_xlsx.py", [
        ('"9СУ"', '"9 CУ"'),
        ("'9СУ'", "'9 CУ'"),
        ('"9У"', '"9 CУ"'),
        ("'9У'", "'9 CУ'"),
    ]),
    ("test_api_convert.py", [
        ('"3СУ"', '"3 CУ"'),
        ("'3СУ'", "'3 CУ'"),
        ('"5СУ"', '"5 CУ"'),
        ("'5СУ'", "'5 CУ'"),
    ]),
]


def patch_tests() -> int:
    fixed = 0
    for fname, pairs in TEST_FIXES:
        path = TESTS / fname
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in pairs:
            if old in text:
                text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding="utf-8")
            fixed += 1
            print(f"  ИЗМЕНЁН: {path.relative_to(BASE)}")
    return fixed


def main() -> int:
    print("fix_28: import logging + формат '9 CУ' в тестах")
    print("=" * 60)

    print("[1] app.py — импорты logging / sys / RotatingFileHandler")
    ok1 = ensure_imports()

    print("\n[2] Тесты: '9У'/'9СУ'/'3СУ' → '9 CУ'/'3 CУ'")
    fixed = patch_tests()
    print(f"  Обновлено модулей: {fixed}")

    print()
    if not ok1:
        print("ОШИБКА в шаге 1.")
        return 1
    print("=" * 60)
    print("Готово.")
    print()
    print("ВАЖНО — правильный интерпретатор:")
    print("  Раньше: Releases/alpha/0.0.6/.venv/Scripts/python.exe  (релизный)")
    print("  Нужно:  .venv\\Scripts\\python.exe                       (основной)")
    print()
    print("Перезапустите тесты:")
    print("  .venv\\Scripts\\python.exe run_tests.py")
    print()
    print("Ожидание: 51 модуль OK, FAIL = 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())