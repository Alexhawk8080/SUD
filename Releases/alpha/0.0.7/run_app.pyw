# -*- coding: utf-8 -*-
"""
Тонкая обёртка для запуска launcher.py через pythonw.exe (без окна
консоли). Двойной клик по этому файлу в проводнике Windows.
"""

import os
import runpy
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
LAUNCHER = BASE / "launcher.py"

if not LAUNCHER.exists():
    # На случай, если файла нет — просто тихо выйти, чтобы не пугать
    # пользователя окном с трейсбеком.
    sys.exit(1)

os.chdir(str(BASE))
runpy.run_path(str(LAUNCHER), run_name="__main__")
