# -*- coding: utf-8 -*-
"""
Конвертация Excel-результата («Результат обработки») в Word-акт по шаблону.

Использование:
    records, mapping = read_result_xlsx(path)          # только чтение
    path = convert_xlsx_to_word(
        filepath, template_path, output_path,
        common_values=..., year="2020")

Логика определения столбцов (решения 55):
    1. По позиции: 8 столбцов в ожидаемом порядке.
    2. Эвристика по содержимому: в столбце есть «Гражданское дело №...» ->
       title; «N год ... Ст. M» -> retention и т.п.
    3. Если не удалось найти ключевые столбцы (sequential, title) —
       ColumnsNotFound.
"""

import os
import re

from .exceptions import BadFileError, ColumnsNotFound, SheetNotFound
from .sheets import RESULT_SHEET_NAME, inspect_sheets, verify_xlsx_content

# Роли и их заголовки в Excel-результате (в ожидаемом порядке)
COLUMNS = [
    ("sequential", "№ п/п"),
    ("title", "Заголовок дела"),
    ("dates", "Даты дела"),
    ("opis", "№ описи"),
    ("unit", "№ ед.хр."),
    ("count", "Кол-во ед.хр."),
    ("retention", "Срок хранения"),
    ("note", "Примечание"),
]

# Ожидаемые заголовки для эвристики по шапке (нормализованные)
_HEADER_HINTS = {
    "sequential": ("№ п/п", "п/п", "№"),
    "title": ("заголовок",),
    "dates": ("даты", "дата"),
    # stage12b_v2: явные «№ описи» / «№ ед.хр» — заголовок начинается с «№»
    "opis": ("№ описи", "описи", "опись"),
    "unit": ("№ ед.хр", "№ ед. хр", "ед.хр", "ед. хр", "единиц"),
    "count": ("кол-во", "количество"),
    "retention": ("срок хранения", "срок"),
    "note": ("примечание",),
}

_TITLE_RE = re.compile(r"Гражданское дело\s+№", re.IGNORECASE)
_RETENTION_RE = re.compile(r"\b\d+\s*(?:год|года|лет)\b", re.IGNORECASE)


def _norm(v) -> str:
    """Нормализация значения для сравнения (нижний регистр, без пробелов по краям)."""
    if v is None:
        return ""
    return " ".join(str(v).strip().lower().split())


def _detect_columns(rows: list) -> dict:
    """
    Определяет role -> индекс столбца (0-based) по шапке или эвристике.

    rows — список кортежей (values_only из openpyxl).
    Бросает ColumnsNotFound, если не удалось определить обязательные
    title/sequential.
    """
    if not rows:
        raise ColumnsNotFound("Файл не содержит строк с данными.")

    header = [_norm(v) for v in rows[0]]
    mapping = {}
    # Шаг 1: точное или startswith-совпадение по шапке
    for idx, h in enumerate(header):
        if not h:
            continue
        for role, hints in _HEADER_HINTS.items():
            if role in mapping:
                continue
            for hint in hints:
                nh = _norm(hint)
                if h == nh or h.startswith(nh):
                    mapping[role] = idx
                    break
            if role in mapping:
                break

    # Шаг 2: эвристика по содержимому (только title и retention, если не нашли)
    if "title" not in mapping or "retention" not in mapping:
        data_rows = rows[1:20]
        for col_idx in range(len(header)):
            col_values = []
            for r in data_rows:
                if col_idx < len(r):
                    col_values.append(r[col_idx])
            joined = " ".join(_norm(v) for v in col_values)
            if "title" not in mapping and _TITLE_RE.search(joined):
                mapping["title"] = col_idx
            if "retention" not in mapping and _RETENTION_RE.search(joined):
                mapping["retention"] = col_idx

    # Шаг 3: если sequential не нашли — ставим 0 (первый столбец) как разумный дефолт
    if "sequential" not in mapping:
        mapping["sequential"] = 0

    if "title" not in mapping:
        raise ColumnsNotFound(
            "Не удалось найти столбец «Заголовок дела» ни по шапке, "
            "ни по содержимому (нет строк вида «Гражданское дело №...»).")
    return mapping


def _make_record(row, mapping: dict) -> dict:
    """
    Строит запись для write_word_result из строки и маппинга.

    fix_10_v2: sanitize_text — нормализуем _x000D_/\r/\v в \n.
    """
    from ..text_utils import sanitize_text

    def _get(role):
        idx = mapping.get(role)
        if idx is None or idx >= len(row):
            return ""
        v = row[idx]
        if v is None:
            return ""
        return sanitize_text(v) if isinstance(v, str) else v

    def _get_str(role):
        v = _get(role)
        if v is None:
            return ""
        return sanitize_text(str(v)).strip()

    return {
        "sequential": _get("sequential"),
        "title": _get_str("title"),
        "dates": _get_str("dates"),
        "opis": _get("opis"),
        "unit": _get("unit"),
        "count": _get("count"),
        "retention": _get_str("retention"),
        "note": _get_str("note"),
    }


def read_result_xlsx(filepath, sheet_name: str = None):
    """
    Читает лист Excel-результата и возвращает (records, mapping).

    Параметры:
        filepath   — путь к .xlsx/.xlsm;
        sheet_name — имя листа; None -> «Результат обработки», если есть,
                     иначе активный (см. sheets.inspect_sheets).

    Возвращает:
        records — список словарей с полями записи (все строки, включая
                  пустые — для сохранения сквозной нумерации);
        mapping — словарь role -> индекс столбца (0-based).

    Бросает BadFileError, SheetNotFound, ColumnsNotFound.
    """
    verify_xlsx_content(filepath)
    info = inspect_sheets(filepath)
    if sheet_name is None:
        sheet_name = info["default"]
    if sheet_name not in info["sheets"]:
        raise SheetNotFound(
            f"Лист «{sheet_name}» не найден. Доступные: "
            f"{', '.join(info['sheets'])}")

    from openpyxl import load_workbook
    try:
        wb = load_workbook(filepath, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise BadFileError(f"Не удалось открыть книгу: {exc}") from exc

    try:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        try:
            wb.close()
        except Exception:  # noqa: BLE001
            pass

    if not rows:
        raise ColumnsNotFound(f"Лист «{sheet_name}» пуст.")

    mapping = _detect_columns(rows)
    records = [_make_record(r, mapping) for r in rows[1:]]
    return records, mapping


def convert_xlsx_to_word(filepath, template_path, output_path,
                         common_values: dict, year,
                         sheet_name: str = None):
    """
    Полный цикл: Excel-результат -> Word-акт по шаблону.

    Параметры:
        filepath        — путь к Excel-результату;
        template_path   — путь к .docx-шаблону;
        output_path     — путь для сохранения .docx;
        common_values   — словарь реквизитов (участок, судья, ...).
                          Если передан пустой dict, в Word будут пустые поля.
        year            — год дел (число или строка), уходит в {{год_дел}};
        sheet_name      — имя листа; None -> default.

    Возвращает словарь:
        {"path": output_path, "records": [...], "mapping": {...},
         "count": <число непустых дел>}
    """
    records, mapping = read_result_xlsx(filepath, sheet_name=sheet_name)

    # Дополняем common_values годом (после None-фильтра, как в pipeline)
    cv = {k: ("" if v is None else v) for k, v in dict(common_values).items()}
    cv["год_дел"] = str(year) if year is not None else ""

    # Импорт здесь, чтобы не тянуть docx при импорте модуля
    from core.word_writer import write_word_result

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".",
                exist_ok=True)
    write_word_result(records, template_path, output_path, cv)

    count = sum(1 for r in records if str(r.get("title") or "").strip())
    return {
        "path": output_path,
        "records": records,
        "mapping": mapping,
        "count": count,
    }
