# -*- coding: utf-8 -*-
"""
Единая точка прогона всех тестов проекта.

Запускает каждый tests/test_*.py как отдельный процесс. В консоль
выводится по одной строке на модуль плюс итог. Полные логи пишутся:

    test.log        — весь вывод всех модулей (перезаписывается каждый раз);
    test_error.log  — только провалившиеся модули + итог
                      (если провалов нет — файл создаётся пустым).

Запуск:
    .venv\\Scripts\\python.exe run_tests.py
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
TESTS_DIR = BASE / "court_case_app" / "tests"
LOG_PATH = BASE / "test.log"
ERROR_LOG_PATH = BASE / "test_error.log"


def venv_python() -> Path:
    if os.name == "nt":
        return BASE / ".venv" / "Scripts" / "python.exe"
    return BASE / ".venv" / "bin" / "python"


def run_module(python: Path, test_file: Path) -> tuple:
    """Запускает один тест. Возвращает (returncode, stdout, stderr)."""
    r = subprocess.run(
        [str(python), str(test_file)],
        cwd=str(BASE / "court_case_app"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout or "", r.stderr or ""


def _log_header(log, count: int) -> None:
    log.write("=" * 78 + "\n")
    log.write(f"Прогон тестов: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    log.write(f"Модулей обнаружено: {count}\n")
    log.write(f"Python: {sys.executable}\n")
    log.write("=" * 78 + "\n\n")


def _log_module(log, test_file: Path, rc: int,
                stdout: str, stderr: str) -> None:
    status = "OK" if rc == 0 else "FAIL"
    log.write("=" * 78 + "\n")
    log.write(f"  {test_file.name}  [{status}]  (exit={rc})\n")
    log.write("=" * 78 + "\n")
    if stdout:
        log.write(stdout)
        if not stdout.endswith("\n"):
            log.write("\n")
    if stderr:
        log.write("--- stderr ---\n")
        log.write(stderr)
        if not stderr.endswith("\n"):
            log.write("\n")
    log.write("\n")


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

    ok = 0
    failed = []

    with open(LOG_PATH, "w", encoding="utf-8") as log, \
         open(ERROR_LOG_PATH, "w", encoding="utf-8") as err_log:

        _log_header(log, len(test_files))
        _log_header(err_log, len(test_files))

        for tf in test_files:
            rc, out, err = run_module(python, tf)
            status = "OK" if rc == 0 else "FAIL"
            print(f"{tf.name} - {status}")
            _log_module(log, tf, rc, out, err)
            if rc == 0:
                ok += 1
            else:
                failed.append(tf.name)
                _log_module(err_log, tf, rc, out, err)

        # Итог в оба лога
        summary = (
            "=" * 78 + "\n"
            f"ИТОГО: модулей OK = {ok}, FAIL = {len(failed)}\n"
        )
        if failed:
            summary += "Провалившиеся модули:\n"
            for name in failed:
                summary += f"  - {name}\n"
        summary += "=" * 78 + "\n"
        log.write(summary)
        err_log.write(summary)

    print()
    print(f"ИТОГО: модулей OK = {ok}, FAIL = {len(failed)}")
    if failed:
        print(f"Подробности: {ERROR_LOG_PATH.name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
