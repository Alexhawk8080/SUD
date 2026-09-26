# -*- coding: utf-8 -*-
"""
Разбор номеров дел и построение потока (этап 14b, решения 4–7, 16–18).

Столбцы «Таблицы»:
    D — префикс (переносится как есть; при двойных номерах — выбранного);
    E — приращение номера: E_i = F_i − F_{i−1} (для i>4; E4 не заполняется);
    F — номер дела: F4 = числовая часть первого номера потока,
        далее формула =F_{i-1}+E_i;
    G — год выбранного номера (число).

Двойные номера вида «№ 11-47/2018 (№ 2-14/2018)» — выбор номера,
который «в потоке» (решение 16).

Год потока — самый частый год (решение 18).
"""

import re
from collections import Counter

# --- Регулярные выражения ---------------------------------------------------

# Номер дела: «2-14/2018», «11-47/2018», «2а-3/2018» (буквенный префикс).
_CASE_RE = re.compile(r"(\d+[а-яА-Я]?)\s*-\s*(\d+)\s*/\s*(\d{4})")

# Префикс: ведущие цифры + возможная буква («2а» -> «2а»).
_PREFIX_RE = re.compile(r"^\s*(\d+[а-яА-Я]?)")


def parse_numbers(name) -> list:
    """
    Все номера дел в тексте (по порядку появления).

    Возвращает список словарей:
        {prefix, number, year, raw}
    где number — числовая часть, prefix — как есть («2а», «11»).
    """
    text = " ".join(str(name or "").split())
    result = []
    for m in _CASE_RE.finditer(text):
        result.append({
            "prefix": m.group(1),
            "number": int(m.group(2)),
            "year": int(m.group(3)),
            "raw": m.group(0).replace(" ", ""),
        })
    return result


def choose_number(numbers, prev, next_) -> dict:
    """
    Выбор номера для двойных номеров (решение 16).

    prev / next_ — выбранные номера соседей: {prefix, number} или None.

    «Выпал» из потока, если:
        - префикс отличается от префикса ОБОИХ доступных соседей;
        - число не укладывается между соседними числами.
    Для первой строки смотрим только следующего, для последней — только
    предыдущего.

    Возвращает {chosen, fell_out, reason}:
        chosen  — выбранный номер (dict) или None;
        fell_out — True, если первый номер выпал (взят второй);
        reason  — текст причины для «Требует внимания» либо "".
    """
    if not numbers:
        return {"chosen": None, "fell_out": False, "reason": ""}
    if len(numbers) == 1:
        return {"chosen": numbers[0], "fell_out": False, "reason": ""}

    def fits(cand):
        checks = []
        if prev is not None:
            checks.append(cand["prefix"] == prev["prefix"]
                          and cand["number"] >= prev["number"])
        if next_ is not None:
            checks.append(cand["prefix"] == next_["prefix"]
                          and cand["number"] <= next_["number"])
        return any(checks) if checks else True

    if fits(numbers[0]):
        return {"chosen": numbers[0], "fell_out": False, "reason": ""}
    if fits(numbers[1]):
        return {"chosen": numbers[1], "fell_out": True,
                "reason": "первый номер выпал из потока — взят второй"}
    return {"chosen": numbers[0], "fell_out": False,
            "reason": "оба номера выпали из потока — взят первый"}


# ---------------------------------------------------------------------------
# Год потока (решение 18)
# ---------------------------------------------------------------------------

def detect_flow_year(years) -> dict:
    """
    Определяет год потока по списку годов.

    Возвращает:
        {"year": int | None,
         "dominant": bool,        # один год доминирует (>= 90%)
         "needs_choice": bool,    # второй год значимый (>= 10%)
         "attention": [год, ...]} # «чужие» годы для пометки
    """
    counts = Counter(y for y in years if y)
    if not counts:
        return {"year": None, "dominant": False,
                "needs_choice": False, "attention": []}
    total = sum(counts.values())
    year, cnt = counts.most_common(1)[0]
    share = cnt / total
    others = [y for y in counts if y != year]
    needs_choice = bool(others) and (1 - share) >= 0.10
    dominant = share >= 0.90
    attention = []
    if needs_choice:
        attention = sorted(others)
    elif others and dominant:
        attention = sorted(others)
    return {"year": year, "dominant": dominant,
            "needs_choice": needs_choice, "attention": attention}


# ---------------------------------------------------------------------------
# Столбцы D / E / F / G по потоку (решения 4–7)
# ---------------------------------------------------------------------------

def build_stream(chosen_list, flow_year=None) -> dict:
    """
    Строит столбцы D/E/F/G для потока выбранных номеров.

    chosen_list — список выбранных номеров ({prefix, number, year}) по порядку.
    flow_year   — год потока (если None, определяется по данным).

    Возвращает:
        {"f4": int | None,                     # база F4 (первый номер)
         "year": int | None,                   # год потока
         "rows": [ {D, E, F, G, attention}, ... ],
         "year_plan": {...},                   # результат detect_flow_year
         "prefixes": [...] }                   # встреченные префиксы (D «как есть»)
    """
    valid = [c for c in chosen_list if c]
    if not valid:
        return {"f4": None, "year": flow_year, "rows": [], "year_plan": {}}

    plan = detect_flow_year([c["year"] for c in valid])
    year = flow_year or plan["year"]

    prefixes = []
    for c in valid:
        if c["prefix"] not in prefixes:
            prefixes.append(c["prefix"])

    rows = []
    f4 = valid[0]["number"]
    prev_number = None
    for i, c in enumerate(valid):
        row_attention = ""
        g = c["year"]
        if year and g != year:
            g = year
            row_attention = f"год исправлен на поток ({year}) вместо {c['year']}"
        if i == 0:
            e = None  # E4 не заполняется — F4 задаётся из Word
        else:
            e = c["number"] - prev_number
        rows.append({"D": c["prefix"], "E": e, "F": c["number"],
                     "G": g, "attention": row_attention})
        prev_number = c["number"]

    return {"f4": f4, "year": year, "rows": rows,
            "prefixes": prefixes, "year_plan": plan}


def resolve_chosen_list(rows) -> list:
    """
    Выбирает номер для каждой строки потока (двойные номера — решение 16).

    rows — список записей docx с полем «name».
    Двухпроходно: сначала черновой выбор (первый номер), затем уточнение
    с учётом выбранных номеров соседей.

    Возвращает список:
        {chosen, numbers, fell_out, reason}
    """
    numbers_list = [parse_numbers(r.get("name")) for r in rows]
    chosen = [nums[0] if nums else None for nums in numbers_list]

    for i, nums in enumerate(numbers_list):
        if len(nums) < 2:
            continue
        prev = chosen[i - 1] if i > 0 else None
        next_ = chosen[i + 1] if i + 1 < len(chosen) else None
        if prev is None and next_ is None:
            continue
        res = choose_number(nums, prev, next_)
        chosen[i] = res["chosen"]

    out = []
    for i, nums in enumerate(numbers_list):
        reason = ""
        fell_out = False
        if len(nums) >= 2:
            prev = chosen[i - 1] if i > 0 else None
            next_ = chosen[i + 1] if i + 1 < len(chosen) else None
            res = choose_number(nums, prev, next_)
            reason, fell_out = res["reason"], res["fell_out"]
        out.append({"chosen": chosen[i], "numbers": nums,
                    "fell_out": fell_out, "reason": reason})
    return out


def build_from_rows(rows, flow_year=None) -> dict:
    """Строит поток (D/E/F/G) непосредственно из записей docx-описи."""
    resolved = resolve_chosen_list(rows)
    chosen_list = [r["chosen"] for r in resolved]
    stream = build_stream(chosen_list, flow_year=flow_year)
    stream["resolved"] = resolved
    return stream