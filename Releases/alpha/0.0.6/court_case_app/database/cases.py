# -*- coding: utf-8 -*-
"""
CRUD для source_files и cases (stage16d2).

Версии файлов (source_files) и разобранные дела (cases) — изолированные
сущности, работающие только с соединением SQLite. Этот модуль не зависит
от database.db (никаких циклических импортов).

Публичный API:
    # source_files
    save_source_file, list_source_files, get_source_file,
    get_source_file_content, get_current_source_file,
    set_current_source_file, delete_source_file, count_source_files,

    # cases
    add_cases_bulk, list_cases, get_case, delete_cases_for_source,
    count_cases_for_source, case_types_in_year.
"""

import json as _json


# ---------------------------------------------------------------------------
# source_files
# ---------------------------------------------------------------------------

def save_source_file(conn, court_year_id: int, filename: str, content: bytes,
                     *, file_kind: str = "source", sheet_name: str = "",
                     header_row: int = 0, mapping: dict = None,
                     row_count: int = 0) -> int:
    """
    Сохраняет файл как новую версию для года.

    Автоматически:
      * version = max(version) + 1 для пары (court_year_id, file_kind);
      * снимает is_current со всех предыдущих версий той же пары
        и ставит is_current=1 новой версии.

    Возвращает id новой записи.
    """
    if file_kind not in ("source", "processed"):
        raise ValueError("file_kind должен быть 'source' или 'processed'")

    # Год должен существовать (прямой SQL, без зависимости от db.py)
    if not conn.execute(
            "SELECT 1 FROM court_years WHERE id = ?", (court_year_id,)
    ).fetchone():
        raise ValueError(f"Год id={court_year_id} не найден")

    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) FROM source_files "
        "WHERE court_year_id = ? AND file_kind = ?",
        (court_year_id, file_kind)).fetchone()
    next_version = int(row[0]) + 1

    conn.execute(
        "UPDATE source_files SET is_current = 0 "
        "WHERE court_year_id = ? AND file_kind = ?",
        (court_year_id, file_kind))

    mapping_json = _json.dumps(mapping or {}, ensure_ascii=False)

    cur = conn.execute(
        "INSERT INTO source_files ("
        "court_year_id, version, filename, content, file_kind, "
        "sheet_name, header_row, mapping_json, row_count, is_current) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (court_year_id, next_version, filename, content, file_kind,
         sheet_name, int(header_row), mapping_json, int(row_count)))
    conn.commit()
    return cur.lastrowid


def _sf_row_to_dict(r, with_content=False) -> dict:
    base = {
        "id": r[0], "court_year_id": r[1], "version": r[2],
        "filename": r[3], "file_kind": r[4], "sheet_name": r[5],
        "header_row": r[6], "row_count": r[7],
        "is_current": bool(r[8]), "imported_at": r[9],
    }
    try:
        base["mapping"] = _json.loads(r[10]) if r[10] else {}
    except Exception:  # noqa: BLE001
        base["mapping"] = {}
    if with_content:
        base["content"] = r[11]
    return base


_SF_COLS_NO_CONTENT = (
    "id, court_year_id, version, filename, file_kind, sheet_name, "
    "header_row, row_count, is_current, imported_at, mapping_json"
)
_SF_COLS_WITH_CONTENT = _SF_COLS_NO_CONTENT + ", content"


def list_source_files(conn, court_year_id: int = None,
                      file_kind: str = None) -> list:
    """Список версий (без BLOB). Сортировка: год, kind, version DESC."""
    sql = f"SELECT {_SF_COLS_NO_CONTENT} FROM source_files"
    where = []
    params = []
    if court_year_id is not None:
        where.append("court_year_id = ?")
        params.append(court_year_id)
    if file_kind:
        where.append("file_kind = ?")
        params.append(file_kind)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY court_year_id, file_kind, version DESC"
    return [_sf_row_to_dict(r) for r in conn.execute(sql, params)]


def get_source_file(conn, file_id: int):
    """Запись без BLOB, или None."""
    r = conn.execute(
        f"SELECT {_SF_COLS_NO_CONTENT} FROM source_files WHERE id = ?",
        (file_id,)).fetchone()
    return _sf_row_to_dict(r) if r else None


def get_source_file_content(conn, file_id: int):
    """Содержимое файла (bytes) или None."""
    r = conn.execute(
        "SELECT content FROM source_files WHERE id = ?",
        (file_id,)).fetchone()
    return r[0] if r else None


def get_current_source_file(conn, court_year_id: int,
                            file_kind: str = "source"):
    """Актуальная (is_current=1) версия или None."""
    r = conn.execute(
        f"SELECT {_SF_COLS_NO_CONTENT} FROM source_files "
        "WHERE court_year_id = ? AND file_kind = ? AND is_current = 1 "
        "LIMIT 1",
        (court_year_id, file_kind)).fetchone()
    return _sf_row_to_dict(r) if r else None


def set_current_source_file(conn, file_id: int) -> bool:
    """
    Делает указанную версию актуальной для её (год, kind).
    Возвращает True, если запись найдена.
    """
    r = conn.execute(
        "SELECT court_year_id, file_kind FROM source_files WHERE id = ?",
        (file_id,)).fetchone()
    if not r:
        return False
    year_id, kind = r[0], r[1]
    conn.execute(
        "UPDATE source_files SET is_current = 0 "
        "WHERE court_year_id = ? AND file_kind = ?",
        (year_id, kind))
    conn.execute(
        "UPDATE source_files SET is_current = 1 WHERE id = ?",
        (file_id,))
    conn.commit()
    return True


def delete_source_file(conn, file_id: int) -> None:
    """Удаляет файл; связанные дела уходят каскадом (FK ON DELETE CASCADE)."""
    conn.execute("DELETE FROM source_files WHERE id = ?", (file_id,))
    conn.commit()


def count_source_files(conn, court_year_id: int = None) -> int:
    if court_year_id is None:
        return conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
    return conn.execute(
        "SELECT COUNT(*) FROM source_files WHERE court_year_id = ?",
        (court_year_id,)).fetchone()[0]


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

_CASE_COLS = (
    "id, source_file_id, case_type, row_index, "
    "date, case_number, applicants, respondents, category, "
    "opis_number, unit_number, note, end_date, "
    "is_problematic, is_alimony, is_valid, skip_reason, created_at"
)


def _case_row_to_dict(r) -> dict:
    return {
        "id": r[0], "source_file_id": r[1], "case_type": r[2],
        "row_index": r[3],
        "date": r[4], "case_number": r[5], "applicants": r[6],
        "respondents": r[7], "category": r[8],
        "opis_number": r[9], "unit_number": r[10], "note": r[11],
        "end_date": r[12],
        "is_problematic": bool(r[13]), "is_alimony": bool(r[14]),
        "is_valid": bool(r[15]), "skip_reason": r[16],
        "created_at": r[17],
    }


def add_cases_bulk(conn, source_file_id: int, cases: list) -> int:
    """
    Массовая вставка дел. cases — список dict с полями:
        case_type, row_index, date, case_number, applicants, respondents,
        category, opis_number, unit_number, note, end_date,
        is_problematic, is_alimony, is_valid, skip_reason.
    Возвращает количество вставленных записей.
    """
    if not get_source_file(conn, source_file_id):
        raise ValueError(f"source_files id={source_file_id} не найден")

    rows = []
    for c in cases or []:
        rows.append((
            source_file_id,
            str(c.get("case_type") or "civil"),
            int(c.get("row_index") or 0),
            str(c.get("date") or ""),
            str(c.get("case_number") or ""),
            str(c.get("applicants") or ""),
            str(c.get("respondents") or ""),
            str(c.get("category") or ""),
            str(c.get("opis_number") or ""),
            str(c.get("unit_number") or ""),
            str(c.get("note") or ""),
            str(c.get("end_date") or ""),
            1 if c.get("is_problematic") else 0,
            1 if c.get("is_alimony") else 0,
            1 if c.get("is_valid") else 0,
            str(c.get("skip_reason") or ""),
        ))

    if not rows:
        return 0

    conn.executemany(
        "INSERT INTO cases ("
        "source_file_id, case_type, row_index, "
        "date, case_number, applicants, respondents, category, "
        "opis_number, unit_number, note, end_date, "
        "is_problematic, is_alimony, is_valid, skip_reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows)
    conn.commit()
    return len(rows)


def list_cases(conn, source_file_id: int = None, case_type: str = None) -> list:
    sql = f"SELECT {_CASE_COLS} FROM cases"
    where = []
    params = []
    if source_file_id is not None:
        where.append("source_file_id = ?")
        params.append(source_file_id)
    if case_type:
        where.append("case_type = ?")
        params.append(case_type)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY source_file_id, row_index, id"
    return [_case_row_to_dict(r) for r in conn.execute(sql, params)]


def get_case(conn, case_id: int):
    r = conn.execute(
        f"SELECT {_CASE_COLS} FROM cases WHERE id = ?",
        (case_id,)).fetchone()
    return _case_row_to_dict(r) if r else None


def delete_cases_for_source(conn, source_file_id: int) -> int:
    """Удаляет все дела конкретной версии файла. Возвращает число удалённых."""
    cur = conn.execute(
        "DELETE FROM cases WHERE source_file_id = ?", (source_file_id,))
    conn.commit()
    return cur.rowcount or 0


def count_cases_for_source(conn, source_file_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM cases WHERE source_file_id = ?",
        (source_file_id,)).fetchone()[0]


def case_types_in_year(conn, court_year_id: int) -> list:
    """
    Список case_type, для которых в году есть дела (по всем версиям).
    """
    sql = (
        "SELECT DISTINCT c.case_type FROM cases c "
        "JOIN source_files sf ON sf.id = c.source_file_id "
        "WHERE sf.court_year_id = ? ORDER BY c.case_type"
    )
    return [r[0] for r in conn.execute(sql, (court_year_id,))]
