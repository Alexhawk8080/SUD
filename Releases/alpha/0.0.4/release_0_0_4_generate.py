# -*- coding: utf-8 -*-
"""
release_0_0_4_generate.py — снимок релиза 0.0.4-alpha.

Создаёт Releases/alpha/0.0.2/ с актуальным состоянием проекта
(этапы A/B/C + fix_10_v2).

Особенности:
    - защита от длинных путей Windows (префикс \\\\?\\ для путей > 240);
    - обработка ошибок per-file (не падает на одном файле);
    - лог ошибок копирования в _release_errors.log.

Запуск (из корня проекта):
    .venv\\Scripts\\python.exe release_0_0_4_generate.py
    .venv\\Scripts\\python.exe release_0_0_4_generate.py --force
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
VERSION = "0.0.4"
TAG = f"{VERSION}-{CHANNEL}"

INCLUDE_ROOT_FILES = [
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "conftest.py",
    "run_tests.py",
    "setup_env.py",
    "Plan.md",
    "context.md",
]

INCLUDE_ROOT_GLOBS = ["stage*.py", "fix_*.py", "release_*.py"]

INCLUDE_DIRS = [".vscode", "court_case_app"]

EXCLUDE_NAMES = {
    ".venv", ".git", "__pycache__", ".pytest_cache", "coverage_html",
    ".mypy_cache", ".ruff_cache", "node_modules",
    "uploads", "output",
    "app.db", "app.db-wal", "app.db-shm",
    "$null", "server_test.log", "_release_errors.log", "TEST.LOG",
    "2020 гр.xlsx",
}

EXCLUDE_SUFFIXES = (".log", ".pyc", ".pyo", ".tmp")
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

Реализованы все три направления работы с документами:

1. **Обычная обработка** — из исходной таблицы дел.
2. **Excel <-> Word** — конвертация между «Результатом обработки»
   и Word-актом по шаблону.
3. **Справочник судебных участков** — полные реквизиты на каждый участок,
   используются при обычной обработке и при конвертации.
4. **Внутренняя опись** — конвертация Word-описи в лист «Таблица» Excel.

## Новое в 0.0.4

- **Доработка 7**: в режиме «готовый результат» (file_type=legacy)
  данные переносятся «как есть»: «Даты дела», «№ описи», «№ ед.хр.»,
  «Кол-во ед.хр.», «Срок хранения»; пустые остаются пустыми;
  предупреждение о неполноте данных убрано. Столбцы определяются по
  названиям заголовков, при невозможности — по позициям 3–6(7).

## Новое в 0.0.3

- **Модуль «Внутренняя опись»** (этапы 14a–14f): конвертер Word-описи
  (административные и гражданские дела) в лист «Таблица» Excel.
  Заполняются C, D, E, G, H и ячейка F4; формулы шаблона сохранены,
  добавляется лист «Требует внимания». Страница «Внутренняя опись»:
  шаблон .xlsx, несколько .docx, судебный участок, редактируемое имя.

## Новое в 0.0.2

- **Этап A**: `court_areas` (9 обязательных полей + `is_incomplete`),
  миграция из `settings` (двойное чтение), CRUD, API `/api/court_areas`,
  селект участка на странице обработки и на странице конвертации.
- **Этап B**: невидимые метки Word (`core_properties.keywords` + `comments`)
  и Excel (`wb.properties.keywords` + `description`) в формате
  `\\u200BACT-V1-COURT-CASE-APP\\u200B`; пакет `core/converter/`;
  страница «Конвертация» (Excel -> Word).
- **Этап C**: парсер Word-акта, страница «Конвертация» (Word -> Excel),
  умная нумерация, attention-строки, `restore_gaps`.
- **fix_10_v2**: `core/text_utils.sanitize_text` — `_x000D_`/`\\r`/`\\v` -> `\\n`
  на всех границах (Word / Excel / конвертация).

## Быстрый старт

    python setup_env.py
    .venv\\Scripts\\python.exe run_tests.py     # 24 модуля
    .venv\\Scripts\\python.exe court_case_app\\app.py

## Что НЕ включено

- `.venv/`, `app.db`, `uploads/`, `output/` — создаются автоматически
- Личные файлы пользователя (исходные .xlsx, логи)

Статистика: {fcount} файлов, {dcount} папок.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Снимок релиза 0.0.4-alpha.")
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
        print(f"Удаление старого снимка...")
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

- Этап A: справочник судебных участков (`court_areas`) + миграция
  из `settings` + CRUD + API + UI
- Этап B: Excel -> Word (метки, пакет `core/converter/`, роуты, UI)
- Этап C: Word -> Excel (парсер акта, роут, UI)
- Доработка 7: перенос данных из готового результата «как есть»
  (даты дела, № описи, № ед.хр., кол-во, срок хранения); предупреждение
  о неполноте данных убрано
- Этап 14: модуль «Внутренняя опись» (Word -> лист «Таблица»):
  `core/inventory/` (docx_reader, normalizer, case_number, flow,
  sheets_io, writer, api), страница «Внутренняя опись», фикстуры,
  регрессия
- fix_10_v2: `_x000D_` -> `\\n` на всех границах
- Тесты: 31 модуль, все OK
"""
    write_file(release_root / "CHANGELOG.md", changelog)
    print("  CREATE CHANGELOG.md")

    if COPY_ERRORS:
        log_path = BASE / "_release_errors.log"
        log_path.write_text("\n".join(COPY_ERRORS) + "\n", encoding="utf-8")
        print(f"\nОШИБКИ копирования: {len(COPY_ERRORS)}  (см. {log_path.name})")

    print()
    print("=" * 64)
    print(f"ГОТОВО: {release_root}")
    print(f"Файлов скопировано: {files}")
    size = sum(f.stat().st_size for f in release_root.rglob("*") if f.is_file())
    print(f"Размер: {size / 1024:.1f} КБ")
    if COPY_ERRORS:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())