# -*- coding: utf-8 -*-
"""
CRUD для processing_inventories / processing_inventory_rows (stage16d3b).

Опись привязана к акту (result_id) — одна на акт, при пересохранении
перезаписывается (полная замена).

Поля строки:
    sequence_number — № п/п
    title           — наименование и краткое содержание документа
    prefix          — префикс (2, 5, ...)
    case_number     — номер дела
    year            — год
    pages_count     — кол-во стр.
    sheet_numbers   — номера листов в наряде
    extra_json      — задел для будущих полей.

Публичный API:
    save_processing_inventory, get_processing_inventory,
    get_inventory_by_result, list_processing_inventories,
    delete_processing_inventory,
    list_inventory_rows, add_inventory_rows_bulk, count_inventory_rows.
"""

import json as _json


_INV_COLS = "id, result_id, note, created_at, updated_at"
_ROW_COLS = (
    "id, inventory_id, row_index, sequence_number, title, prefix, "
    "case_number, year, pages_count, sheet_numbers, extra_json, created_at"
)

_INV_FIELDS = ("sequence_number", "title", "prefix", "case_number",
               "year", "pages_count", "sheet_numbers")


def _inv_row_to_dict(r) -> dict:
    return {
        "id": r[0], "result_id": r[1], "note": r[2],
        "created_at": r[3], "updated_at": r[4],
    }


def _inv_line_to_dict(r) -> dict:
    try:
        extra = _json.loads(r[10]) if r[10] else {}
    except Exception:  # noqa: BLE001
        extra = {}
    return {
        "id": r[0], "inventory_id": r[1], "row_index": r[2],
        "sequence_number": r[3], "title": r[4], "prefix": r[5],
        "case_number": r[6], "year": r[7], "pages_count": r[8],
        "sheet_numbers": r[9], "extra": extra, "created_at": r[11],
    }


# ---------------------------------------------------------------------------
# Опись (шапка)
# ---------------------------------------------------------------------------

def save_processing_inventory(conn, result_id: int, rows: list,
                              note: str = "") -> int:
    """
    Сохраняет опись для акта. Полная замена: если у result_id уже была
    опись — она удаляется, создаётся новая + строки.

    Возвращает id нового inventory.
    """
    if not conn.execute(
            "SELECT 1 FROM processing_results WHERE id = ?", (result_id,)
    ).fetchone():
        raise ValueError(f"processing_results id={result_id} не найден")

    old = conn.execute(
        "SELECT id FROM processing_inventories WHERE result_id = ?",
        (result_id,)).fetchone()
    if old:
        conn.execute("DELETE FROM processing_inventories WHERE id = ?",
                     (old[0],))

    cur = conn.execute(
        "INSERT INTO processing_inventories (result_id, note) VALUES (?, ?)",
        (result_id, note or ""))
    inv_id = cur.lastrowid
    conn.commit()

    if rows:
        add_inventory_rows_bulk(conn, inv_id, rows)
    return inv_id


def get_processing_inventory(conn, inventory_id: int):
    r = conn.execute(
        f"SELECT {_INV_COLS} FROM processing_inventories WHERE id = ?",
        (inventory_id,)).fetchone()
    return _inv_row_to_dict(r) if r else None


def get_inventory_by_result(conn, result_id: int):
    r = conn.execute(
        f"SELECT {_INV_COLS} FROM processing_inventories WHERE result_id = ?",
        (result_id,)).fetchone()
    return _inv_row_to_dict(r) if r else None


def list_processing_inventories(conn) -> list:
    sql = f"SELECT {_INV_COLS} FROM processing_inventories ORDER BY id"
    return [_inv_row_to_dict(r) for r in conn.execute(sql)]


def delete_processing_inventory(conn, inventory_id: int) -> None:
    conn.execute("DELETE FROM processing_inventories WHERE id = ?",
                 (inventory_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Строки описи
# ---------------------------------------------------------------------------

def list_inventory_rows(conn, inventory_id: int) -> list:
    sql = f"SELECT {_ROW_COLS} FROM processing_inventory_rows " \
          "WHERE inventory_id = ? ORDER BY row_index, id"
    return [_inv_line_to_dict(r) for r in conn.execute(sql, (inventory_id,))]


def add_inventory_rows_bulk(conn, inventory_id: int, rows: list) -> int:
    """Массовая вставка строк описи. Возвращает число вставленных."""
    if not get_processing_inventory(conn, inventory_id):
        raise ValueError(f"processing_inventories id={inventory_id} не найден")

    to_insert = []
    for i, r in enumerate(rows, start=1):
        extra = r.get("extra")
        if extra is None:
            extra_json = "{}"
        elif isinstance(extra, str):
            extra_json = extra or "{}"
        else:
            extra_json = _json.dumps(extra, ensure_ascii=False)
        to_insert.append((
            inventory_id,
            int(r.get("row_index") or i),
            str(r.get("sequence_number") or ""),
            str(r.get("title") or ""),
            str(r.get("prefix") or ""),
            str(r.get("case_number") or ""),
            str(r.get("year") or ""),
            str(r.get("pages_count") or ""),
            str(r.get("sheet_numbers") or ""),
            extra_json,
        ))
    if not to_insert:
        return 0
    conn.executemany(
        "INSERT INTO processing_inventory_rows ("
        "inventory_id, row_index, sequence_number, title, prefix, "
        "case_number, year, pages_count, sheet_numbers, extra_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        to_insert)
    conn.commit()
    return len(to_insert)


def count_inventory_rows(conn, inventory_id: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM processing_inventory_rows WHERE inventory_id = ?",
        (inventory_id,)).fetchone()[0]
