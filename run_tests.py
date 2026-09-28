# -*- coding: utf-8 -*-
"""
Dual-runner тестов: legacy (subprocess) + modern (pytest).

  * legacy (без "^def test_" на верхнем уровне) — subprocess, exit code;
  * modern (с "^def test_") — pytest через subprocess, exit code.

Оба варианта запускаются VENV_PY. Формат вывода и test_error.log сохранены.

Запуск:
    .venv\\Scripts\\python.exe run_tests.py
"""

import os
import re
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


def is_modern(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return re.search(r"^def test_", text, re.MULTILINE) is not None


def run_legacy(python: Path, test_file: Path):
    r = subprocess.run(
        [str(python), str(test_file)],
        cwd=str(BASE / "court_case_app"),
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return r.returncode, r.stdout or "", r.stderr or ""


def run_modern(python: Path, test_file: Path):
    r = subprocess.run(
        [str(python), "-m", "pytest", str(test_file),
         "-q", "--tb=short", "-p", "no:cacheprovider"],
        cwd=str(BASE / "court_case_app"),
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return r.returncode, r.stdout or "", r.stderr or ""


def _log_header(log, count: int) -> None:
    log.write("=" * 78 + "\n")
    log.write(f"Прогон тестов: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    log.write(f"Модулей обнаружено: {count}\n")
    log.write(f"Python: {sys.executable}\n")
    log.write("=" * 78 + "\n\n")


def _log_module(log, test_file, rc, stdout, stderr, kind) -> None:
    status = "OK" if rc == 0 else "FAIL"
    log.write("=" * 78 + "\n")
    log.write(f"  {test_file.name}  [{status}]  ({kind}, exit={rc})\n")
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
        return 1

    if not TESTS_DIR.exists():
        print(f"НЕ НАЙДЕНА папка тестов: {TESTS_DIR}")
        return 1

    test_files = sorted(TESTS_DIR.glob("test_*.py"))
    if not test_files:
        print("Тестов не найдено.")
        return 1

    legacy = [f for f in test_files if not is_modern(f)]
    modern = [f for f in test_files if is_modern(f)]

    ok = 0
    failed = []

    with open(LOG_PATH, "w", encoding="utf-8") as log, \
         open(ERROR_LOG_PATH, "w", encoding="utf-8") as err_log:

        _log_header(log, len(test_files))
        _log_header(err_log, len(test_files))

        for tf in legacy:
            rc, out, err = run_legacy(python, tf)
            status = "OK" if rc == 0 else "FAIL"
            print(f"{tf.name} - {status}")
            _log_module(log, tf, rc, out, err, "legacy")
            if rc == 0:
                ok += 1
            else:
                failed.append(tf.name)
                _log_module(err_log, tf, rc, out, err, "legacy")

        for tf in modern:
            rc, out, err = run_modern(python, tf)
            status = "OK" if rc == 0 else "FAIL"
            print(f"{tf.name} - {status}")
            _log_module(log, tf, rc, out, err, "modern")
            if rc == 0:
                ok += 1
            else:
                failed.append(tf.name)
                _log_module(err_log, tf, rc, out, err, "modern")

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
    print(f"  legacy: {len(legacy)}, modern: {len(modern)}")
    if failed:
        print(f"Подробности: {ERROR_LOG_PATH.name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())