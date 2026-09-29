# stage_46
# fix_46_01
# -*- coding: utf-8 -*-
"""
Перенос данных из Excel-результата в Word-акт.

Порт VBA Sub ПереносДанныхСНумерациейWord() с отличиями:
  * строки данных в целевой таблице предварительно очищаются
    (кроме заголовка) — повторный прогон идемпотентен;
  * исходный Word-файл не перезаписывается, результат сохраняется
    рядом с суффиксом `_filled`;
  * автонумерация столбца 1 сохраняется путём копирования
    XML-структуры строки-образца (deepcopy <w:tr>).

Использование:
    from core.converter.excel_to_act import import_excel_to_act
    info = import_excel_to_act("result.xlsx", "act.docx")
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from docx import Document
from openpyxl import load_workbook


SHEET_NAME = "Результат обработки"
HEADER_LABELS = ["1", "2", "3", "4", "5", "6", "7", "8"]
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# --- Поиск целевой таблицы --------------------------------------------------

def _cell_text(cell) -> str:
    """Текст ячейки без завершающего \\r\\x07, который добавляет Word."""
    return cell.text.replace("\r", "").replace("\x07", "").strip()


def _find_target_table(doc):
    """Ищет таблицу, у которой первая строка содержит «1»..«8».
    Возвращает (index, table) или (None, None)."""
    for idx, table in enumerate(doc.tables):
        if len(table.rows) < 1 or len(table.columns) < 8:
            continue
        try:
            if all(_cell_text(table.cell(0, c)) == HEADER_LABELS[c]
                   for c in range(8)):
                return idx, table
        except Exception:
            continue
    return None, None


# --- Чтение Excel -----------------------------------------------------------

def _read_excel_rows(excel_path: Path):
    wb = load_workbook(excel_path, data_only=True)
    try:
        if SHEET_NAME not in wb.sheetnames:
            raise ValueError(
                f"В файле Excel нет листа «{SHEET_NAME}». "
                f"Доступные листы: {', '.join(wb.sheetnames)}"
            )
        ws = wb[SHEET_NAME]

        # Последняя заполненная строка по столбцу A (аналог xlUp).
        last_row = 0
        for r in range(ws.max_row, 0, -1):
            v = ws.cell(row=r, column=1).value
            if v is not None and str(v).strip():
                last_row = r
                break
        if last_row < 2:
            raise ValueError(
                f"На листе «{SHEET_NAME}» нет данных (только заголовок)."
            )

        rows = []
        for r in range(2, last_row + 1):
            row_vals = []
            for c in range(2, 9):  # B..H
                v = ws.cell(row=r, column=c).value
                row_vals.append("" if v is None else str(v))
            rows.append(row_vals)
        return rows
    finally:
        wb.close()


# --- Работа с Word ----------------------------------------------------------

def _clear_data_rows(table):
    """Удаляет все строки кроме первой (заголовка).
    Возвращает deepcopy первой строки данных (образец для копирования).
    Если строк данных не было — возвращает None."""
    trs = table._tbl.findall(f"{W_NS}tr")
    if len(trs) < 2:
        return None
    sample = deepcopy(trs[1])
    for tr in trs[1:]:
        table._tbl.remove(tr)
    return sample


def _set_cell_text(cell, text: str) -> None:
    """Записывает текст, сохраняя форматирование первого run.
    Удаляет лишние абзацы в ячейке."""
    paragraphs = cell.paragraphs
    if not paragraphs:
        cell.add_paragraph(text)
        return
    first = paragraphs[0]
    if first.runs:
        first.runs[0].text = text
        for run in first.runs[1:]:
            run.text = ""
    else:
        first.add_run(text)
    for p in paragraphs[1:]:
        p._element.getparent().remove(p._element)


# --- Публичный API ----------------------------------------------------------

def import_excel_to_act(excel_path, word_path, output_path=None) -> dict:
    """Переносит данные из Excel-листа «Результат обработки» в Word-таблицу
    с заголовками «1»..«8».

    Параметры:
        excel_path  — путь к .xlsx с листом «Результат обработки».
        word_path   — путь к .docx с целевой таблицей.
        output_path — куда сохранить (по умолчанию <word>_filled.docx).

    Возвращает:
        {
          "rows_written": int,   # сколько строк добавлено
          "table_index":  int,   # индекс целевой таблицы (0-based)
          "output_path":  str,   # путь к сохранённому файлу
          "sheet_used":   str,   # имя использованного листа
        }

    Бросает ValueError при проблемах с исходными файлами.
    """
    excel_path = Path(excel_path)
    word_path = Path(word_path)
    if not excel_path.exists():
        raise ValueError(f"Excel-файл не найден: {excel_path}")
    if not word_path.exists():
        raise ValueError(f"Word-файл не найден: {word_path}")

    rows = _read_excel_rows(excel_path)

    doc = Document(str(word_path))
    table_idx, table = _find_target_table(doc)
    if table is None:
        raise ValueError(
            "В документе не найдена таблица с заголовками '1'..'8' "
            "и минимум 8 столбцами."
        )

    sample_tr = _clear_data_rows(table)
    if sample_tr is None:
        # Строк данных нет — образцом служит заголовок.
        sample_tr = deepcopy(table._tbl.findall(f"{W_NS}tr")[0])

    for row_vals in rows:
        new_tr = deepcopy(sample_tr)
        table._tbl.append(new_tr)
        r_idx = len(table.rows) - 1
        # fix_46_01: очищаем текст столбца 1 — автонумерация Word
        # хранится в <w:numPr> абзаца и после очистки текста сохранится.
        _set_cell_text(table.cell(r_idx, 0), "")
        for i, val in enumerate(row_vals):
            _set_cell_text(table.cell(r_idx, i + 1), val)

    if output_path is None:
        output_path = word_path.with_name(
            f"{word_path.stem}_filled{word_path.suffix}")
    output_path = Path(output_path)
    doc.save(str(output_path))

    return {
        "rows_written": len(rows),
        "table_index": table_idx,
        "output_path": str(output_path),
        "sheet_used": SHEET_NAME,
    }
