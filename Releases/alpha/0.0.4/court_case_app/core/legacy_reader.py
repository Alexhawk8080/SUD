# -*- coding: utf-8 -*-
"""
Чтение ранее обработанных файлов («старой версии») для проверки категорий
(Доработка 6).

Поддерживаются:
    - результат обработки .xlsx (лист «Результат обработки», колонка
      «Заголовок дела»);
    - акт уничтожения .docx (ячейки таблиц с текстом «Гражданское дело №...»).

Из заголовка извлекаются номер дела, заявители и категория «о ...».
Категория — хвост заголовка, начинающийся с «о/об»; если его нет,
категория считается пустой (дело проблемное).
"""

import re

from .category_check import extract_phrase

# Заголовок дела: «Гражданское дело №2-3/2023 по иску Истец к Ответчик о ...»
_TITLE_RE = re.compile(
    r"Гражданское дело\s+№(?P<num>[0-9]+-[0-9]+/[0-9]{4})"
    r"\s+(?P<prefix>по иску|по заявлению)"
    r"(?:\s+(?P<applicants>.+?))?\s+к\s+(?P<rest>.+)",
    re.IGNORECASE)

# Фраза «о ...» / «об ...» для отделения ответчика от категории
_CATEGORY_START_RE = re.compile(r"(?:^|\s)(о|об)\s")

# --- Определение столбцов готового файла (Доработка 7) -----------------------
# Роли: title, dates, opis, unit, count, retention.
_HEADER_HINTS = {
    "title": ("заголовок", "наименование", "заголовок дела"),
    "dates": ("даты дела", "даты", "дата"),
    "opis": ("№ описи", "описи", "опись"),
    "unit": ("№ ед.хр", "ед.хр", "ед. хр", "единиц"),
    "count": ("кол-во", "количество"),
    "retention": ("срок хранения", "срок"),
}

# Позиции по умолчанию (0-based), как в excel_writer/акте.
_DEFAULT_POSITIONS = {
    "title": 1, "dates": 2, "opis": 3, "unit": 4,
    "count": 5, "retention": 6,
}

_RAW_ROLES = ("dates", "opis", "unit", "count", "retention")


def _norm(v) -> str:
    return " ".join(str(v or "").strip().lower().split())


def detect_columns(cells) -> dict:
    """
    Определяет role -> индекс столбца по названиям заголовков.

    Возвращает найденное (может быть частично); позиции не подставляются —
    за это отвечает _columns_or_default.
    """
    mapping = {}
    for idx, cell in enumerate(cells):
        h = _norm(cell)
        if not h:
            continue
        for role, hints in _HEADER_HINTS.items():
            if role in mapping:
                continue
            if any(h == _norm(hint) or h.startswith(_norm(hint))
                   for hint in hints):
                mapping[role] = idx
                break
    return mapping


def _columns_or_default(mapping) -> dict:
    """Дополняет распознанные столбцы позициями по умолчанию."""
    result = dict(mapping)
    for role, pos in _DEFAULT_POSITIONS.items():
        result.setdefault(role, pos)
    return result


def _looks_header(cells) -> bool:
    """True, если строка похожа на шапку таблицы готового результата."""
    joined = " ".join(_norm(c) for c in cells)
    return "заголовок" in joined or "наименование" in joined


def _clean_raw(value):
    """Сырое значение «как есть»: строки — trim, None -> ''."""
    if value is None:
        return ""
    return str(value).strip()


def tc_text(tc, qn) -> str:
    """Текст ячейки <w:tc> с учётом переносов (<w:br/> -> \\n, <w:tab/> -> \\t)."""
    parts = []
    for node in tc.iter():
        if node.tag == qn("w:t"):
            parts.append(node.text or "")
        elif node.tag == qn("w:br"):
            parts.append("\n")
        elif node.tag == qn("w:tab"):
            parts.append("\t")
    return "".join(parts)


def attach_raw(parsed: dict, columns: dict, cells) -> dict:
    """Добавляет к записи сырые значения столбцов (Доработка 7)."""
    for role in _RAW_ROLES:
        idx = columns.get(role)
        value = ""
        if idx is not None and idx < len(cells):
            value = _clean_raw(cells[idx])
        parsed[f"{role}_raw"] = value
    parsed["legacy_raw"] = True
    return parsed


def parse_title(title) -> dict | None:
    """
    Разбор заголовка дела из готового результата.

    Возвращает словарь {case_number, applicants, respondents, category,
    prefix, title} или None, если текст не похож на заголовок дела.
    """
    if not title:
        return None
    text = " ".join(str(title).split())
    m = _TITLE_RE.match(text)
    if not m:
        return None
    applicants = (m.group("applicants") or "").strip()
    rest = m.group("rest").strip()

    # Ответчик — часть rest до фразы «о/об»; категория — с этой фразы
    cm = _CATEGORY_START_RE.search(rest.lower())
    if cm:
        respondents = rest[:cm.start()].strip()
        phrase = rest[cm.start(1):].strip()
    else:
        respondents = rest.strip()
        phrase = ""

    return {
        "case_number": m.group("num"),
        "prefix": m.group("prefix"),
        "applicants": applicants,
        "respondents": respondents,
        "category": phrase,          # «о ...» или "" (дело проблемное)
        "title": text,
    }


def parse_result_xlsx(filepath) -> list:
    """
    Чтение файла-результата .xlsx (лист «Результат обработки»).

    Колонки (как в excel_writer): № п/п, Заголовок дела, Даты дела,
    № описи, № ед.хр., Кол-во ед.хр., Срок хранения, Примечание.

    Возвращает список записей parse_title (пустые строки пропускаются).
    """
    from openpyxl import load_workbook

    wb = load_workbook(filepath, data_only=True, read_only=True)
    try:
        ws = (wb["Результат обработки"]
              if "Результат обработки" in wb.sheetnames else wb.active)
        columns = None
        records = []
        for row in ws.iter_rows(values_only=True):
            cells = [_clean_raw(c) for c in (row or ())]
            if columns is None:
                if _looks_header(cells):
                    columns = _columns_or_default(detect_columns(cells))
                continue
            title = cells[columns["title"]] \
                if columns["title"] < len(cells) else ""
            parsed = parse_title(title)
            if parsed:
                records.append(attach_raw(parsed, columns, cells))
        return records
    finally:
        wb.close()


def parse_act_docx(filepath) -> list:
    """
    Чтение акта уничтожения .docx: поиск ячеек таблиц с текстом
    «Гражданское дело №...» (заголовки дел).

    Возвращает список записей parse_title.

    fix_05_v2: обходим XML-узлы w:tc напрямую (table._tbl.iter).
    Каждый узел w:tc уникален в дереве, поэтому объединённые ячейки
    (merge) не дают дубликатов, а разные ячейки не схлопываются.
    """
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(filepath)
    records = []
    for table in doc.tables:
        rows = []
        for row in table.rows:
            tcs = getattr(row._tr, "tc_lst", None)
            if tcs is None:
                cells = [c.text or "" for c in row.cells]
            else:
                cells = [tc_text(tc, qn) for tc in tcs]
            rows.append([_clean_raw(c) for c in cells])

        columns = None
        start = 0
        for idx, cells in enumerate(rows[:5]):
            if _looks_header(cells):
                columns = _columns_or_default(detect_columns(cells))
                start = idx + 1
                break
        if columns is None:
            columns = _columns_or_default({})

        for cells in rows[start:]:
            ti = columns["title"]
            parsed = parse_title(cells[ti]) if ti < len(cells) else None
            if parsed is None:
                # Устойчивость к merge: ищем ячейку с заголовком дела
                for idx, cell in enumerate(cells):
                    parsed = parse_title(cell)
                    if parsed:
                        ti = idx
                        break
            if parsed:
                records.append(attach_raw(parsed, {**columns, "title": ti},
                                          cells))
    return records


def parse_legacy_file(filepath) -> list:
    """
    Универсальное чтение старого результата по расширению файла.

    Возвращает список записей (пустой, если ничего не найдено).
    """
    lower = str(filepath).lower()
    if lower.endswith(".docx"):
        return parse_act_docx(filepath)
    if lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        return parse_result_xlsx(filepath)
    return []