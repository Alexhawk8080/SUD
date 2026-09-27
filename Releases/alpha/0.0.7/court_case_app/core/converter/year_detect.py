# -*- coding: utf-8 -*-
"""
Определение года из номеров дел.

Вход — список номеров («2-5/2019») или строк с полем case_number.
Логика (решения 6, 7):
    * берётся самый частый год;
    * при равенстве частот — наибольший;
    * возвращается статистика по всем годам и список «чужих» (не победивших).
"""

import re
from collections import Counter

from .exceptions import NoValidCaseNumbers

# Регулярка совпадает с core.case_processor._CASE_NUM_RE (fix_04).
# Не импортируем оттуда, чтобы не тянуть приватное имя.
_CASE_NUM_RE = re.compile(r"^(.+)-(\d+)/(\d{4})$")


def extract_year(case_num) -> str:
    """
    Год из номера вида «2-5/2019» -> «2019». Пустая строка, если номер
    не соответствует формату.
    """
    if case_num is None:
        return ""
    s = str(case_num).strip()
    m = _CASE_NUM_RE.match(s)
    return m.group(3) if m else ""


def detect_year_from_numbers(case_numbers) -> dict:
    """
    Определяет год по списку номеров.

    Возвращает:
        {
          "year":    "2020",             # самый частый, при равенстве — больший
          "years":   {"2019": 1, "2020": 2},
          "others":  [["2019", 1]],       # годы, не ставшие победителем
          "total":   3,                   # количество валидных номеров
        }

    Бросает NoValidCaseNumbers, если валидных номеров не нашлось.
    """
    years = []
    for cn in case_numbers or []:
        y = extract_year(cn)
        if y:
            years.append(y)

    if not years:
        raise NoValidCaseNumbers(
            "В файле не найдено ни одного номера вида «2-N/ГГГГ» — "
            "невозможно определить год.")

    counter = Counter(years)
    # Сортировка: сначала по частоте (убыв.), затем по значению года (убыв.)
    ranked = sorted(counter.items(), key=lambda kv: (kv[1], int(kv[0])),
                    reverse=True)
    winner = ranked[0][0]
    others = [[y, c] for y, c in ranked[1:]]
    return {
        "year": winner,
        "years": dict(counter),
        "others": others,
        "total": len(years),
    }


def detect_year_from_rows(rows) -> dict:
    """
    То же, но принимает список строк с методом .get('case_number')
    (SourceRow или dict).
    """
    nums = []
    for row in rows or []:
        try:
            nums.append(row.get("case_number"))
        except AttributeError:
            nums.append(None)
    return detect_year_from_numbers(nums)


def make_warning_message(result: dict) -> str:
    """
    Человекочитаемое предупреждение о «чужих» годах (решение 7).
    Пустая строка, если других годов нет.
    """
    others = result.get("others") or []
    if not others:
        return ""
    parts = [f"{y} ({c} шт.)" for y, c in others]
    return (f"Определён год {result['year']}. "
            f"Также в файле есть дела за: {', '.join(parts)}. "
            f"Убедитесь, что это ожидаемо.")
