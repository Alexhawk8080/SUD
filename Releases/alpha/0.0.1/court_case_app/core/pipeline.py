# -*- coding: utf-8 -*-
"""
Конвейер обработки: загрузка файла -> чтение -> обработка -> выгрузка.

Связывает excel_reader, case_processor, excel_writer, word_writer и БД.
"""

import os

from core.excel_reader import read_source_table
from core.case_processor import process_cases
from core.excel_writer import write_excel_result, DEFAULT_KEYS
from core.word_writer import write_word_result


def process_upload(filepath: str, target_year, process_alimony: bool,
                   output_format: str, db_path: str, template_path: str,
                   output_dir: str, columns=None, mapping=None,
                   header_row=None, category_fixes=None,
                   auto_fix_enabled=True):
    """
    Полный цикл обработки загруженного файла.

    Параметры:
        filepath        — путь к загруженному .xlsx;
        target_year     — год дел;
        process_alimony — включать ли алиментные дела;
        output_format   — 'excel' или 'word';
        db_path         — путь к базе SQLite;
        template_path   — путь к Word-шаблону (для формата word);
        output_dir      — папка для результата;
        columns         — список столбцов для Excel (по умолчанию все);
        mapping         — ручной маппинг ролей (по умолчанию автоопределение);
        header_row      — номер строки с заголовками (None = автоопределение,
                          0 = нет заголовков);
        category_fixes  — Доработка 6: dict «номер дела -> категория»
                          (исправления со страницы проверки);
        auto_fix_enabled — Доработка 6: подставлять ли категории из словаря
                          case_categories для проблемных дел.

    Возвращает словарь:
        {"records": [...], "stats": {...}, "filename": "...", "title": "..."}
    """
    from database import db

    # 1. Чтение исходной таблицы
    headers, rows, used_mapping = read_source_table(
        filepath, mapping=mapping, header_row=header_row)

    return process_rows(
        rows, target_year, process_alimony, output_format,
        db_path, template_path, output_dir,
        columns=columns, category_fixes=category_fixes,
        auto_fix_enabled=auto_fix_enabled,
        used_mapping=used_mapping)


def process_rows(rows, target_year, process_alimony: bool,
                 output_format: str, db_path: str, template_path: str,
                 output_dir: str, columns=None, category_fixes=None,
                 auto_fix_enabled=True, used_mapping=None):
    """
    Обработка готового списка строк (SourceRow/dict) и запись результата.

    Используется как основным конвейером, так и для готовых результатов
    со страницы «Проверка категорий» (Доработка 6), где строки получены
    разбором заголовков (legacy_reader): даты/описи нет — поля остаются
    пустыми (обработчик предупреждает пользователя о неполноте данных).
    """
    if output_format not in ("excel", "word"):
        raise ValueError(
            f"Недопустимый формат результата: {output_format!r} "
            f"(ожидается 'excel' или 'word')")

    from database import db

    # 2. Данные из БД
    conn = db.init_db(db_path)
    try:
        organizations = db.organizations_dict(conn)
        organization_names = db.organization_names(conn)
        keywords, texts = db.load_retention_rules(conn)
        settings = db.get_settings(conn)
        auto_fix_map = db.case_categories_map(conn) if auto_fix_enabled else {}
    finally:
        conn.close()

    # 3. Обработка (организации не склоняются и определяют «по иску»)
    records, stats = process_cases(
        rows, target_year, process_alimony,
        organizations, organization_names, keywords, texts,
        category_fixes=category_fixes or None,
        auto_fix_map=auto_fix_map or None)

    if not records:
        raise ValueError(
            f"Нет дел за {target_year} год, соответствующих критериям!")

    # 4. Формирование результата
    os.makedirs(output_dir, exist_ok=True)

    # Доработка 7: имя файла «Акт уничтожения гражданских дел {участок}СУ {год}»
    # для обоих форматов (участок из настроек БД).
    num = str(settings.get("судебный_участок") or "").strip()
    base = "Акт уничтожения гражданских дел"
    if num:
        base += f" {num}СУ"
    base += f" {target_year}"

    if output_format == "word":
        # fix_03: убираем None из реквизитов — иначе в Word попадёт «None»
        common_values = {
            k: ("" if v is None else v) for k, v in dict(settings).items()
        }
        common_values["год_дел"] = str(target_year)
        filename = f"{base}.docx"
        out_path = os.path.join(output_dir, filename)
        write_word_result(records, template_path, out_path, common_values)
    else:
        cols = columns if columns else DEFAULT_KEYS
        filename = f"{base}.xlsx"
        out_path = os.path.join(output_dir, filename)
        write_excel_result(records, out_path, columns=cols)

    return {
        "records": records,
        "stats": stats,
        "filename": filename,
        "path": out_path,
        "used_mapping": used_mapping,
    }