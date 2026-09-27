# -*- coding: utf-8 -*-
"""
Smoke-тест файлов launcher (stage16d6g, D6g).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_launcher_files.py
"""

import ast
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
LAUNCHER = BASE / "launcher.py"
START_BAT = BASE / "start.bat"
RUN_APP_PYW = BASE / "run_app.pyw"

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


def main():
    print("[1] Файлы созданы")
    check("launcher.py существует", LAUNCHER.exists(), True)
    check("start.bat существует", START_BAT.exists(), True)
    check("run_app.pyw существует", RUN_APP_PYW.exists(), True)

    print("\n[2] launcher.py — синтаксис и ключевые элементы")
    text = LAUNCHER.read_text(encoding="utf-8")
    # Синтаксис
    try:
        ast.parse(text)
        check("синтаксис валиден", True, True)
    except SyntaxError as exc:
        check("синтаксис валиден", False, f"SyntaxError: {exc}")

    check("import tkinter", "import tkinter as tk" in text, True)
    check("класс LauncherApp", "class LauncherApp" in text, True)
    check("start_server", "def start_server" in text, True)
    check("stop_server", "def stop_server" in text, True)
    check("restart_server", "def restart_server" in text, True)
    check("open_browser", "def open_browser" in text, True)
    check("открытие логов", "def open_logs" in text, True)
    # fix_32: on_close теперь спрашивает 2 кнопки (Да/Нет) и всегда
    # останавливает сервер — вместо трёх кнопок (Да/Нет/Отмена)
    check("подтверждение при закрытии (askyesno)",
          "askyesno" in text, True)
    check("atexit-страховка (_atexit_stop)",
          "_atexit_stop" in text, True)
    check("atexit.register в __init__",
          "atexit.register(self._atexit_stop)" in text, True)
    check("env NO_WATCHDOG передаётся дочернему",
          "COURT_CASE_NO_WATCHDOG" in text, True)
    check("env PARENT_PID передаётся дочернему",
          "COURT_CASE_PARENT_PID" in text, True)
    check("SERVER_URL 127.0.0.1:5000",
          "http://127.0.0.1:5000" in text, True)
    check("taskkill на Windows",
          "taskkill" in text, True)

    print("\n[3] start.bat — содержимое")
    bat = START_BAT.read_text(encoding="utf-8")
    check("pythonw.exe", "pythonw.exe" in bat, True)
    check("launcher.py", "launcher.py" in bat, True)

    print("\n[4] run_app.pyw — содержимое")
    pyw = RUN_APP_PYW.read_text(encoding="utf-8")
    check("runpy", "runpy" in pyw, True)
    check("launcher.py", "launcher.py" in pyw, True)

    print("\n[5] Проверка функции is_port_in_use (без запуска GUI)")
    # Импортируем только функции из launcher через ast (не через import,
    # чтобы не тянуть tkinter)
    sys.path.insert(0, str(BASE))
    # Извлечём модуль без запуска main: отдельный импорт невозможен,
    # т.к. launcher импортирует tkinter и создаёт окно в main.
    # Поэтому просто проверим наличие ключевых имён.
    check("функция get_python_executable",
          "def get_python_executable" in text, True)
    check("функция is_port_in_use",
          "def is_port_in_use" in text, True)
    check("функция http_check",
          "def http_check" in text, True)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
