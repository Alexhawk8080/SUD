# -*- coding: utf-8 -*-
"""
Ядро обработки гражданских дел.

Порт процедуры ProcessLegalCasesFinal() из Module1.bas (VBA) 1:1:
сбор дел, фильтрация по году и алиментам, сквозная нумерация диапазона
номеров, формирование заголовков и записей результата.
"""

import re
from datetime import datetime

from .genitive import genitive_case
from .dative import dative_case
from .retention import get_retention_info
from .org_inflector import inflect_organization_name
from .category_check import (
    build_organization_lookup,
    extract_phrase,
    get_plaintiff_key,
    is_problematic,
    most_frequent,
)


# ---------------------------------------------------------------------------
# Вспомогательные функции (порты из Module1.bas)
# ---------------------------------------------------------------------------

def format_date(value) -> str:
    """Форматирование даты в dd.mm.yyyy (аналог Format(value, 'dd.mm.yyyy'))."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    # Число-серийный номер Excel (например 45121) не преобразуем
    return text


# fix_04: строгий формат номера дела — ПРЕФИКС-NNN/ГГГГ (числа, дефис, слэш)
_CASE_NUM_RE = re.compile(r"^(\d+)-(\d+)/(\d{4})$")


def is_valid_case_number(case_num, target_year) -> bool:
    """
    Проверка формата номера дела (IsValidCaseNumber): ПРЕФИКС-NNN/ГГГГ.

    fix_04: строгая проверка через регулярное выражение — все части
    числовые (префикс, номер, год), год в конце. Отсекает мусор вида
    «abc-def/2023», «2-3-4/2023», «2-хх/2023».
    """
    if case_num is None:
        return False
    s = str(case_num).strip()
    m = _CASE_NUM_RE.match(s)
    if not m:
        return False
    return m.group(3) == str(target_year)


def parse_case_number(case_num) -> int:
    """
    Извлечение числовой части номера: '2-3/2023' -> 3 (SafeCLng в VBA).

    fix_04: если номер не соответствует формату — возвращается 0
    без исключений.
    """
    if case_num is None:
        return 0
    s = str(case_num).strip()
    m = _CASE_NUM_RE.match(s)
    if not m:
        return 0
    return int(m.group(2))


def get_case_prefix(case_num) -> str:
    """
    Префикс номера дела: '2-3/2023' -> '2'.

    fix_04: если номер не соответствует формату — возвращается "".
    """
    if case_num is None:
        return ""
    s = str(case_num).strip()
    m = _CASE_NUM_RE.match(s)
    if not m:
        return ""
    return m.group(1)


def contains_alimony(category_text) -> bool:
    """Проверка на алиментное дело (ContainsAlimony)."""
    if category_text is None:
        return False
    return "алимент" in str(category_text).lower()


def extract_case_type(category_text) -> str:
    """Текст категории после ' О ' или ' Об ' (ExtractCaseType)."""
    if category_text is None:
        return ""
    text = " ".join(str(category_text).split())
    lower_text = text.lower()
    pos = lower_text.find(" о ")
    if pos == -1:
        pos = lower_text.find(" об ")
    if pos == -1:
        return ""
    case_type = text[pos:]
    if case_type.endswith("."):
        case_type = case_type[:-1]
    return " ".join(case_type.split())


def is_organization(name, exclusions) -> bool:
    """Определение организации по первому слову (IsOrganization)."""
    if name is None:
        return False
    first_word = str(name).strip().split(" ", 1)[0].lower()
    for item in exclusions:
        if first_word == str(item).strip().lower():
            return True
    return False


def process_names_list(names_text, case_type: str, exclusions) -> str:
    """
    Склонение списка имён (ProcessNamesList).

    case_type: "Genitive" — заявители, "Dative" — ответчики.

    Организации (справочник exclusions) склоняются по родовым словам
    («Администрация города» -> род. «Администрации города»); аббревиатуры
    и названия в кавычках остаются без изменений.
    """
    if names_text is None:
        return ""
    text = str(names_text)
    names = text.replace(",", ";").split(";")
    result_parts = []
    for raw in names:
        name = raw.strip()
        if not name:
            continue
        if is_organization(name, exclusions):
            name = inflect_organization_name(name, case_type)
        else:
            if case_type == "Genitive":
                name = genitive_case(name)
            elif case_type == "Dative":
                name = dative_case(name)
        result_parts.append(name)
    # Нормализация пробелов (убирает хвостовые пробелы от склонения ФИО без отчества)
    return " ".join("; ".join(result_parts).split())


def get_case_type_prefix(applicants, organizations: dict, exclusions) -> str:
    """
    Определение префикса «по иску»/«по заявлению» (GetCaseTypePrefix).

    organizations: dict название_организации -> тип подачи («по иску»/...).
    """
    if applicants is None or not str(applicants).strip():
        return "по заявлению"
    org_list = str(applicants).replace(",", ";").split(";")
    for raw in org_list:
        current_org = raw.strip()
        if not current_org:
            continue
        if is_organization(current_org, exclusions):
            for key, org_type in organizations.items():
                if key and str(key).strip().lower() in current_org.lower():
                    if org_type == "по иску":
                        return "по иску"
    return "по заявлению"


def build_empty_record(sequential: int) -> dict:
    """Пустая запись для пропущенного номера (только порядковый номер)."""
    return {
        "sequential": sequential,
        "title": "",
        "dates": "",
        "opis": "",
        "unit": "",
        "count": "",
        "retention": "",
        "note": "",
    }


def build_case_record(src_row, prefix: str, exclusions, organizations: dict,
                      keywords=None, texts=None, category=None) -> dict:
    """
    Формирование записи результата для одного дела (ProcessCase).

    category — категория дела, используемая для заголовка и срока хранения.
    Если None, берётся исходная категория из src_row (Доработка 6:
    сюда передаётся исправленная/автоподставленная категория).
    """
    case_num = src_row.get("case_number")
    start_date = format_date(src_row.get("date"))
    end_date = format_date(src_row.get("end_date")) or start_date

    if category is None:
        category = src_row.get("category")

    # VBA-логика extract_case_type ищет « О » С ПРОБЕЛОМ ПЕРЕД «О».
    # Для исправленных категорий вида «о взыскании ...» (фраза в начале)
    # используем extract_phrase как запасной вариант (Доработка 6).
    case_type = extract_case_type(category)
    if not case_type:
        case_type = extract_phrase(category) or ""
    retention_info = get_retention_info(category, keywords, texts)

    # Доработка 8: в готовом результате имена УЖЕ в нужном падеже
    # (истец — родительный, ответчик — дательный), а префикс уже в заголовке.
    # Повторно не склоняем и префикс не пересчитываем.
    if src_row.get("legacy_raw"):
        applicants = src_row.get("applicants") or ""
        respondents = src_row.get("respondents") or ""
        prefix = src_row.get("prefix") or prefix
    else:
        applicants = process_names_list(
            src_row.get("applicants"), "Genitive", exclusions)
        respondents = process_names_list(
            src_row.get("respondents"), "Dative", exclusions)

    title = (f"Гражданское дело №{case_num} {prefix} {applicants} "
             f"к {respondents} {case_type.lower()}")

    # fix_10_v2: sanitize — start_date/end_date могут содержать
    # артефакты из исходного Excel
    from .text_utils import sanitize_text
    start_clean = sanitize_text(start_date) if start_date else ""
    end_clean = sanitize_text(end_date) if end_date else ""

    # Доработка 7: готовый результат — переносим данные «как есть»
    # (даты, № описи, № ед.хр., кол-во, срок хранения; пусто -> пусто).
    if src_row.get("legacy_raw"):
        dates_value = src_row.get("dates_raw") or ""
        opis_value = src_row.get("opis_raw") or ""
        unit_value = src_row.get("unit_raw") or ""
        count_value = src_row.get("count_raw") or ""
        retention_value = src_row.get("retention_raw") or ""
    else:
        dates_value = f"{start_clean}\n{end_clean}"
        opis_value = src_row.get("opis_number")
        unit_value = src_row.get("unit_number")
        count_value = 1
        retention_value = retention_info

    return {
        "sequential": None,  # заполняется вызывающим кодом
        "title": title,
        "dates": dates_value,
        "opis": opis_value,
        "unit": unit_value,
        "count": count_value,
        "retention": retention_value,
        "note": src_row.get("note"),
    }


# ---------------------------------------------------------------------------
# Главная функция обработки (порт ProcessLegalCasesFinal)
# ---------------------------------------------------------------------------

def process_cases(rows, target_year, process_alimony: bool,
                  organizations: dict, exclusions,
                  keywords=None, texts=None,
                  category_fixes=None, auto_fix_map=None):
    """
    Обработка списка строк исходной таблицы.

    Параметры:
        rows             — список SourceRow (см. excel_reader);
        target_year      — год дел (число или строка);
        process_alimony  — включать ли алиментные дела;
        organizations    — dict: организация -> тип подачи;
        exclusions       — список первых слов-организаций (не склоняются);
        keywords/texts   — правила сроков хранения (см. retention);
        category_fixes   — Доработка 6: dict «номер дела -> категория»
                           (исправления, внесённые на странице проверки);
        auto_fix_map     — Доработка 6: dict «ключ истца -> [категории]»
                           из словаря БД case_categories; для проблемных дел
                           без явного исправления подставляется самая частая
                           категория.

    Возвращает кортеж (records, stats):
        records — список записей результата (словари);
        stats   — словарь статистики обработки.
    """
    target_year = str(target_year)
    # fix_02: нормализация ключей исправлений — номера дел могут прийти
    # из Excel или формы с хвостовыми/неразрывными пробелами
    category_fixes = {
        str(k).strip(): v for k, v in (category_fixes or {}).items()
    }
    auto_fix_map = auto_fix_map or {}
    org_lookup = build_organization_lookup(exclusions)

    # 1. Сбор информации о всех делах
    case_list = {}  # номер -> индекс строки в rows
    min_num, max_num = 10 ** 9, 0
    case_prefix = ""

    for idx, row in enumerate(rows):
        case_num = row.get("case_number")
        if not is_valid_case_number(case_num, target_year):
            continue
        num = parse_case_number(case_num)
        case_list[num] = idx
        if num < min_num:
            min_num = num
        if num > max_num:
            max_num = num
        if not case_prefix:
            case_prefix = get_case_prefix(case_num)

    # 2. Фильтрация дел (с учётом настройки алиментов)
    case_numbers = {}
    valid_count = 0
    for num, idx in case_list.items():
        if process_alimony or not contains_alimony(rows[idx].get("category")):
            case_numbers[num] = idx
            valid_count += 1

    # 3. Формирование результата с пустыми строками для пропусков
    records = []
    sequential = 1
    auto_fixed_count = 0

    if case_list:
        for num in range(min_num, max_num + 1):
            if num in case_numbers:
                idx = case_numbers[num]
                prefix = get_case_type_prefix(
                    rows[idx].get("applicants"), organizations, exclusions)

                # Доработка 6: исправление отсутствующей категории
                category = rows[idx].get("category")
                if is_problematic(category):
                    # fix_02: ключ ищем по нормализованному значению
                    case_num = str(rows[idx].get("case_number") or "").strip()
                    if case_num in category_fixes and category_fixes[case_num]:
                        category = category_fixes[case_num]
                    elif auto_fix_map:
                        key, _label, _is_org = get_plaintiff_key(
                            rows[idx].get("applicants"), org_lookup)
                        dict_cats = auto_fix_map.get(key, [])
                        if dict_cats:
                            category = most_frequent(dict_cats)
                            auto_fixed_count += 1

                record = build_case_record(rows[idx], prefix, exclusions,
                                           organizations, keywords, texts,
                                           category=category)
                record["sequential"] = sequential
            else:
                record = build_empty_record(sequential)
            records.append(record)
            sequential += 1

    # 4. Статистика (для отчёта пользователю)
    stats = {
        "case_prefix": case_prefix,
        "min_case_num": min_num if case_list else 0,
        "max_case_num": max_num if case_list else 0,
        "total_in_range": (max_num - min_num + 1) if case_list else 0,
        "valid_count": valid_count,
        "skipped_numbers": (max_num - min_num + 1 - len(case_list)) if case_list else 0,
        "alimony_excluded": len(case_list) - len(case_numbers),
        "process_alimony": process_alimony,
        "target_year": target_year,
        "auto_fixed": auto_fixed_count,  # Доработка 6: автоподстановок из словаря
    }
    return records, stats