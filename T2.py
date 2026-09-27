# -*- coding: utf-8 -*-
"""
release_0_0_7_generate.py — снимок релиза 0.0.7-alpha.

Создаёт Releases/alpha/0.0.7/ с актуальным состоянием проекта
(launcher, watchdog parent-mode, логирование, единый формат имён).

Запуск:
    .venv\\Scripts\\python.exe release_0_0_7_generate.py
    .venv\\Scripts\\python.exe release_0_0_7_generate.py --force
"""

import argparse
import os
import shutil
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent

RELEASES_DIRNAME = "Releases"
CHANNEL = "alpha"
VERSION = "0.0.7"
TAG = f"{VERSION}-{CHANNEL}"

INCLUDE_ROOT_FILES = [
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "conftest.py",
    "run_tests.py",
    "setup_env.py",
    "migrate_db_v2.py",
    "README.md",
    "Plan.md",
    "context.md",
    "launcher.py",
    "start.bat",
    "run_app.pyw",
]

INCLUDE_ROOT_GLOBS = ["stage*.py", "fix_*.py", "release_*.py"]

INCLUDE_DIRS = [".vscode", "court_case_app"]

EXCLUDE_NAMES = {
    ".venv", ".git", "__pycache__", ".pytest_cache", "coverage_html",
    ".mypy_cache", ".ruff_cache", "node_modules",
    "uploads", "output",
    "app.db", "app.db-wal", "app.db-shm",
    "$null", "server_test.log", "_release_errors.log",
    "TEST.LOG", "test.log", "test_error.log",
    "server_errors.log", "server_console.log",
    "2020 гр.xlsx",
}

EXCLUDE_SUFFIXES = (".log", ".pyc", ".pyo", ".tmp", ".bak")
EXCLUDE_NAMES_EXTRA = {".DS_Store", "Thumbs.db"}

COPY_ERRORS: list = []


def should_skip(path: Path) -> bool:
    name = path.name
    if name in EXCLUDE_NAMES or name in EXCLUDE_NAMES_EXTRA:
        return True
    if any(name.endswith(s) for s in EXCLUDE_SUFFIXES):
        return True
    return False


def win_long(path: Path) -> str:
    s = str(path.resolve())
    if os.name == "nt" and len(s) > 240 and not s.startswith("\\\\?\\"):
        if s.startswith("\\\\"):
            return "\\\\?\\UNC\\" + s[2:]
        return "\\\\?\\" + s
    return s


def safe_copy_file(src: Path, dst: Path) -> bool:
    try:
        if not src.exists():
            msg = f"  SKIP   нет источника: {src}"
            print(msg)
            COPY_ERRORS.append(msg)
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(win_long(src), win_long(dst))
        return True
    except OSError as exc:
        msg = (f"  ОШИБКА: {type(exc).__name__}: {exc}\n"
               f"          src: {src}\n"
               f"          dst: {dst}")
        print(msg)
        COPY_ERRORS.append(msg)
        return False


def copy_tree(src: Path, dst: Path):
    files = dirs = 0
    try:
        items = list(src.iterdir())
    except OSError as exc:
        print(f"  ОШИБКА чтения {src}: {exc}")
        COPY_ERRORS.append(str(exc))
        return 0, 0
    for item in items:
        if should_skip(item):
            continue
        target = dst / item.name
        try:
            is_dir = item.is_dir()
        except OSError:
            continue
        if is_dir:
            try:
                target.mkdir(parents=True, exist_ok=True)
                dirs += 1
            except OSError:
                continue
            f, d = copy_tree(item, target)
            files += f
            dirs += d
        else:
            if safe_copy_file(item, target):
                files += 1
    return files, dirs


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_readme(tag, fcount, dcount):
    today = date.today().strftime("%Y-%m-%d")
    return f"""# Акт уничтожения гражданских дел — релиз {tag}

**Дата сборки:** {today}
**Канал:** {CHANNEL}
**Версия:** {VERSION}

## О релизе

Стабилизация после крупной переработки БД (0.0.6): добавлен **launcher** —
окно-пульт управления сервером, логирование в файлы, **watchdog в
parent-mode** (сервер живёт без вкладки, пока открыт launcher), единый
формат имени файла акта, устойчивые тесты.

## Новое в 0.0.7

- **launcher.py** (окно-пульт): статус 🟢/🟡/🔴, кнопки
  «Открыть в браузере» / «Перезапустить» / «Остановить» / «Открыть логи»,
  живой лог, автостоп при закрытии, `CREATE_NO_WINDOW` для дочернего
  процесса.
- **Логирование сервера**: `server_errors.log` (исключения + watchdog),
  `server_console.log` (stdout werkzeug и print).
- **Watchdog parent-mode** (`fix_32`): при запуске из launcher
  heartbeat-watchdog отключается, вместо него — проверка живости
  родителя раз в 2 с. Сервер не умирает без вкладки, но завершается
  вместе с окном-пультом.
- **Единый формат имени файла** (`core/filename_utils.py`):
  «Акт уничтожения гражданских дел 3 CУ 2020.docx».
  `year_page.js::parseContentDisposition` читает `filename*` (UTF-8) из
  Content-Disposition.
- **UI создания участка/года**: кнопка «+ Участок» в сайдбаре,
  hover-кнопка «+» у каждого участка, модалка с опцией «скопировать
  реквизиты из [год]».
- **Стабилизация**: import logging, base-leftovers, устойчивые тесты.

## Быстрый старт

    python setup_env.py
    .venv\\Scripts\\python.exe run_tests.py     # 51 модуль
    .venv\\Scripts\\python.exe court_case_app\\app.py

**Или через окно-пульт** (двойной клик):
    start.bat
    run_app.pyw

## Миграция со старой версии

Если у вас БД от 0.0.5 или раньше:

    .venv\\Scripts\\python.exe migrate_db_v2.py

## Что НЕ включено

- `.venv/`, `app.db`, `uploads/`, `output/` — создаются автоматически
- Логи (`server_errors.log`, `server_console.log`) — создаются при старте
- Личные файлы (исходные `.xlsx`)

Статистика: {fcount} файлов, {dcount} папок.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Снимок релиза 0.0.7-alpha.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    release_root = BASE / RELEASES_DIRNAME / CHANNEL / VERSION
    print(f"Релиз: {TAG}")
    print(f"Папка: {release_root}")
    print("=" * 64)

    if release_root.exists():
        if not args.force:
            print(f"Папка уже существует: {release_root}")
            print("Используйте --force для перезаписи.")
            return 1
        print("Удаление старого снимка...")
        shutil.rmtree(win_long(release_root))

    release_root.mkdir(parents=True, exist_ok=True)

    print("\n[1] Файлы корня")
    files = dirs = 0
    for name in INCLUDE_ROOT_FILES:
        src = BASE / name
        if not src.exists():
            print(f"  SKIP   {name}  (нет файла)")
            continue
        if safe_copy_file(src, release_root / name):
            files += 1
            print(f"  COPY   {name}")

    for pattern in INCLUDE_ROOT_GLOBS:
        for src in sorted(BASE.glob(pattern)):
            if not src.is_file() or should_skip(src):
                continue
            if safe_copy_file(src, release_root / src.name):
                files += 1

    print("\n[2] Деревья")
    for name in INCLUDE_DIRS:
        src = BASE / name
        if not src.exists():
            print(f"  SKIP   {name}/  (нет папки)")
            continue
        f, d = copy_tree(src, release_root / name)
        files += f
        dirs += d
        print(f"  COPY   {name}/  ({f} файлов, {d} папок)")

    print("\n[3] Метаданные релиза")
    write_file(release_root / "VERSION", TAG + "\n")
    print(f"  CREATE VERSION ({TAG})")
    write_file(release_root / "README.md", make_readme(TAG, files, dirs))
    print("  CREATE README.md")

    changelog = f"""# История изменений

## {TAG} — {date.today().strftime('%Y-%m-%d')}

- launcher.py — окно-пульт управления сервером (tkinter)
- Логирование: server_errors.log + server_console.log
- Watchdog parent-mode (env NO_WATCHDOG + PARENT_PID)
- Единый формат имени файла (core/filename_utils.py)
- UI создания участка/года из сайдбара
- Стабилизация: import logging, base-leftovers, устойчивые тесты
- Тесты: 51 модуль, все OK
"""
    write_file(release_root / "CHANGELOG.md", changelog)
    print("  CREATE CHANGELOG.md")

    if COPY_ERRORS:
        log_path = BASE / "_release_errors.log"
        log_path.write_text("\n".join(COPY_ERRORS) + "\n", encoding="utf-8")
        print(f"\nОШИБКИ копирования: {len(COPY_ERRORS)}  "
              f"(см. {log_path.name})")

    print()
    print("=" * 64)
    print(f"ГОТОВО: {release_root}")
    print(f"Файлов скопировано: {files}")
    size = sum(f.stat().st_size for f in release_root.rglob("*")
               if f.is_file())
    print(f"Размер: {size / 1024:.1f} КБ")
    if COPY_ERRORS:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())git status