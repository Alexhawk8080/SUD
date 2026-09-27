# -*- coding: utf-8 -*-
"""
Тесты ядра обработки административных дел (D8b).

Проверяет: номер дела, склонение лица (физлицо/организация), нормализацию
статьи, расчёт конечной даты (+2 месяца с переносом на рабочий день),
заголовок, формирование записи и сквозную нумерацию с пропусками.

Запуск: .venv\\Scripts\\python.exe court_case_app\\tests\\test_admin_processor.py
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.admin_processor import (
    is_valid_admin_case_number,
    parse_admin_case_number,
    get_admin_case_prefix,
    is_organization_name,
    inflect_person,
    normalize_article,
    _add_months,
    next_working_day,
    parse_date,
    format_date_ru,
    compute_end_date,
    build_admin_title,
    build_admin_record,
    process_admin_cases,
)

FAILED = 0
PASSED = 0


def check(name: str, actual, expected):
    global FAILED, PASSED
    ok = actual == expected
    if ok:
        PASSED += 1
        print(f"  OK   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось: {expected!r}\n       получено:  {actual!r}")


class FakeRow:
    """Минимальная заглушка AdminRow для тестов."""

    def __init__(self, **kw):
        self._d = kw

    def get(self, role):
        return self._d.get(role)


def main():
    print("[1] Номер дела")
    check("валидный 5-1/2020", is_valid_admin_case_number("5-1/2020", 2020), True)
    check("неверный год", is_valid_admin_case_number("5-1/2020", 2021), False)
    check("другой префикс валиден", is_valid_admin_case_number("2-1/2020", 2020), True)
    check("неверный формат", is_valid_admin_case_number("2-1-2020", 2020), False)
    check("None", is_valid_admin_case_number(None, 2020), False)
    check("parse 5-3/2020", parse_admin_case_number("5-3/2020"), 3)
    check("parse мусор", parse_admin_case_number("abc"), 0)
    check("prefix 5-3/2020", get_admin_case_prefix("5-3/2020"), "5")
    check("prefix мусор", get_admin_case_prefix("abc"), "")

    print("[2] Организация / физлицо")
    check("ООО Ромашка", is_organization_name("ООО Ромашка"), True)
    check("ИП Иванов", is_organization_name("ИП Иванов И.И."), True)
    check("МУП «Водоканал»", is_organization_name("МУП «Водоканал»"), True)
    check("физлицо", is_organization_name("Иванов Иван Иванович"), False)
    check("склонение физлица",
          inflect_person("Сурков Эдуард Владимирович"),
          "Суркова Эдуарда Владимировича")
    check("организация как есть",
          inflect_person("ООО Ромашка"), "ООО Ромашка")
    check("пустое лицо", inflect_person(""), "")

    print("[3] Статья")
    check("дедупликация + КоАП",
          normalize_article("ст. 15.6 ч. 1; ст. 15.6 ч. 1; "),
          "ст. 15.6 ч. 1 КоАП РФ")
    check("региональная ЗСО без суффикса",
          normalize_article("1.1 ч.1 ЗСО №104"),
          "1.1 ч.1 ЗСО №104")
    check("уже с КоАП",
          normalize_article("ст. 12.8 ч. 1 КоАП РФ"),
          "ст. 12.8 ч. 1 КоАП РФ")
    check("пустая статья", normalize_article(None), "")
    check("две разные статьи",
          normalize_article("ст. 1; ст. 2"),
          "ст. 1; ст. 2 КоАП РФ")

    print("[4] Даты")
    check("_add_months конец месяца (31.01 + 1)",
          _add_months(date(2020, 1, 31), 1), date(2020, 2, 29))
    check("_add_months через год",
          _add_months(date(2020, 11, 15), 3), date(2021, 2, 15))
    check("next_working_day: праздник 08.03.2020 (вс)",
          next_working_day(date(2020, 3, 8)), date(2020, 3, 9))
    check("next_working_day: рабочий день",
          next_working_day(date(2020, 3, 10)), date(2020, 3, 10))
    check("parse_date строка", parse_date("28.11.2019"), date(2019, 11, 28))
    check("parse_date мусор", parse_date("не дата"), None)
    check("format_date_ru", format_date_ru(date(2020, 1, 5)), "05.01.2020")
    check("compute_end_date 10.01.2020 -> 10.03.2020",
          compute_end_date("10.01.2020"), date(2020, 3, 10))
    check("compute_end_date 30.11.2020 -> 01.02.2021 (сб/вс)",
          compute_end_date("30.11.2020"), date(2021, 2, 1))
    check("compute_end_date 31.12.2020 -> 01.03.2021",
          compute_end_date("31.12.2020"), date(2021, 3, 1))
    check("compute_end_date None", compute_end_date(None), None)

    print("[5] Заголовок")
    check("заголовок",
          build_admin_title("5-1/2020", "Суркова Эдуарда Владимировича",
                            "ст. 15.6 ч. 1 КоАП РФ"),
          "Дело об административном правонарушении №5-1/2020 "
          "в отношении Суркова Эдуарда Владимировича по ст. 15.6 ч. 1 КоАП РФ")

    print("[6] Запись")
    row = FakeRow(
        case_number="5-1/2020", person="Сурков Эдуард Владимирович",
        article="ст. 15.6 ч. 1", date="10.01.2020",
        task="в работе", in_number=101, act_state="не сформирован")
    rec = build_admin_record(row, "2 года Ст. 369")
    check("title", rec["title"],
          "Дело об административном правонарушении №5-1/2020 "
          "в отношении Суркова Эдуарда Владимировича по ст. 15.6 ч. 1 КоАП РФ")
    check("dates", rec["dates"], "10.01.2020\n10.03.2020")
    check("retention", rec["retention"], "2 года Ст. 369")
    check("note (task)", rec["note"], "в работе")
    check("applicants (person)", rec["applicants"], "Суркова Эдуарда Владимировича")
    check("category (article)", rec["category"], "ст. 15.6 ч. 1 КоАП РФ")
    check("opis_number (in_number)", rec["opis_number"], "101")
    check("act_state", rec["act_state"], "не сформирован")
    check("count", rec["count"], 1)

    print("[7] process_admin_cases: сквозная нумерация с пропуском")
    rows = [
        FakeRow(case_number="5-1/2020", person="Сурков Эдуард Владимирович",
                article="ст. 15.6 ч. 1", date="10.01.2020",
                task="", in_number=1, act_state=""),
        FakeRow(case_number="5-3/2020", person="ООО Ромашка",
                article="1.1 ч.1 ЗСО №104", date="20.02.2020",
                task="", in_number=3, act_state=""),
        FakeRow(case_number="5-9/2021", person="Петров Пётр Петрович",
                article="ст. 1", date="01.01.2021",
                task="", in_number=9, act_state=""),
    ]
    records, stats = process_admin_cases(rows, 2020, "2 года Ст. 369")
    check("записей = 3 (1..3)", len(records), 3)
    check("sequential[0]", records[0]["sequential"], 1)
    check("sequential[1]", records[1]["sequential"], 2)
    check("sequential[2]", records[2]["sequential"], 3)
    check("пропуск 5-2/2020 пустой", records[1]["title"], "")
    check("5-3/2020 заполнено", records[2]["case_number"], "5-3/2020")
    check("дело 2021 отфильтровано", stats["valid_count"], 2)
    check("min_case_num", stats["min_case_num"], 1)
    check("max_case_num", stats["max_case_num"], 3)
    check("skipped_numbers", stats["skipped_numbers"], 1)
    check("case_prefix", stats["case_prefix"], "5")

    print()
    print(f"Итого: {PASSED} OK, {FAILED} FAIL")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
