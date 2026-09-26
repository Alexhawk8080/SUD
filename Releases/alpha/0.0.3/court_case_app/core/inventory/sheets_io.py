# -*- coding: utf-8 -*-
"""
Работа с шаблоном «Таблица».xlsx (этап 14d, решения 10–13).

Шаблон загружает пользователь. Лист строго «Таблица». Конвертер:
    - определяет last_template_row (последняя заполненная строка в столбце A);
    - очищает шаблон (решение 11);
    - протягивает формулы при нехватке строк (решение 12);
    - расширяет диапазоны VLOOKUP (решение 13).

ВАЖНО: книга открывается с формулами (data_only=False) — формулы
переносятся как текст и сдвигаются по строкам вручную.
"""

import re

from .exceptions import TemplateSheetNotFound

TEMPLATE_SHEET = "Таблица"
FIRST_DATA_ROW = 4            # строка 4 — первая строка данных (эталон)
FORMULA_COLUMNS = ("A", "B", "F", "I", "J", "K", "L")   # протягиваем только эти
CLEAR_REPLICATE = ("C", "D", "G")   # копируем значение строки 4 вниз
CLEAR_FILL_ONE = ("E", "H")         # заполняем 1
RANGE_RESERVE = 100                 # запас расширения диапазонов VLOOKUP

_CELL_RE = re.compile(r"(\$?)([A-Za-z]{1,3})(\$?)(\d+)")


def shift_formula(formula, delta: int) -> str:
    """
    Сдвигает относительные ссылки на строки в формуле на delta.

    Абсолютные строки ($4) и диапазоны ($A$4) не меняются.
    """
    if not formula or not isinstance(formula, str) or not formula.startswith("="):
        return formula

    def repl(m):
        col_dollar, col, row_dollar, row = m.groups()
        new_row = row if row_dollar else str(int(row) + delta)
        return f"{col_dollar}{col}{row_dollar}{new_row}"

    return _CELL_RE.sub(repl, formula)


def find_template_sheet(workbook):
    """Лист строго «Таблица» или TemplateSheetNotFound."""
    if TEMPLATE_SHEET not in workbook.sheetnames:
        raise TemplateSheetNotFound(
            f"В шаблоне нет листа «{TEMPLATE_SHEET}». "
            f"Найдены: {', '.join(workbook.sheetnames) or '—'}.")
    return workbook[TEMPLATE_SHEET]


def detect_last_template_row(ws, start_row: int = FIRST_DATA_ROW) -> int:
    """Последняя заполненная строка в столбце A (не меньше start_row)."""
    last = start_row
    for row in range(start_row, ws.max_row + 1):
        val = ws.cell(row=row, column=1).value
        if val is not None and str(val).strip() != "":
            last = row
    return last


def clean_template(ws, last_row: int) -> None:
    """
    Очистка шаблона (решение 11, порядок: сначала очистка).

        1) C4 -> скопировать значение на C4:C{last_row}
        2) D4 -> скопировать на D4:D{last_row}
        3) E и H -> заполнить 1 на E4:E{last_row} / H4:H{last_row}
        4) G4 -> скопировать на G4:G{last_row}
    """
    for col in CLEAR_REPLICATE:
        value = ws.cell(row=FIRST_DATA_ROW, column=_col_index(col)).value
        for row in range(FIRST_DATA_ROW, last_row + 1):
            ws.cell(row=row, column=_col_index(col)).value = value
    for col in CLEAR_FILL_ONE:
        for row in range(FIRST_DATA_ROW, last_row + 1):
            ws.cell(row=row, column=_col_index(col)).value = 1


def _col_index(letter: str) -> int:
    """Индекс столбца по букве (A=1)."""
    idx = 0
    for ch in letter.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx


def extend_formulas(ws, last_row: int, target_last_row: int) -> None:
    """
    Протяжка формул при нехватке строк (решение 12).

    Эталон — строка 4. Протягиваются ТОЛЬКО A, B, F, I, J, K, L.
    O, P, Q, R, T, U не протягиваются.
    """
    if target_last_row <= last_row:
        return
    for row in range(last_row + 1, target_last_row + 1):
        delta = row - FIRST_DATA_ROW
        for col in FORMULA_COLUMNS:
            src = ws.cell(row=FIRST_DATA_ROW, column=_col_index(col)).value
            if isinstance(src, str) and src.startswith("="):
                ws.cell(row=row, column=_col_index(col)).value = \
                    shift_formula(src, delta)


_VLOOKUP_RANGE_RE = re.compile(r"\$A\$4:\$([A-Z])\$(\d+)")


def extend_vlookup_ranges(ws, target_last_row: int) -> int:
    """
    Расширяет диапазоны $A$4:$F$10003 и $A$4:$K$10003 (решение 13).

    Новый конец = target_last_row + RANGE_RESERVE (одинаковый для обоих).
    Возвращает новый номер последней строки диапазона.
    """
    new_end = target_last_row + RANGE_RESERVE
    for row in ws.iter_rows():
        for cell in row:
            val = cell.value
            if isinstance(val, str) and val.startswith("=") and "$A$4:$" in val:
                cell.value = _VLOOKUP_RANGE_RE.sub(
                    lambda m: f"$A$4:${m.group(1)}${new_end}", val)
    return new_end