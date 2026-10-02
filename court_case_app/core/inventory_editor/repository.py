# fix_49a_01
"""CRUD над processing_inventory_rows. Схема читается через PRAGMA."""
from __future__ import annotations
from typing import List, Optional
from .model import Doc
from .calculator import compute_derived
from .validator import validate_all


def _columns(conn, table: str) -> set:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in cur.fetchall()}


def list_docs(conn, inventory_id: int) -> List[Doc]:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, row_index, title, prefix, case_number, year, pages_count"
        " FROM processing_inventory_rows WHERE inventory_id = ?"
        " ORDER BY row_index, id",
        (inventory_id,),
    )
    return [Doc(title=r[2] or "", prefix=r[3] or "",
                case_number=int(r[4] or 0), year=int(r[5] or 0),
                pages_count=int(r[6] or 1), row_id=r[0], row_index=int(r[1] or 0))
            for r in cur.fetchall()]


def replace_docs(conn, inventory_id: int, docs: List[Doc]) -> None:
    validate_all(docs)
    cols = _columns(conn, "processing_inventory_rows")
    cur = conn.cursor()
    cur.execute("DELETE FROM processing_inventory_rows WHERE inventory_id = ?",
                (inventory_id,))
    derived = compute_derived(docs)
    for i, (d, der) in enumerate(zip(docs, derived)):
        values = {
            "inventory_id": inventory_id,
            "row_index": i,
            "sequence_number": der["B"],
            "title": d.title,
            "prefix": d.prefix,
            "case_number": d.case_number,
            "year": d.year,
            "pages_count": d.pages_count,
            "sheet_numbers": str(der["I"]),
        }
        use = {k: v for k, v in values.items() if k in cols}
        q_cols = ", ".join(use.keys())
        q_marks = ", ".join(["?"] * len(use))
        cur.execute(
            f"INSERT INTO processing_inventory_rows ({q_cols}) VALUES ({q_marks})",
            tuple(use.values()),
        )
    conn.commit()


def add_case(conn, inventory_id: int, prefix: str, case_number: int, year: int,
             doc_titles: List[str], pages: Optional[List[int]] = None) -> None:
    docs = list_docs(conn, inventory_id)
    pages = pages or [1] * len(doc_titles)
    new_docs = [Doc(title=t, prefix=prefix, case_number=case_number, year=year,
                    pages_count=p) for t, p in zip(doc_titles, pages)]
    key = (year, case_number)
    insert_at = len(docs)
    for i, d in enumerate(docs):
        dk = (d.year, d.case_number)
        if dk == key:
            insert_at = i + 1
        elif dk > key:
            insert_at = i
            break
    docs = docs[:insert_at] + new_docs + docs[insert_at:]
    replace_docs(conn, inventory_id, docs)


def delete_case(conn, inventory_id: int, year: int, case_number: int) -> int:
    docs = list_docs(conn, inventory_id)
    new_docs = [d for d in docs
                if not (d.year == year and d.case_number == case_number)]
    removed = len(docs) - len(new_docs)
    replace_docs(conn, inventory_id, new_docs)
    return removed


def delete_row(conn, inventory_id: int, row_id: int) -> None:
    docs = list_docs(conn, inventory_id)
    new_docs = [d for d in docs if d.row_id != row_id]
    replace_docs(conn, inventory_id, new_docs)
