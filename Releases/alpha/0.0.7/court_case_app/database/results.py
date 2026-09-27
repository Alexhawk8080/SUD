# -*- coding: utf-8 -*-
"""
CRUD для processing_results / processing_result_rows (stage16d3a).

Результат обработки привязан к паре (court_year_id, case_type).
При повторной обработке перезаписывается (полная замена).

Публичный API:
    save_processing_result, get_processing_result,
    get_processing_result_by_pair, list_processing_results,
    delete_processing_result, set_result_stale,
    list_result_rows, add_result_rows_bulk, count_result_rows.
"""

import json as _json


_RESULT_COLS = (
    "id, court_year_id, case_type, source_file_id, output_format, "
    "processed_at, record_count, stats_json, process_alimony, "
    "target_year, court_area_id, is_stale, created_at"
)
_ROW_COLS = (
    "id, result_id, row_index, sequential, title, dates, opis, unit, "
    "count, retention, note, case_number, case_id, created_at"
)


def _result_row_to_dict(r) -> dict:
    try:
        stats = _json.loads(r[7]) if r[7] else {}
    except Exception:  # noqa: BLE001
        stats = {}
    return {
        "id": r[0], "court_year_id": r[1], "case_type": r[2],
        "source_file_id": r[3], "output_format": r[4],
        "processed_at": r[5], "record_count": r[6], "stats": stats,
        "process_alimony": bool(r[8]), "target_year": r[9],
        "court_area_id": r[10], "is_stale": bool(r[11]),
        "created_at": r[12],
    }


def _row_to_dict(r) -> dict:
    return {
        "id": r[0], "result_id": r[1], "row_index": r[2],
        "sequential": r[3], "title": r[4], "dates": r[5],
        "opis": r[6], "unit": r[7], "count": r[8],
        "retention": r[9], "note": r[10], "case_number": r[11],
        "case_id": r[12], "created_at": r[13],
    }


# ---------------------------------------------------------------------------
# Шапка результата
# ---------------------------------------------------------------------------

def save_processing_result(conn, court_year_id: int, case_type: str,
                           records: list, *, stats: dict = None,
                           source_file_id: int = None,
                           output_format: str = "word",
                           process_alimony: bool = False,
                           target_year: int = 0,
                           court_area_id: int = None) -> int:
    """
    Сохраняет результат. Полная замена: старая запись для пары
    (court_year_id, case_type) удаляется, создаётся новая + строки.

    Возвращает id нового result.
    """
    if case_type not in ("civil", "admin"):
        raise ValueError("case_type должен быть 'civil' или 'admin'")
    if not conn.execute(
            "SELECT 1 FROM court_years WHERE id = ?", (court_year_id,)
    ).fetchone():
        raise ValueError(f"Год id={court_year_id} не найден")

    # Полная замена
    old = conn.execute(
        "SELECT id FROM processing_results "
        "WHERE court_year_id = ? AND case_type = ?",
        (court_year_id, case_type)).fetchone()
    if old:
        conn.execute("DELETE FROM processing_results WHERE id = ?", (old[0],))

    stats_json = _json.dumps(stats or {}, ensure_ascii=False)
    count_records = sum(1 for r in records
                        if str(r.get("title") or "").strip())

    cur = conn.execute(
        "INSERT INTO processing_results ("
        "court_year_id, case_type, source_file_id, output_format, "
        "record_count, stats_json, process_alimony, target_year, "
        "court_area_id, is_stale) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
        (court_year_id, case_type, source_file_id, output_format,
         count_records, stats_json, 1 if process_alimony else 0,
         int(target_year or 0), court_area_id))
    result_id = cur.lastrowid

    # Строки
    rows = []
    for i, r in enumerate(records, start=1):
        rows.append((
            result_id,
            int(r.get("row_index") or i),
            str(r.get("sequential") or ""),
            str(r.get("title") or ""),
            str(r.get("dates") or ""),
            str(r.get("opis") or ""),
            str(r.get("unit") or ""),
            str(r.get("count") or ""),
            str(r.get("retention") or ""),
            str(r.get("note") or ""),
            str(r.get("case_number") or ""),
            r.get("case_id"),
        ))
    if rows:
        conn.executemany(
            "INSERT INTO processing_result_rows ("
            "result_id, row_index, sequential, title, dates, opis, "
            "unit, count, retention, note, case_number, case_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows)
    conn.commit()
    return result_id


def get_processing_result(conn, result_id: int):
    r = conn.execute(
        f"SELECT {_RESULT_COLS} FROM processing_results WHERE id = ?",
        (result_id,)).fetchone()
    return _result_row_to_dict(r) if r else None


def get_processing_result_by_pair(conn, court_year_id: int, case_type: str):
    r = conn.execute(
        f"SELECT {_RESULT_COLS} FROM processing_results "
        "WHERE court_year_id = ? AND case_type = ?",
        (court_year_id, case_type)).fetchone()
    return _result_row_to_dict(r) if r else None


def list_processing_results(conn, court_year_id: int = None) -> list:
    sql = f"SELECT {_RESULT_COLS} FROM processing_results"
    params = []
    if court_year_id is not None:
        sql += " WHERE court_year_id = ?"
        params.append(court_year_id)
    sql += " ORDER BY court_year_id, case_type"
    return [_result_row_to_dict(r) for r in conn.execute(sql, params)]


def delete_processing_result(conn, result_id: int) -> None:
    conn.execute("DELETE FROM processing_results WHERE id = ?", (result_id,))
    conn.commit()


def set_result_stale(conn, result_id: int, is_stale: bool = True) -> None:
    conn.execute(
        "UPDATE processing_results SET is_stale = ? WHERE id = ?",
        (1 if is_stale else 0, result_id))
    conn.commit()


# ---------------------------------------------------------------------------
# Строки результата
# ---------------------------------------------------------------------------

def list_result_rows(conn, result_id: int) -> list:
    sql = f"SELECT {_ROW_COLS} FROM processing_result_rows " \
          "WHERE result_id = ? ORDER BY row_index, id"
    return [_row_to_dict(r) for r in conn.execute(sql, (result_id,))]


def add_result_rows_bulk(conn, result_id: int, rows: list) -> int:
    """Дописать строки к существующему результату."""
    if not get_processing_result(conn, result_id):
        raise ValueError(f"processing_results id={result_id} не найден")
    to_insert = []
    for i, r in enumerate(rows, start=1):
        to_insert.append((
            result_id,
            int(r.get("row_index") or i),
            str(r.get("sequential") or ""),
            str(r.get("title") or ""),
            str(r.get("dates") or ""),
            str(r.get("opis") or ""),
            str(r.get("unit") or ""),
            str(r.get("count") or ""),
            str(r.get("retention") or ""),
            str(r.get("note") or ""),
            str(r.get("case_number") or ""),
            r.get("case_id"),
        ))
    if not to_insert:
        return 0
    conn.executemany(
        "INSERT INTO processing_result_rows ("
        "result_id, row_index, sequential, title, dates, opis, unit, "
        "count, retention, note, case_number, case_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        to_insert)
    conn.commit()
    return len(to_insert)


def count_result_rows(conn, result_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM processing_result_rows WHERE result_id = ?",
        (result_id,)).fetchone()[0]
