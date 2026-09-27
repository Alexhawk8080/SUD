# -*- coding: utf-8 -*-
"""
migrate_db_v2.py — миграция старой схемы БД (v1) в схему v2.

Порядок действий:
    1. Проверяет schema_version. Если v2 — сообщает и завершается.
    2. Бэкап: app.db -> app.db.bak-YYYYMMDD-HHMMSS (в той же папке).
    3. Читает старую court_areas (9 полей) в память.
    4. DROP старой court_areas.
    5. Создаёт полную схему v2 (через db.init_db после удаления v1-маркеров).
    6. Переносит: номер -> court_areas (name/address/note = "").
    7. Переносит 8 реквизитов -> court_years за 2019 год.
    8. Удаляет 9 legacy-ключей из settings (судебный_участок, судья, ...).
    9. Ставит schema_version = 'v2'.

Использование:
    .venv\Scripts\python.exe migrate_db_v2.py
    .venv\Scripts\python.exe migrate_db_v2.py --force
    .venv\Scripts\python.exe migrate_db_v2.py --db-path путь\\к\\app.db
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
DEFAULT_DB = BASE / "court_case_app" / "database" / "app.db"

# 8 реквизитов, которые раньше жили в court_areas и переезжают в court_years
_REF_FIELDS = (
    "судья", "секретарь", "дата_утверждения", "дата_акта",
    "номер_акта", "дата_подписи", "протокол_эк_дата",
    "протокол_эк_номер",
)
# Все legacy-ключи settings (включая номер участка) — удаляются
_LEGACY_SETTINGS_KEYS = ("судебный_участок",) + _REF_FIELDS
# Год, к которому приписываем старые реквизиты
_LEGACY_YEAR = 2019


def _backup(db_path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_suffix(db_path.suffix + f".bak-{ts}")
    shutil.copy2(db_path, backup)
    return backup


def _detect_version(conn) -> str:
    has_settings = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
    ).fetchone()
    if not has_settings:
        return "empty"
    row = conn.execute(
        "SELECT value FROM settings WHERE key='schema_version'"
    ).fetchone()
    if row and row[0] == "v2":
        return "v2"
    has_years = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='court_years'"
    ).fetchone()
    return "v2" if has_years else "v1"


def _read_old_court_areas(conn) -> list:
    """Возвращает список dict со старыми 9 полями court_areas."""
    try:
        cur = conn.execute(
            "SELECT id, номер, судья, секретарь, дата_утверждения, "
            "дата_акта, номер_акта, дата_подписи, "
            "протокол_эк_дата, протокол_эк_номер "
            "FROM court_areas ORDER BY id")
    except sqlite3.OperationalError:
        return []  # таблицы нет — нечего мигрировать
    rows = cur.fetchall()
    return [{
        "id": r[0], "номер": r[1] or "",
        "судья": r[2] or "", "секретарь": r[3] or "",
        "дата_утверждения": r[4] or "", "дата_акта": r[5] or "",
        "номер_акта": r[6] or "", "дата_подписи": r[7] or "",
        "протокол_эк_дата": r[8] or "", "протокол_эк_номер": r[9] or "",
    } for r in rows]


def _drop_old_court_areas(conn) -> None:
    try:
        conn.execute("DROP TABLE court_areas")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # уже нет


def _apply_v2_schema(conn) -> None:
    """
    Создаёт полную схему v2. Импортируем _SCHEMA из database.db
    (только как строку, без открытия соединения).
    """
    sys.path.insert(0, str(BASE / "court_case_app"))
    from database.db import _SCHEMA  # noqa: PLC0415
    conn.executescript(_SCHEMA)
    conn.commit()


def _insert_new_court_area(conn, номер: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO court_areas (номер) VALUES (?)",
        (номер,))
    conn.commit()
    row = conn.execute(
        "SELECT id FROM court_areas WHERE номер = ?", (номер,)
    ).fetchone()
    return row[0]


def _insert_court_year(conn, area_id: int, year: int, refs: dict) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO court_years ("
        "court_area_id, year, судья, секретарь, дата_утверждения, "
        "дата_акта, номер_акта, дата_подписи, протокол_эк_дата, "
        "протокол_эк_номер, is_incomplete, is_closed) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
        (area_id, year,
         refs.get("судья", ""), refs.get("секретарь", ""),
         refs.get("дата_утверждения", ""), refs.get("дата_акта", ""),
         refs.get("номер_акта", ""), refs.get("дата_подписи", ""),
         refs.get("протокол_эк_дата", ""), refs.get("протокол_эк_номер", ""),
         0 if all(refs.get(f) for f in _REF_FIELDS) else 1))
    conn.commit()


def _drop_legacy_settings(conn) -> int:
    q = ",".join("?" * len(_LEGACY_SETTINGS_KEYS))
    cur = conn.execute(
        f"DELETE FROM settings WHERE key IN ({q})",
        _LEGACY_SETTINGS_KEYS)
    conn.commit()
    return cur.rowcount or 0


def _set_schema_version_v2(conn) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('schema_version', 'v2') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value")
    conn.commit()


def migrate(db_path, force: bool = False) -> dict:
    """
    Программная миграция. Возвращает отчёт:
        {
          "status": "ok" | "already_v2" | "empty",
          "backup": "путь" | None,
          "court_areas_migrated": N,
          "years_created": M,
          "settings_deleted": K,
        }

    Бросает RuntimeError при проблеме (v1 + --force не указан).
    """
    path = Path(db_path).resolve()
    if not path.exists():
        return {"status": "empty", "backup": None,
                "court_areas_migrated": 0, "years_created": 0,
                "settings_deleted": 0}

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    version = _detect_version(conn)

    if version == "v2":
        conn.close()
        return {"status": "already_v2", "backup": None,
                "court_areas_migrated": 0, "years_created": 0,
                "settings_deleted": 0}

    # Бэкап
    backup_path = _backup(path)

    # Читаем старые данные
    old_areas = _read_old_court_areas(conn)

    # DROP старой таблицы
    _drop_old_court_areas(conn)

    # Схема v2 (создаст все таблицы, включая новые court_areas и court_years)
    _apply_v2_schema(conn)

    # Перенос
    years_created = 0
    for rec in old_areas:
        номер = (rec.get("номер") or "").strip()
        if not номер:
            continue
        area_id = _insert_new_court_area(conn, номер)
        _insert_court_year(conn, area_id, _LEGACY_YEAR, rec)
        years_created += 1

    # Чистка legacy settings
    deleted = _drop_legacy_settings(conn)

    # Версия
    _set_schema_version_v2(conn)

    conn.close()
    return {
        "status": "ok",
        "backup": str(backup_path),
        "court_areas_migrated": len(old_areas),
        "years_created": years_created,
        "settings_deleted": deleted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Миграция БД v1 -> v2.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB),
                        help="Путь к app.db")
    parser.add_argument("--force", action="store_true",
                        help="Принудительно, если схема уже v2")
    args = parser.parse_args()

    path = Path(args.db_path).resolve()
    print(f"migrate_db_v2: {path}")
    print("=" * 64)

    if path.exists():
        conn = sqlite3.connect(str(path))
        try:
            version = _detect_version(conn)
        finally:
            conn.close()
        if version == "v2" and not args.force:
            print("Схема уже v2. Ничего не делаем (--force для повтора).")
            return 0

    try:
        report = migrate(path, force=args.force)
    except Exception as exc:  # noqa: BLE001
        print(f"ОШИБКА: {exc}")
        return 1

    status = report["status"]
    if status == "empty":
        print("Файл БД не найден — миграция не требуется.")
        return 0
    if status == "already_v2":
        print("Схема уже v2. Ничего не делаем.")
        return 0

    print(f"Бэкап:              {report['backup']}")
    print(f"Перенесено участков: {report['court_areas_migrated']}")
    print(f"Создано годов:       {report['years_created']} "
          f"(год {_LEGACY_YEAR})")
    print(f"Удалено legacy-ключей settings: {report['settings_deleted']}")
    print()
    print("Готово. Запускайте приложение: "
          ".venv\\Scripts\\python.exe court_case_app\\app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
