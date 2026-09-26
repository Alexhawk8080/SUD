# -*- coding: utf-8 -*-
"""
Настройка окружения: создание .venv и установка зависимостей.

Учитывает корпоративный SSL: pip вызывается с --trusted-host.

Запуск:
    python setup_env.py
"""

import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
VENV = BASE / ".venv"
TRUSTED = ["--trusted-host", "pypi.org",
           "--trusted-host", "files.pythonhosted.org"]


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def main() -> int:
    if not VENV.exists():
        print(f"Создание {VENV} ...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    else:
        print(f"{VENV} уже существует")

    pip = venv_python()
    if not pip.exists():
        print(f"НЕ НАЙДЕН интерпретатор .venv: {pip}")
        return 1

    for req in ("requirements.txt", "requirements-dev.txt"):
        path = BASE / req
        if not path.exists():
            print(f"Пропуск (нет файла): {req}")
            continue
        print(f"Установка {req} ...")
        subprocess.run(
            [str(pip), "-m", "pip", "install", "-r", str(path), *TRUSTED],
            check=True)

    print("\nОкружение готово.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
