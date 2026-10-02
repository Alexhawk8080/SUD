# stage_49b
"""Формирование описи из базы данных.

Мягкая деградация: если в таблице cases нет нужных колонок —
возвращаем пустой список, а вызывающий код показывает ошибку.
Это защита от угадывания схемы (§13).
"""
from __future__ import annotations
from typing import List
from .model import Doc

CIVIL_TITLES = {
    "Судебный приказ по гражданскому делу",
    "Определение по гражданскому делу",
    "Заочное решение по гражданскому делу",
    "Решение по гражданскому делу",
}
ADMIN_TITLES = {
    "Постановление по делу об административном правонарушении",
    "Решение по делу об административном правонарушении",
    "Определение по делу об административном правонарушении",
}


def _columns(conn, table: str) -> set:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {r[1] for r in cur.fetchall()}


def generate_from_cases(conn, year: int, kind: str = "civil") -> List[Doc]:
    """Вернёт список Doc для указанного года и типа дел.

    Ожидает в `cases` колонки: case_number, year, title
    и (опционально) prefix. Если чего-то нет — возвращает [].
    """
    cols = _columns(conn, "cases")
    need = {"case_number", "year", "title"}
    if not need <= cols:
        return []
    prefix_col = "prefix" if "prefix" in cols else None

    sql = "SELECT case_number, year"
    sql += ", prefix" if prefix_col else ", ''"
    sql += ", title FROM cases WHERE year = ? ORDER BY case_number"
    cur = conn.cursor()
    cur.execute(sql, (year,))

    allowed = CIVIL_TITLES if kind == "civil" else ADMIN_TITLES
    docs: List[Doc] = []
    for cn, y, p, t in cur.fetchall():
        if t not in allowed:
            continue
        try:
            case_number = int(cn)
            year_val = int(y)
        except (TypeError, ValueError):
            continue
        docs.append(Doc(title=str(t), prefix=str(p or ""),
                        case_number=case_number, year=year_val,
                        pages_count=1))
    return docs
