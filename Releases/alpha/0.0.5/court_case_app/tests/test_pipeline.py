# -*- coding: utf-8 -*-
"""
Тесты конвейера обработки (pipeline.py).

Проверяют валидацию output_format (fix_06) и базовые сценарии ошибок.

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_pipeline.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.pipeline import process_rows

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


def expect_error(name: str, fn, message_part: str):
    """Проверка, что fn() бросает ValueError с подстрокой message_part."""
    global FAILED, PASSED
    try:
        fn()
    except ValueError as exc:
        if message_part in str(exc):
            PASSED += 1
            print(f"  OK   {name}")
            return
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось содержащее: {message_part!r}"
              f"\n       получено: {str(exc)!r}")
        return
    except Exception as exc:  # noqa: BLE001
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось ValueError, получено "
              f"{type(exc).__name__}: {exc}")
        return
    FAILED += 1
    print(f"  FAIL {name}\n       ошибка не была поднята")


def main():
    tmp = tempfile.mkdtemp(prefix="pipeline_")
    db_path = os.path.join(tmp, "app.db")
    template = os.path.join(tmp, "tpl.docx")
    out_dir = os.path.join(tmp, "out")

    print("[1] Валидация output_format (fix_06)")
    expect_error(
        "Неизвестный формат -> ValueError",
        lambda: process_rows([], 2023, False, "pdf", db_path, template, out_dir),
        "Недопустимый формат")
    expect_error(
        "None -> ValueError",
        lambda: process_rows([], 2023, False, None, db_path, template, out_dir),
        "Недопустимый формат")
    expect_error(
        "excel с пробелом -> ValueError",
        lambda: process_rows([], 2023, False, "excel ", db_path, template, out_dir),
        "Недопустимый формат")

    print("\n[2] Валидный формат, но нет дел -> ValueError о годе")
    expect_error(
        "excel без дел -> ValueError о годе",
        lambda: process_rows([], 2023, False, "excel", db_path, template, out_dir),
        "Нет дел за 2023")

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
