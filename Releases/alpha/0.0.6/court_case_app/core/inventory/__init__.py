# -*- coding: utf-8 -*-
"""
Пакет core.inventory — модуль «Внутренняя опись» (Word -> лист «Таблица»).

Назначение: перенести данные из docx-описи (административные и гражданские
дела) в расчётную «Таблицу» Excel (21 столбец A–U).

Этап 14a — чтение docx:
    InventoryError, BadInventoryFileError, NoInventoryTableError,
    FlowBreakError, MixedTypesError,
    read_inventory_docx, find_inventory_tables, extract_rows,
    clean_name, parse_number, make_record,
"""

from .exceptions import (  # noqa: F401
    BadInventoryFileError,
    FlowBreakError,
    InventoryError,
    MixedTypesError,
    NoInventoryTableError,
)
from .docx_reader import (  # noqa: F401
    HEADER_HINTS,
    clean_name,
    extract_rows,
    find_inventory_tables,
    make_record,
    parse_number,
    read_inventory_docx,
)

# --- 14b: столбец C (тип документа) ---------------------------------------

from .normalizer import (  # noqa: F401
    ALL_DOC_TYPES,
    CASE_ADMIN,
    CASE_CIVIL,
    detect_case_type,
    detect_doc_kind,
    normalize_name,
)

# --- 14b: столбцы D/E/F/G (номера, двойные номера, год потока) -------------

from .case_number import (  # noqa: F401
    build_from_rows,
    build_stream,
    choose_number,
    detect_flow_year,
    parse_numbers,
    resolve_chosen_list,
)

# --- 14c: сборка потока из нескольких docx ---------------------------------

from .flow import (  # noqa: F401
    build_flow,
    combine_type,
    doc_case_type,
    doc_numbers,
    doc_range,
    stitch_docs,
)

# --- 14d: шаблон xlsx и запись результата ---------------------------------

from .sheets_io import (  # noqa: F401
    CLEAR_FILL_ONE,
    CLEAR_REPLICATE,
    FIRST_DATA_ROW,
    FORMULA_COLUMNS,
    TEMPLATE_SHEET,
    clean_template,
    detect_last_template_row,
    extend_formulas,
    extend_vlookup_ranges,
    find_template_sheet,
    shift_formula,
)
from .writer import (  # noqa: F401
    ATTENTION_COLUMNS,
    page_count,
    prepare_rows,
    write_result,
)
