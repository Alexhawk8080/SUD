# -*- coding: utf-8 -*-
"""
Ядро обработки административных дел (D8b).

Отличия от гражданских (case_processor):
  * одно лицо вместо пары «заявители/ответчики»;
  * заголовок «Дело об административном правонарушении №... в отношении
    {лицо} по {статья}»;
  * статья дедуплицируется; суффикс «КоАП РФ» добавляется только если
    статья не региональная (нет «ЗСО»);
  * конечная дата = начальная + 2 месяца (календарно) с переносом на
    следующий рабочий день (выходные + фиксированные праздники РФ);
  * срок хранения — единый для года (передаётся снаружи).
"""

import calendar
import re
from datetime import date, datetime, timedelta

from .genitive import genitive_case

# Номер дела: ПРЕФИКС-NNN/ГГГГ (5-1/2020)
_CASE_NUM_RE = re.compile(r"^(.+)-(\d+)/(\d{4})$")

# Организации (первое слово) — не склоняются
_ORG_PREFIXES = (
    "ООО", "АО", "ЗАО", "ОАО", "ПАО", "НАО", "ИП", "МУП", "ГУП",
    "ГК", "ГСК", "ТСЖ", "УО", "УПФ", "ИФНС", "ПКО", "МФК", "МФО",
    "КПК", "МДОУ", "МОО", "МОУ", "НЭП", "ПСК", "СРОО", "УК",
)

# Фиксированные праздничные дни РФ (месяц, день)
_RU_HOLIDAYS = {
    (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8),
    (2, 23), (3, 8), (5, 1), (5, 9), (6, 12), (11, 4),
}


# ---------------------------------------------------------------------------
# Номер дела
# ---------------------------------------------------------------------------

def is_valid_admin_case_number(case_num, target_year) -> bool:
    """Проверка формата номера admin-дела (ПРЕФИКС-NNN/ГГГГ) и года."""
    if case_num is None:
        return False
    s = str(case_num).strip()
    m = _CASE_NUM_RE.match(s)
    if not m:
        return False
    return m.group(3) == str(target_year)


def parse_admin_case_number(case_num) -> int:
    """Числовая часть номера: '5-3/2020' -> 3 (0 при несоответствии)."""
    if case_num is None:
        return 0
    m = _CASE_NUM_RE.match(str(case_num).strip())
    return int(m.group(2)) if m else 0


def get_admin_case_prefix(case_num) -> str:
    """Префикс номера: '5-3/2020' -> '5' ('' при несоответствии)."""
    if case_num is None:
        return ""
    m = _CASE_NUM_RE.match(str(case_num).strip())
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Лицо (склонение)
# ---------------------------------------------------------------------------

def is_organization_name(name) -> bool:
    """Организация ли (по первому слову: ООО/АО/ИП/...)."""
    if not name:
        return False
    first = str(name).strip().split(" ", 1)[0].upper().strip('"«»')
    return first in _ORG_PREFIXES


def inflect_person(name) -> str:
    """
    Склонение лица в родительный падеж.

    Организации (ООО/АО/ИП/...) — «как есть»; физлица — genitive_case.
    """
    if not name:
        return ""
    text = " ".join(str(name).split())
    if is_organization_name(text):
        return text
    return genitive_case(text)


# ---------------------------------------------------------------------------
# Статья
# ---------------------------------------------------------------------------

def normalize_article(article) -> str:
    """
    Нормализация статьи: дедупликация через ';' + суффикс «КоАП РФ».

    * «ст. 15.6 ч. 1; ст. 15.6 ч. 1; » -> «ст. 15.6 ч. 1 КоАП РФ»
    * «1.1 ч.1 ЗСО №104» -> «1.1 ч.1 ЗСО №104» (суффикс не добавляется)
    """
    if article is None:
        return ""
    text = str(article).strip()
    if not text:
        return ""

    # Дедупликация частей, разделённых ';'
    parts = []
    for raw in text.split(";"):
        part = " ".join(raw.split())
        if part and part not in parts:
            parts.append(part)
    result = "; ".join(parts)
    if not result:
        return ""

    # Суффикс «КоАП РФ» — только для не-региональных статей
    if "ЗСО" in result.upper():
        return result
    if "КОАП" in result.upper():
        return result
    return result + " КоАП РФ"


# ---------------------------------------------------------------------------
# Даты
# ---------------------------------------------------------------------------

def _add_months(d: date, months: int) -> date:
    """Прибавление месяцев с корректной обработкой конца месяца."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _is_working_day(d: date) -> bool:
    """Рабочий ли день (не сб/вс и не праздник РФ)."""
    if d.weekday() >= 5:  # 5 = сб, 6 = вс
        return False
    if (d.month, d.day) in _RU_HOLIDAYS:
        return False
    return True


def next_working_day(d: date) -> date:
    """Следующий рабочий день (если d — рабочий, возвращается d)."""
    while not _is_working_day(d):
        d += timedelta(days=1)
    return d


def parse_date(value):
    """Разбор даты из Excel: datetime/date/строка 'dd.mm.yyyy' -> date|None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def format_date_ru(d) -> str:
    """Форматирование даты в dd.mm.yyyy."""
    if d is None:
        return ""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%d.%m.%Y")


def compute_end_date(start_value):
    """
    Конечная дата = начальная + 2 месяца, с переносом на рабочий день.

    Возвращает date|None (None, если начальная дата не распознана).
    """
    start = parse_date(start_value)
    if start is None:
        return None
    return next_working_day(_add_months(start, 2))


# ---------------------------------------------------------------------------
# Заголовок и запись
# ---------------------------------------------------------------------------

def build_admin_title(case_num, person, article) -> str:
    """Заголовок admin-дела."""
    return (f"Дело об административном правонарушении №{case_num} "
            f"в отношении {person} по {article}")


def build_admin_record(row, retention: str) -> dict:
    """
    Формирование записи результата для одного admin-дела.

    row — AdminRow (см. admin_reader).
    retention — единый срок хранения для года.
    """
    case_num = str(row.get("case_number") or "").strip()
    person = inflect_person(row.get("person"))
    article = normalize_article(row.get("article"))

    start = parse_date(row.get("date"))
    end = compute_end_date(row.get("date"))
    dates_value = f"{format_date_ru(start)}\n{format_date_ru(end)}".strip()

    title = build_admin_title(case_num, person, article)

    return {
        "sequential": None,  # заполняется вызывающим кодом
        "title": title,
        "dates": dates_value,
        "opis": "",          # у admin нет № описи
        "unit": "",          # у admin нет № ед.хр.
        "count": 1,
        "retention": retention,
        "note": str(row.get("task") or ""),
        # служебные поля для БД (переиспользование колонок cases)
        "case_number": case_num,
        "applicants": person,
        "respondents": "",
        "category": article,
        "opis_number": str(row.get("in_number") or ""),
        "unit_number": "",
        "act_state": str(row.get("act_state") or ""),
    }


def build_empty_admin_record(sequential: int) -> dict:
    """Пустая запись для пропущенного номера."""
    return {
        "sequential": sequential,
        "title": "",
        "dates": "",
        "opis": "",
        "unit": "",
        "count": "",
        "retention": "",
        "note": "",
        "case_number": "",
        "applicants": "",
        "respondents": "",
        "category": "",
        "opis_number": "",
        "unit_number": "",
        "act_state": "",
    }


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def process_admin_cases(rows, target_year, retention: str):
    """
    Обработка списка admin-строк.

    Параметры:
        rows        — список AdminRow (см. admin_reader);
        target_year — год дел (число/строка);
        retention   — единый срок хранения для года.

    Возвращает кортеж (records, stats):
        records — записи результата (с пустыми строками для пропусков);
        stats   — статистика обработки.
    """
    target_year = str(target_year)

    case_list = {}  # номер -> индекс строки
    min_num, max_num = 10 ** 9, 0
    case_prefix = ""

    for idx, row in enumerate(rows):
        case_num = row.get("case_number")
        if not is_valid_admin_case_number(case_num, target_year):
            continue
        num = parse_admin_case_number(case_num)
        case_list[num] = idx
        if num < min_num:
            min_num = num
        if num > max_num:
            max_num = num
        if not case_prefix:
            case_prefix = get_admin_case_prefix(case_num)

    records = []
    sequential = 1
    if case_list:
        for num in range(min_num, max_num + 1):
            if num in case_list:
                record = build_admin_record(
                    rows[case_list[num]], retention)
                record["sequential"] = sequential
            else:
                record = build_empty_admin_record(sequential)
            records.append(record)
            sequential += 1

    stats = {
        "case_prefix": case_prefix,
        "min_case_num": min_num if case_list else 0,
        "max_case_num": max_num if case_list else 0,
        "total_in_range": (max_num - min_num + 1) if case_list else 0,
        "valid_count": len(case_list),
        "skipped_numbers": ((max_num - min_num + 1 - len(case_list))
                            if case_list else 0),
        "target_year": target_year,
    }
    return records, stats
