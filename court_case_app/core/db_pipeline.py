# -*- coding: utf-8 -*-
"""
Связка «файл -> БД» для новой иерархии (court_areas -> court_years ->
source_files -> cases).

Публичный API (D4a):
    save_year_source_from_xlsx(conn, court_year_id, filepath, filename, ...)
        — прочитать .xlsx/.xlsm, разобрать дела, сохранить BLOB+метаданные
          в source_files и все дела в cases.

Не путать с core/pipeline.py — там старая логика «файл -> результат-файл».
"""

import os

from core.category_check import is_problematic
from core.case_processor import (
    contains_alimony,
    format_date,
    is_valid_case_number,
)
from core.excel_reader import read_source_table
from database import db as _db


def _row_to_case(row, target_year, row_index: int,
                 case_type: str = "civil") -> dict:
    """Преобразует SourceRow в dict для db.add_cases_bulk."""
    case_number = row.get("case_number")
    category = row.get("category")

    valid = bool(is_valid_case_number(case_number, target_year))
    alimony = contains_alimony(category)
    problematic = is_problematic(category)

    skip_reason = ""
    if not valid:
        skip_reason = "неверный формат или год номера дела"
    elif alimony:
        skip_reason = "алиментное дело"

    return {
        "case_type": case_type,
        "row_index": row_index,
        "date": format_date(row.get("date")),
        "case_number": "" if case_number is None else str(case_number).strip(),
        "applicants": "" if row.get("applicants") is None else str(row.get("applicants")),
        "respondents": "" if row.get("respondents") is None else str(row.get("respondents")),
        "category": "" if category is None else str(category),
        "opis_number": "" if row.get("opis_number") is None else str(row.get("opis_number")),
        "unit_number": "" if row.get("unit_number") is None else str(row.get("unit_number")),
        "note": "" if row.get("note") is None else str(row.get("note")),
        "end_date": format_date(row.get("end_date")),
        "is_valid": valid,
        "is_alimony": alimony,
        "is_problematic": problematic,
        "skip_reason": skip_reason,
    }


def save_year_source_from_xlsx(conn, court_year_id: int, filepath: str,
                               filename: str, *,
                               sheet_name: str = "",
                               header_row: int = None,
                               mapping: dict = None,
                               file_kind: str = "source",
                               case_type: str = "civil") -> dict:
    """
    Читает файл, разбирает дела, сохраняет BLOB+метаданные в source_files
    и разобранные дела в cases.

    Параметры:
        conn            — соединение SQLite (уже открыто);
        court_year_id   — id года (court_years.id);
        filepath        — путь к .xlsx/.xlsm;
        filename        — имя файла (сохраняется в source_files.filename);
        sheet_name      — имя листа (для метаданных);
        header_row      — номер строки заголовков (None = автоопределение);
        mapping         — ручной маппинг ролей (None = автоопределение);
        file_kind       — 'source' | 'processed';
        case_type       — 'civil' | 'admin'.

    Возвращает dict:
        {
          "source_file_id": int,
          "row_count": int,          # всего разобрано строк
          "valid_count": int,        # is_valid
          "alimony_count": int,      # is_alimony
          "problematic_count": int,  # is_problematic
          "mapping": dict,           # итоговый маппинг ролей
        }

    Бросает ValueError (нет года, нет файла) или BadFileError.
    """
    if not os.path.exists(filepath):
        raise ValueError(f"Файл не найден: {filepath}")

    # Проверяем существование года + берём его year
    rec = _db.get_court_year(conn, court_year_id)
    if not rec:
        raise ValueError(f"Год id={court_year_id} не найден")
    target_year = int(rec["year"])

    # Читаем содержимое как BLOB
    with open(filepath, "rb") as f:
        content = f.read()

    # Разбор
    headers, rows, used_mapping = read_source_table(
        filepath, mapping=mapping, header_row=header_row)

    # Преобразуем строки в дела
    cases = []
    valid_count = 0
    alimony_count = 0
    problematic_count = 0
    for idx, row in enumerate(rows, start=1):
        case = _row_to_case(row, target_year, idx, case_type=case_type)
        if case["is_valid"]:
            valid_count += 1
        if case["is_alimony"]:
            alimony_count += 1
        if case["is_problematic"]:
            problematic_count += 1
        cases.append(case)

    # Сохраняем BLOB + метаданные
    sfid = _db.save_source_file(
        conn, court_year_id, filename, content,
        file_kind=file_kind,
        sheet_name=sheet_name or "",
        header_row=int(header_row or 0),
        mapping=used_mapping or {},
        row_count=len(cases))

    # Сохраняем дела
    if cases:
        _db.add_cases_bulk(conn, sfid, cases)

    return {
        "source_file_id": sfid,
        "row_count": len(cases),
        "valid_count": valid_count,
        "alimony_count": alimony_count,
        "problematic_count": problematic_count,
        "mapping": dict(used_mapping or {}),
    }


# ============================================================================
# D4b: обработка + экспорт
# ============================================================================

import re as _re

from core.case_processor import process_cases


_CASE_NUM_IN_TITLE_RE = _re.compile(r"№\s*(\d+-\d+/\d{4})")


def _extract_case_number_from_title(title: str) -> str:
    """Номер дела из заголовка: 'Гражданское дело №2-3/2020 ...' -> '2-3/2020'."""
    if not title:
        return ""
    m = _CASE_NUM_IN_TITLE_RE.search(str(title))
    return m.group(1) if m else ""


def process_year(conn, court_year_id: int, *, case_type: str = "civil",
                 process_alimony: bool = False,
                 category_fixes: dict = None,
                 auto_fix_enabled: bool = True,
                 court_area_id: int = None,
                 source_file_id: int = None) -> dict:
    """
    Прогоняет обработку по данным из БД и сохраняет результат.

    Алгоритм:
      1. Берёт актуальный (is_current=1) source_file за указанный год
         или конкретную версию (source_file_id).
      2. Читает его дела (cases) нужного case_type.
      3. Прогоняет process_cases (та же логика, что и раньше).
      4. Сохраняет processing_results + processing_result_rows.
      5. Помечает результат как устаревший, если source_file уже не актуален.

    Возвращает:
        {
          "result_id": int,
          "source_file_id": int,
          "record_count": int,
          "stats": dict,
          "target_year": int,
        }
    """
    # 1. source_file
    if source_file_id is not None:
        sf = _db.get_source_file(conn, source_file_id)
        if not sf:
            raise ValueError(f"source_files id={source_file_id} не найден")
        if sf["court_year_id"] != court_year_id:
            raise ValueError(
                f"source_file id={source_file_id} относится к другому году")
    else:
        sf = _db.get_current_source_file(
            conn, court_year_id, file_kind="source")
        if not sf:
            raise ValueError(
                "Нет актуального исходного файла для этого года. "
                "Сначала загрузите файл.")

    # 2. Год + дела
    cy = _db.get_court_year(conn, court_year_id)
    if not cy:
        raise ValueError(f"Год id={court_year_id} не найден")
    target_year = int(cy["year"])

    raw_cases = _db.list_cases(
        conn, source_file_id=sf["id"], case_type=case_type)
    if not raw_cases:
        raise ValueError(
            f"В файле нет дел типа {case_type}. Нечего обрабатывать.")

    # 3. Преобразование в строки для process_cases
    rows = []
    for c in raw_cases:
        rows.append({
            "date": c["date"],
            "case_number": c["case_number"],
            "applicants": c["applicants"],
            "respondents": c["respondents"],
            "category": c["category"],
            "opis_number": c["opis_number"],
            "unit_number": c["unit_number"],
            "note": c["note"],
            "end_date": c["end_date"],
        })

    # 4. Справочники
    organizations = _db.organizations_dict(conn)
    exclusions = _db.organization_names(conn)
    keywords, texts = _db.load_retention_rules(conn)
    auto_fix_map = (_db.case_categories_map(conn)
                    if auto_fix_enabled else None)

    # 5. Обработка
    records, stats = process_cases(
        rows, target_year, process_alimony,
        organizations, exclusions,
        keywords=keywords, texts=texts,
        category_fixes=category_fixes or None,
        auto_fix_map=auto_fix_map or None)

    # 6. Дополняем case_number (извлекаем из title)
    for r in records:
        r["case_number"] = _extract_case_number_from_title(r.get("title", ""))

    # 7. Сохраняем результат
    rid = _db.save_processing_result(
        conn, court_year_id, case_type, records,
        stats=stats, source_file_id=sf["id"],
        output_format="word",
        process_alimony=process_alimony,
        target_year=target_year,
        court_area_id=court_area_id)

    # 8. Если source_file не актуален — помечаем результат устаревшим
    if not sf["is_current"]:
        _db.set_result_stale(conn, rid, True)

    # record_count = число непустых записей (совпадает с шапкой БД),
    # т.к. в records могут быть пустые строки для сквозной нумерации.
    filled_count = sum(1 for r in records
                       if str(r.get("title") or "").strip())

    return {
        "result_id": rid,
        "source_file_id": sf["id"],
        "record_count": filled_count,
        "stats": stats,
        "target_year": target_year,
    }


def export_year_result_to_file(conn, result_id: int, *, template_path: str,
                               output_dir: str,
                               output_format: str = "word",
                               columns: list = None) -> dict:
    """
    Экспорт сохранённого результата в .docx / .xlsx.

    Параметры:
        conn         — соединение SQLite;
        result_id    — id processing_results;
        template_path — путь к Word-шаблону (для 'word');
        output_dir   — папка для выходного файла;
        output_format — 'word' | 'excel';
        columns      — список столбцов для Excel (None = все 8).

    Возвращает:
        {"path": ..., "filename": ..., "record_count": ...}
    """
    if output_format not in ("word", "excel"):
        raise ValueError(
            f"output_format должен быть 'word' или 'excel', "
            f"получено {output_format!r}")

    res = _db.get_processing_result(conn, result_id)
    if not res:
        raise ValueError(f"processing_results id={result_id} не найден")

    rows = _db.list_result_rows(conn, result_id)

    # Реквизиты: из court_years выбранного участка / года; fallback — settings
    common = {}
    if res["court_area_id"]:
        common = _db.court_area_settings_dict(
            conn, res["court_area_id"], year=res["target_year"])
    if not common:
        # fallback на settings (там только служебные ключи, но на всякий)
        settings = _db.get_settings(conn)
        common = {k: v for k, v in settings.items()
                  if k in ("судебный_участок", "судья", "секретарь",
                           "дата_утверждения", "дата_акта", "номер_акта",
                           "дата_подписи", "протокол_эк_дата",
                           "протокол_эк_номер")}
    common["год_дел"] = str(res["target_year"])

    # Имя файла (единый формат — см. core/filename_utils)
    from core.filename_utils import make_act_filename
    num = str(common.get("судебный_участок") or "").strip()
    ext = "docx" if output_format == "word" else "xlsx"
    filename = make_act_filename(
        num, res.get("case_type"), res["target_year"], ext)

    import os as _os
    _os.makedirs(output_dir, exist_ok=True)
    path = _os.path.join(output_dir, filename)

    # Записи для writer'ов: 8 полей как ожидают word_writer/excel_writer
    records = []
    for r in rows:
        records.append({
            "sequential": r["sequential"],
            "title": r["title"],
            "dates": r["dates"],
            "opis": r["opis"],
            "unit": r["unit"],
            "count": r["count"],
            "retention": r["retention"],
            "note": r["note"],
        })

    if output_format == "word":
        from core.word_writer import write_word_result
        write_word_result(records, template_path, path, common)
    else:
        from core.excel_writer import write_excel_result, DEFAULT_KEYS
        write_excel_result(records, path, columns=columns or DEFAULT_KEYS)

    return {
        "path": path,
        "filename": filename,
        "record_count": len(records),
    }
