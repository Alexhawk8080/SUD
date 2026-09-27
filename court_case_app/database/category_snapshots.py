# -*- coding: utf-8 -*-
"""
CRUD для category_check_snapshots / category_check_problems (stage16d3c).

Снимок — история проверок категорий для конкретной версии исходного файла.
Хранится N последних (N из settings.category_snapshot_limit, по умолчанию 5).
Ротация — автоматически при создании нового снимка.

Исправления пользователя в снимке НЕ хранятся: они идут в cases.category.

Публичный API:
    save_category_snapshot, get_category_snapshot,
    list_category_snapshots, delete_category_snapshot,
    list_category_problems, get_snapshot_limit, set_snapshot_limit.
"""

import json as _json

_DEFAULT_LIMIT = 5

_SNAP_COLS = "id, source_file_id, stats_json, created_at"
_PROB_COLS = (
    "id, snapshot_id, case_id, case_number, applicants, "
    "current_category, suggested, source, options_json"
)


def _snapshot_to_dict(r) -> dict:
    try:
        stats = _json.loads(r[2]) if r[2] else {}
    except Exception:  # noqa: BLE001
        stats = {}
    return {
        "id": r[0], "source_file_id": r[1], "stats": stats,
        "created_at": r[3],
    }


def _problem_to_dict(r) -> dict:
    try:
        options = _json.loads(r[8]) if r[8] else []
    except Exception:  # noqa: BLE001
        options = []
    return {
        "id": r[0], "snapshot_id": r[1], "case_id": r[2],
        "case_number": r[3], "applicants": r[4],
        "current_category": r[5], "suggested": r[6],
        "source": r[7] or None, "options": options,
    }


# ---------------------------------------------------------------------------
# Настройка «сколько снимков хранить»
# ---------------------------------------------------------------------------

def get_snapshot_limit(conn) -> int:
    """N из settings.category_snapshot_limit. По умолчанию 5."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key='category_snapshot_limit'"
    ).fetchone()
    if not row or not row[0]:
        return _DEFAULT_LIMIT
    try:
        n = int(row[0])
        return n if n > 0 else _DEFAULT_LIMIT
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT


def set_snapshot_limit(conn, n: int) -> None:
    if n <= 0:
        raise ValueError("Лимит снимков должен быть > 0")
    conn.execute(
        "INSERT INTO settings (key, value) "
        "VALUES ('category_snapshot_limit', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(int(n)),))
    conn.commit()


# ---------------------------------------------------------------------------
# Снимок
# ---------------------------------------------------------------------------

def save_category_snapshot(conn, source_file_id: int,
                           problems: list, stats: dict = None) -> int:
    """
    Сохраняет снимок + проблемные дела. Автоматически ротирует:
    удаляет старые снимки того же source_file_id, если их стало > N.

    problems — список dict с полями:
        case_id, case_number, applicants, current_category,
        suggested, source, options (list).
    """
    if not conn.execute(
            "SELECT 1 FROM source_files WHERE id = ?", (source_file_id,)
    ).fetchone():
        raise ValueError(f"source_files id={source_file_id} не найден")

    stats_json = _json.dumps(stats or {}, ensure_ascii=False)
    cur = conn.execute(
        "INSERT INTO category_check_snapshots (source_file_id, stats_json) "
        "VALUES (?, ?)",
        (source_file_id, stats_json))
    snap_id = cur.lastrowid

    to_insert = []
    for p in problems or []:
        options = p.get("options") or []
        to_insert.append((
            snap_id,
            p.get("case_id"),
            str(p.get("case_number") or ""),
            str(p.get("applicants") or ""),
            str(p.get("current_category") or ""),
            str(p.get("suggested") or ""),
            str(p.get("source") or ""),
            _json.dumps(options, ensure_ascii=False),
        ))
    if to_insert:
        conn.executemany(
            "INSERT INTO category_check_problems ("
            "snapshot_id, case_id, case_number, applicants, "
            "current_category, suggested, source, options_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            to_insert)
    conn.commit()

    # Ротация: оставляем N последних
    _rotate(conn, source_file_id)
    return snap_id


def _rotate(conn, source_file_id: int) -> int:
    """Удаляет старые снимки, оставляя N последних. Возвращает число удалённых."""
    limit = get_snapshot_limit(conn)
    rows = conn.execute(
        "SELECT id FROM category_check_snapshots "
        "WHERE source_file_id = ? ORDER BY created_at DESC, id DESC",
        (source_file_id,)).fetchall()
    if len(rows) <= limit:
        return 0
    to_delete = [r[0] for r in rows[limit:]]
    q = ",".join("?" * len(to_delete))
    cur = conn.execute(
        f"DELETE FROM category_check_snapshots WHERE id IN ({q})",
        to_delete)
    conn.commit()
    return cur.rowcount or 0


def get_category_snapshot(conn, snapshot_id: int):
    r = conn.execute(
        f"SELECT {_SNAP_COLS} FROM category_check_snapshots WHERE id = ?",
        (snapshot_id,)).fetchone()
    return _snapshot_to_dict(r) if r else None


def list_category_snapshots(conn, source_file_id: int) -> list:
    """Снимки файла, свежие — первыми."""
    sql = f"SELECT {_SNAP_COLS} FROM category_check_snapshots " \
          "WHERE source_file_id = ? ORDER BY created_at DESC, id DESC"
    return [_snapshot_to_dict(r) for r in conn.execute(sql, (source_file_id,))]


def delete_category_snapshot(conn, snapshot_id: int) -> None:
    conn.execute("DELETE FROM category_check_snapshots WHERE id = ?",
                 (snapshot_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Проблемные дела снимка
# ---------------------------------------------------------------------------

def list_category_problems(conn, snapshot_id: int) -> list:
    sql = f"SELECT {_PROB_COLS} FROM category_check_problems " \
          "WHERE snapshot_id = ? ORDER BY id"
    return [_problem_to_dict(r) for r in conn.execute(sql, (snapshot_id,))]
