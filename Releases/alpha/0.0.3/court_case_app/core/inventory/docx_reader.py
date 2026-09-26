# -*- coding: utf-8 -*-
"""
Чтение docx-описи «Внутренняя опись» (этап 14a).

Формат документа:
    таблица из 3 столбцов (№ п/п | Наименование | Номера листов),
    несколько томов в одном файле, футер «Итого наряд на N листах».

Использование:
    result = read_inventory_docx(path)
    # result = {
    #     "file":          "опись том 1.docx",
    #     "tables":        1,
    #     "rows":          [ {file, word_row, volume, number, number_raw,
    #                         name, name_raw, sheets_raw}, ... ],
    #     "volumes":       [ {volume, table_index, start_row, end_row,
    #                         total_sheets}, ... ],
    #     "footer_total":  20,          # «наряд на N листах» или None
    #     "attention":     [ {file, word_row, number, reason, action}, ... ],
    # }

Чтение устойчиво к дефектам исходных описей (решение 20):
    - пропуски и дубликаты № п/п;
    - артефакты Word: {.mark}, <u>, лишние пробелы;
    - опечатки в тексте — не влияют на извлечение (текст переносится как есть).
"""

import os
import re

from ..text_utils import sanitize_text
from .exceptions import BadInventoryFileError, NoInventoryTableError

# ---------------------------------------------------------------------------
# Столбцы описи
# ---------------------------------------------------------------------------

# Роли столбцов описи: 0 — № п/п, 1 — Наименование, 2 — Номера листов.
# В «Таблице» Excel исходный № п/п НЕ используется (решение 21).
HEADER_HINTS = {
    "number": ("№ п/п", "№п/п", "номер п/п", "номер", "№"),
    "name": ("наименование", "название", "заголовок"),
    "sheets": ("номера листов", "номера листа", "листы", "листов"),
}

# ---------------------------------------------------------------------------
# Регулярные выражения
# ---------------------------------------------------------------------------

# Артефакты Word: {.mark}, <u>, </u>, <i>, <b>, <span ...> — удаляем.
_ARTIFACT_RE = re.compile(r"\{\.[A-Za-zА-Яа-я_]*\}|</?[A-Za-zА-Яа-я][^>]*>")
# Неразрывные пробелы и табуляции -> обычный пробел.
_SPACES_RE = re.compile(r"[ \t\u00a0\u2007\u202f]+")
_ITOGO_RE = re.compile(r"^\s*итого\b", re.IGNORECASE)
_TOM_RE = re.compile(r"^\s*том\s*([IVXLCDM]+|\d+)\s*$", re.IGNORECASE)
_TOTAL_SHEETS_RE = re.compile(r"наряд\s+на\s+(\d+)\s+лист", re.IGNORECASE)
_NUMBER_RE = re.compile(r"^\s*(\d+)\s*[.)]?\s*$")


# ---------------------------------------------------------------------------
# Нормализация текста
# ---------------------------------------------------------------------------

def clean_name(text) -> str:
    """
    Нормализует ячейку «Наименование»: убирает артефакты Word,
    переносы строк -> пробел, схлопывает пробелы.
    """
    if text is None:
        return ""
    s = sanitize_text(str(text))
    s = _ARTIFACT_RE.sub("", s)
    s = s.replace("\n", " ")
    s = _SPACES_RE.sub(" ", s)
    return s.strip()


def parse_number(text):
    """
    Разбирает «№ п/п»: возвращает (число | None, исходный текст).

    «171» -> (171, "171"); «231.» -> (231, "231.");
    пустое/нечисловое -> (None, <как есть>).
    """
    if text is None:
        return None, ""
    raw = sanitize_text(str(text)).strip()
    m = _NUMBER_RE.match(raw)
    if not m:
        return None, raw
    return int(m.group(1)), raw


# ---------------------------------------------------------------------------
# Чтение строк таблицы (устойчиво к merge-ячейкам)
# ---------------------------------------------------------------------------

def _tc_text(tc) -> str:
    """Текст всех <w:t> внутри элемента <w:tc> (с переносами строк)."""
    from docx.oxml.ns import qn
    parts = []
    for t in tc.iter(qn("w:t")):
        parts.append(t.text or "")
    return sanitize_text("".join(parts))


def row_values(row) -> list:
    """
    Значения ячеек строки БЕЗ дублирования объединённых ячеек.

    Читаем напрямую <w:tc> из <w:tr>: python-docx повторяет содержимое
    merged-ячеек в row.cells, что ломает позиции столбцов (fix_05).
    """
    try:
        tcs = row._tr.tc_lst
    except Exception:  # noqa: BLE001
        tcs = None
    if tcs is None:
        return [_tc_text_wrapper(c) for c in row.cells]
    return [_tc_text(tc) for tc in tcs]


def _tc_text_wrapper(cell) -> str:
    try:
        return str(sanitize_text(cell.text or "") or "")
    except Exception:  # noqa: BLE001
        return ""


def _norm(v) -> str:
    return " ".join(str(v or "").strip().lower().split())


def is_header_row(cells) -> bool:
    """True, если строка — шапка таблицы описи."""
    joined = " ".join(_norm(c) for c in cells)
    if "наименование" in joined and ("п/п" in joined or "№" in joined):
        return True
    return "номера листов" in joined or "номера листа" in joined


def is_itogo_row(cells) -> bool:
    """True, если строка — итоговая («Итого …»)."""
    return any(_ITOGO_RE.match(c or "") for c in cells)


def is_tom_row(cells) -> bool:
    """True, если строка — заголовок тома («Том I», «Том 3»)."""
    joined = " ".join(_norm(c) for c in cells)
    return bool(_TOM_RE.match(joined))


# ---------------------------------------------------------------------------
# Извлечение записей
# ---------------------------------------------------------------------------

def make_record(file_name, word_row, volume, number, number_raw,
                name, name_raw, sheets_raw) -> dict:
    """Собирает запись строки описи."""
    return {
        "file": file_name,
        "word_row": word_row,
        "volume": volume,
        "number": number,
        "number_raw": number_raw,
        "name": name,
        "name_raw": name_raw,
        "sheets_raw": sheets_raw,
    }


def extract_rows(table, file_name="", volume=1, start_word_row=1):
    """
    Извлекает строки данных из таблицы описи.

    Возвращает (records, attention, volume_info).
    Служебные строки (шапка, «Итого», «Том …») пропускаются.
    """
    records = []
    attention = []
    seen_numbers = {}
    titles = []
    end_word_row = start_word_row
    expected = 1

    for offset, row in enumerate(table.rows):
        word_row = start_word_row + offset
        end_word_row = word_row
        cells = row_values(row)
        non_empty = [c for c in cells if c and c.strip()]
        if not non_empty:
            continue
        if is_tom_row(cells):
            titles.append(" ".join(c.strip() for c in cells if c.strip()))
            continue
        if is_header_row(cells) or is_itogo_row(cells):
            continue

        name_raw = cells[1] if len(cells) > 1 else ""
        sheets_raw = cells[2] if len(cells) > 2 else ""
        number, number_raw = parse_number(cells[0] if cells else "")
        name = clean_name(name_raw)

        if number is None and not name:
            continue

        if number is not None:
            if number in seen_numbers:
                attention.append({
                    "file": file_name, "word_row": word_row,
                    "number": number_raw,
                    "reason": f"дубликат № п/п (уже был в строке "
                              f"{seen_numbers[number]})",
                    "action": "строка сохранена",
                })
            if number > expected:
                attention.append({
                    "file": file_name, "word_row": word_row,
                    "number": number_raw,
                    "reason": f"пропуск в № п/п ({expected}…{number - 1})",
                    "action": "поток сквозной",
                })
            seen_numbers[number] = word_row
            expected = max(expected, number + 1)

        records.append(make_record(
            file_name, word_row, volume, number, number_raw,
            name, name_raw, sheets_raw))

    info = {
        "volume": volume,
        "start_row": start_word_row,
        "end_row": end_word_row,
        "titles": titles,
    }
    return records, attention, info


# ---------------------------------------------------------------------------
# Поиск таблиц описи в документе
# ---------------------------------------------------------------------------

def _looks_inventory(table) -> bool:
    """Таблица — опись, если шапка содержит «Наименование» либо
    большинство строк имеют числовой № п/п и непустое наименование."""
    rows = list(table.rows)
    if not rows:
        return False
    for row in rows[:3]:
        if is_header_row(row_values(row)):
            return True
    total = numeric = 0
    for row in rows:
        cells = row_values(row)
        if not any(c and c.strip() for c in cells):
            continue
        total += 1
        if parse_number(cells[0] if cells else "")[0] is not None:
            numeric += 1
    return total > 0 and numeric * 2 > total


def find_inventory_tables(doc) -> list:
    """Возвращает [(table_index, table), ...] — таблицы описи по порядку."""
    found = []
    for idx, table in enumerate(doc.tables):
        if _looks_inventory(table):
            found.append((idx, table))
    return found


def _find_footer_total(doc):
    """Ищет «Итого наряд на N листах» в футерах и теле документа."""
    texts = []
    for section in doc.sections:
        for part in (section.footer, section.first_page_footer,
                     section.even_page_footer):
            try:
                texts.append(part.text or "")
            except Exception:  # noqa: BLE001
                continue
    for para in doc.paragraphs:
        texts.append(para.text or "")
    for text in texts:
        m = _TOTAL_SHEETS_RE.search(sanitize_text(text) or "")
        if m:
            return int(m.group(1))
    return None


def _preceding_titles(doc) -> dict:
    """
    Заголовки томов-абзацев: {table_index: текст абзаца перед таблицей}.

    Реальные описи часто содержат «Том I» отдельным абзацем перед таблицей.
    """
    from docx.oxml.ns import qn
    titles = {}
    last_text = ""
    tbl_idx = -1
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            txt = "".join(t.text or "" for t in child.iter(qn("w:t"))).strip()
            if txt:
                last_text = txt
        elif child.tag == qn("w:tbl"):
            tbl_idx += 1
            if last_text:
                titles[tbl_idx] = last_text
            last_text = ""
    return titles


# ---------------------------------------------------------------------------
# Главная точка входа
# ---------------------------------------------------------------------------

def read_inventory_docx(path: str) -> dict:
    """
    Читает один docx-файл описи.

    Возвращает словарь (см. docstring модуля).
    Бросает BadInventoryFileError / NoInventoryTableError.
    """
    from docx import Document

    file_name = os.path.basename(path)
    try:
        doc = Document(path)
    except Exception as exc:  # noqa: BLE001
        raise BadInventoryFileError(
            f"Не удалось открыть «{file_name}» как .docx: {exc}") from exc

    tables = find_inventory_tables(doc)
    if not tables:
        raise NoInventoryTableError(
            f"В «{file_name}» не найдено ни одной таблицы описи "
            "(№ п/п | Наименование | Номера листов).")

    rows = []
    attention = []
    volumes = []
    word_row = 1
    pre_titles = _preceding_titles(doc)
    for volume_no, (table_index, table) in enumerate(tables, start=1):
        recs, att, info = extract_rows(
            table, file_name=file_name, volume=volume_no,
            start_word_row=word_row)
        rows.extend(recs)
        attention.extend(att)
        info["table_index"] = table_index
        if not info["titles"] and table_index in pre_titles:
            info["titles"] = [pre_titles[table_index]]
        volumes.append(info)
        word_row = info["end_row"] + 1

    return {
        "file": file_name,
        "tables": len(tables),
        "rows": rows,
        "volumes": volumes,
        "footer_total": _find_footer_total(doc),
        "attention": attention,
    }