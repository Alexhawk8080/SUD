# fix_49a_01
"""Пересчёт производных полей описи: A (том), B (№ п/п), E (увеличение),
I (начало листов), J (конец листов). Совпадает с формулами шаблона,
F3 = 0 (первая строка данных), E_1 = case_number_1.
"""
from __future__ import annotations
from typing import List, Dict
from .model import Doc


def compute_derived(docs: List[Doc]) -> List[Dict]:
    out: List[Dict] = []
    prev_A, prev_B = 1, 0
    prev_I, prev_J = 0, None
    prev_case = 0
    for i, d in enumerate(docs):
        eff_prev_I = prev_J if prev_J is not None else prev_I
        if i == 0:
            A, B = 1, 1
        elif eff_prev_I >= 150:
            A = prev_A if d.case_number == prev_case else prev_A + 1
            B = prev_B + 1 if d.case_number == prev_case else 1
        else:
            A, B = prev_A, prev_B + 1
        E = d.case_number - prev_case
        I = 1 if (eff_prev_I >= 150 and d.case_number != prev_case) else eff_prev_I + 1
        J = None if d.pages_count == 1 else I + d.pages_count - 1
        out.append({"A": A, "B": B, "E": E, "I": I, "J": J,
                    "case_number": d.case_number})
        prev_A, prev_B = A, B
        prev_I, prev_J = I, J
        prev_case = d.case_number
    return out


def group_by_case(docs: List[Doc]) -> List[Dict]:
    groups: List[Dict] = []
    cur_key, cur = None, None
    for d in docs:
        key = (d.year, d.case_number)
        if key != cur_key:
            cur = {"prefix": d.prefix, "case_number": d.case_number,
                   "year": d.year, "docs": []}
            groups.append(cur)
            cur_key = key
        cur["docs"].append(d)
    return groups
