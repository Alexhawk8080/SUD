# -*- coding: utf-8 -*-
"""
Пакет core.converter — конвертация между Excel-результатом и Word-актом.

Публичный API (B1):
    # Метки (A2)
    WORD_MARKER, EXCEL_MARKER, CURRENT_MARKER_VERSION,
    make_marker, parse_marker,
    mark_word_document, read_word_marker,
    mark_excel_workbook, read_excel_marker,

    # Ошибки (B1)
    ConverterError, BadFileError, WrongDirectionError,
    NoSheetsFound, NoValidCaseNumbers, NoCasesFound,
    SheetNotFound, ColumnsNotFound,

    # Листы (B1)
    RESULT_SHEET_NAME, verify_xlsx_content, verify_docx_content,
    inspect_sheets, sheet_exists,

    # Год (B1)
    extract_year, detect_year_from_numbers, detect_year_from_rows,
    make_warning_message,
"""

from .exceptions import (  # noqa: F401
    BadFileError,
    ColumnsNotFound,
    ConverterError,
    NoCasesFound,
    NoSheetsFound,
    NoValidCaseNumbers,
    SheetNotFound,
    WrongDirectionError,
)
from .markers import (  # noqa: F401
    CURRENT_MARKER_VERSION,
    EXCEL_MARKER,
    WORD_MARKER,
    make_marker,
    mark_excel_workbook,
    mark_word_document,
    parse_marker,
    read_excel_marker,
    read_word_marker,
)
from .sheets import (  # noqa: F401
    RESULT_SHEET_NAME,
    inspect_sheets,
    sheet_exists,
    verify_docx_content,
    verify_xlsx_content,
)
from .year_detect import (  # noqa: F401
    detect_year_from_numbers,
    detect_year_from_rows,
    extract_year,
    make_warning_message,
)


# --- B2: Excel -> Word ----------------------------------------------------

from .xlsx_to_word import (  # noqa: F401
    COLUMNS as XLSX_TO_WORD_COLUMNS,
    convert_xlsx_to_word,
    read_result_xlsx,
)


# --- C1: Word -> Excel ----------------------------------------------------

from .word_to_xlsx import (  # noqa: F401
    extract_refs_from_doc,
    extract_table_records,
    find_cases_table,
    read_act_docx,
)
