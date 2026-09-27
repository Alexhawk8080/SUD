# -*- coding: utf-8 -*-
"""
fix_27_server_logging.py

Гарантированно включает логирование сервера в app.py:
    * logging в court_case_app/server_errors.log (RotatingFileHandler);
    * sys.excepthook / threading.excepthook;
    * логирование watchdog (причина остановки сервера);
    * логирование старта приложения;
    * зеркалирование stdout в server_console.log (чтобы HTTP-строки
      werkzeug тоже сохранялись).

Идемпотентен: если logging уже настроен, ничего не дублирует,
только добавляет отсутствующие части.

Запуск:
    .venv\\Scripts\\python.exe fix_27_server_logging.py
    .venv\\Scripts\\python.exe run_tests.py
    :: перезапустить app.py (через launcher или Ctrl+C + заново)
"""

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
APP_PY = BASE / "court_case_app" / "app.py"


# ---------- ЧАСТЬ 1. Импорты ----------

IMP_OLD = '''import json
import os
import threading
import time
import webbrowser'''

IMP_NEW = '''import json
import logging
import os
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler'''


# ---------- ЧАСТЬ 2. Логирование + перехватчики ----------

SETUP_OLD = '''BASE_DIR = os.path.dirname(os.path.abspath(__file__))'''

SETUP_NEW = '''BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# fix_27: логирование в файлы
# ---------------------------------------------------------------------------
_SERVER_LOG = os.path.join(BASE_DIR, "server_errors.log")

_logger = logging.getLogger("court_case_app")
_logger.setLevel(logging.DEBUG)
if not _logger.handlers:
    _handler = RotatingFileHandler(
        _SERVER_LOG, maxBytes=2 * 1024 * 1024, backupCount=3,
        encoding="utf-8")
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False


def _log_uncaught(exc_type, exc_value, exc_tb):
    """sys.excepthook: пишем необработанные исключения в лог."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _logger.critical("Uncaught exception",
                     exc_info=(exc_type, exc_value, exc_tb))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _log_thread_exception(args):
    """threading.excepthook: пишем исключения фоновых потоков."""
    _logger.critical(
        "Uncaught exception in thread %s",
        getattr(args, "thread", "?").name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


sys.excepthook = _log_uncaught
if hasattr(threading, "excepthook"):
    threading.excepthook = _log_thread_exception

# Зеркалируем stdout/stderr в файл — чтобы HTTP-строки werkzeug и print()
# из приложения тоже сохранялись.
try:
    _CONSOLE_LOG = os.path.join(BASE_DIR, "server_console.log")
    _stream = open(_CONSOLE_LOG, "a", encoding="utf-8", buffering=1)

    class _Tee:
        def __init__(self, original, fileobj):
            self._original = original
            self._fileobj = fileobj

        def write(self, data):
            try:
                self._original.write(data)
            except Exception:
                pass
            try:
                self._fileobj.write(data)
                self._fileobj.flush()
            except Exception:
                pass
            return len(data) if isinstance(data, str) else 0

        def flush(self):
            for obj in (self._original, self._fileobj):
                try:
                    obj.flush()
                except Exception:
                    pass

        def fileno(self):
            return self._original.fileno()

        def isatty(self):
            return False

    sys.stdout = _Tee(sys.stdout, _stream)
    sys.stderr = _Tee(sys.stderr, _stream)
except Exception:
    pass'''

# ---------- ЧАСТЬ 3. Watchdog ----------

WD_OLD = '''def _beat_watchdog():
    """Фоновый поток: останавливает сервер, если heartbeat пропал."""
    while True:
        time.sleep(2.0)
        if time.time() - _last_beat > HEARTBEAT_TIMEOUT:
            os._exit(0)'''

WD_NEW = '''def _beat_watchdog():
    """Фоновый поток: останавливает сервер, если heartbeat пропал."""
    while True:
        time.sleep(2.0)
        if time.time() - _last_beat > HEARTBEAT_TIMEOUT:
            _logger.warning(
                "Watchdog: heartbeat отсутствует %.1f c (порог %.1f) — "
                "останавливаю сервер через os._exit(0)",
                time.time() - _last_beat, HEARTBEAT_TIMEOUT)
            os._exit(0)'''


# ---------- ЧАСТЬ 4. Старт приложения ----------

START_OLD = '''if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)'''

START_NEW = '''if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    _logger.info("Сервер стартует. app.py=%s", __file__)
    _logger.info("DB_PATH=%s", DB_PATH)
    _logger.info("Server log: %s", _SERVER_LOG)
    _logger.info("Console log: %s",
                 locals().get("_CONSOLE_LOG", "(no console log)"))'''


# ---------- Патчи ----------

def _already(text: str, marker: str) -> bool:
    return marker in text


def patch_imports(text: str) -> str:
    if _already(text, "from logging.handlers import RotatingFileHandler"):
        print("  [1] импорты logging — уже есть")
        return text
    if IMP_OLD not in text:
        print("  [1] НЕ НАЙДЕН блок импортов")
        return text
    text = text.replace(IMP_OLD, IMP_NEW, 1)
    print("  [1] импорты logging добавлены")
    return text


def patch_setup(text: str) -> str:
    if _already(text, "_SERVER_LOG = os.path.join"):
        print("  [2] логирование — уже есть")
        return text
    if SETUP_OLD not in text:
        print("  [2] НЕ НАЙДЕН BASE_DIR")
        return text
    text = text.replace(SETUP_OLD, SETUP_NEW, 1)
    print("  [2] настройка логирования + Tee stdout/stderr")
    return text


def patch_watchdog(text: str) -> str:
    if _already(text, "Watchdog: heartbeat отсутствует"):
        print("  [3] watchdog — уже логирует")
        return text
    if WD_OLD not in text:
        print("  [3] НЕ НАЙДЕН _beat_watchdog (старая версия)")
        return text
    text = text.replace(WD_OLD, WD_NEW, 1)
    print("  [3] watchdog пишет причину в лог")
    return text


def patch_start(text: str) -> str:
    if _already(text, "Сервер стартует. app.py="):
        print("  [4] старт — уже логируется")
        return text
    if START_OLD not in text:
        print("  [4] НЕ НАЙДЕН блок __main__")
        return text
    text = text.replace(START_OLD, START_NEW, 1)
    print("  [4] старт приложения логируется")
    return text


def main() -> int:
    print("fix_27: логирование сервера")
    print("=" * 60)

    if not APP_PY.exists():
        print(f"НЕ НАЙДЕН: {APP_PY.relative_to(BASE)}")
        return 1

    text = APP_PY.read_text(encoding="utf-8")
    original = text

    text = patch_imports(text)
    text = patch_setup(text)
    text = patch_watchdog(text)
    text = patch_start(text)

    if text == original:
        print("\nНичего не изменено — либо уже применено, либо структура")
        print("app.py отличается от ожидаемой. Откройте файл вручную и")
        print("проверьте наличие строк '_SERVER_LOG' и 'RotatingFileHandler'.")
        return 1

    APP_PY.write_text(text, encoding="utf-8")
    print()
    print(f"ИЗМЕНЁН: {APP_PY.relative_to(BASE)}")
    print()
    print("Готово.")
    print()
    print("Перезапустите сервер:")
    print("  1) Закройте окно-пульт (с остановкой сервера), или Ctrl+C.")
    print("  2) Запустите заново:")
    print("     .venv\\Scripts\\python.exe court_case_app\\app.py")
    print()
    print("После старта появятся файлы:")
    print("  court_case_app\\server_errors.log   — ошибки и watchdog")
    print("  court_case_app\\server_console.log  — stdout werkzeug и print")
    return 0


if __name__ == "__main__":
    sys.exit(main())