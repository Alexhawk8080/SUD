# fix_49a_01
"""Справочник типов документов для Внутренней описи."""
from __future__ import annotations
from typing import List, Dict, Optional

SEED = [
    ("civil", "Судебный приказ по гражданскому делу", 10),
    ("civil", "Определение по гражданскому делу", 20),
    ("civil", "Заочное решение по гражданскому делу", 30),
    ("civil", "Решение по гражданскому делу", 40),
    ("admin", "Постановление по делу об административном правонарушении", 10),
    ("admin", "Решение по делу об административном правонарушении", 20),
    ("admin", "Определение по делу об административном правонарушении", 30),
]

def ensure_schema(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS inventory_doc_types ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " kind TEXT NOT NULL,"
        " title TEXT NOT NULL,"
        " sort_order INTEGER NOT NULL DEFAULT 0,"
        " UNIQUE(kind, title))"
    )
    for kind, title, order in SEED:
        cur.execute(
            "INSERT OR IGNORE INTO inventory_doc_types (kind, title, sort_order)"
            " VALUES (?, ?, ?)", (kind, title, order))
    conn.commit()

def list_types(conn, kind: Optional[str] = None) -> List[Dict]:
    cur = conn.cursor()
    if kind:
        cur.execute("SELECT id, kind, title, sort_order FROM inventory_doc_types"
                    " WHERE kind = ? ORDER BY sort_order, id", (kind,))
    else:
        cur.execute("SELECT id, kind, title, sort_order FROM inventory_doc_types"
                    " ORDER BY kind, sort_order, id")
    return [{"id": r[0], "kind": r[1], "title": r[2], "sort_order": r[3]}
            for r in cur.fetchall()]

def is_valid_title(conn, title: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM inventory_doc_types WHERE title = ? LIMIT 1",
                (title,))
    return cur.fetchone() is not None
