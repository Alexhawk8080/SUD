# -*- coding: utf-8 -*-
"""
Единая точка прогона всех тестов проекта.

Запускает каждый tests/test_*.py как отдельный процесс (сохраняет
существующие скрипты с sys.exit), собирает итог, возвращает exit code.

Запуск:
    .venv\Scripts\python.exe run_tests.py
"""

import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
TESTS_DIR = BASE / "court_case_app" / "tests"


def venv_python() -> Path:
    if os.name == "nt":
        return BASE / ".venv" / "Scripts" / "python.exe"
    return BASE / ".venv" / "bin" / "python"


def main() -> int:
    python = venv_python()
    if not python.exists():
        print(f"НЕ НАЙДЕН интерпретатор .venv: {python}")
        print("Сначала запустите: python setup_env.py")
        return 1

    if not TESTS_DIR.exists():
        print(f"НЕ НАЙДЕНА папка тестов: {TESTS_DIR}")
        return 1

    test_files = sorted(TESTS_DIR.glob("test_*.py"))
    if not test_files:
        print("Тестов не найдено.")
        return 1

    ok, fail = 0, []
    for tf in test_files:
        print("\n" + "=" * 70)
        print(f"  {tf.name}")
        print("=" * 70)
        r = subprocess.run([str(python), str(tf)],
                           cwd=str(BASE / "court_case_app"))
        if r.returncode == 0:
            ok += 1
        else:
            fail.append(tf.name)

    print("\n" + "=" * 70)
    print(f"ИТОГО: модулей OK = {ok}, FAIL = {len(fail)}")
    if fail:
        for name in fail:
            print(f"  FAIL: {name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
