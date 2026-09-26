# -*- coding: utf-8 -*-
"""
Тесты ядра обработки дел (Этап 5). Сверка с VBA-логикой на данных из акта.

Примечания:
- ExtractCaseType (как и VBA) ищет « О » / « Об » С ПРОБЕЛОМ ПЕРЕД «О».
  Поэтому категории в тесте заданы как «Исковое заявление о ...».
- Алиментное дело, исключённое фильтром, остаётся в диапазоне номеров как
  пустая строка (поведение VBA: цикл по всем номерам min..max).

Запуск: .venv\\Scripts\\python.exe court_case_app\\tests\\test_cases.py
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.excel_reader import SourceRow
from core.case_processor import (
    contains_alimony,
    extract_case_type,
    get_case_prefix,
    get_case_type_prefix,
    is_organization,
    is_valid_case_number,
    parse_case_number,
    process_cases,
    process_names_list,
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


# Справочники (имитация базы данных)
ORGANIZATIONS = {
    "ООО": "по иску",
    "АО": "по иску",
    "ПАО": "по иску",
    "ИП": "по иску",
    "ЗАО": "по иску",
}
EXCLUSIONS = ["ООО", "АО", "ПАО", "ИП", "ЗАО", "ГК", "ГСК", "ТСЖ", "УО", "УПФ",
              "ИФНС", "Администрация", "Управление"]

DIVORCE_KIDS = "Исковое заявление о расторжении брака супругов - имеющих детей"
DIVORCE_NO_KIDS = "Исковое заявление о расторжении брака супругов - бездетных или имеющих взрослых детей"


def d(row):
    """Дата из строки dd.mm.yyyy."""
    return datetime.strptime(row, "%d.%m.%Y")


def make_rows():
    """Строки исходной таблицы: дела из акта за 2019 год + алиментное."""
    rows = [
        SourceRow({"date": d("26.11.2018"), "case_number": "2-3/2019",
                   "applicants": "Саркисян Юлия Геннадьевна",
                   "respondents": "Саркисян Давид Сергеевич",
                   "category": DIVORCE_KIDS,
                   "opis_number": 1, "unit_number": 1, "note": "",
                   "end_date": d("26.12.2018")}),
        SourceRow({"date": d("11.12.2018"), "case_number": "2-5/2019",
                   "applicants": "Орехова Людмила Николаевна",
                   "respondents": "Орехов Игорь Анатольевич",
                   "category": DIVORCE_NO_KIDS,
                   "opis_number": 1, "unit_number": 2, "note": "",
                   "end_date": d("11.01.2019")}),
        SourceRow({"date": d("09.01.2019"), "case_number": "2-6/2019",
                   "applicants": "Сурков Эдуард Владимирович",
                   "respondents": "Суркова Ирина Дмитриевна",
                   "category": DIVORCE_NO_KIDS,
                   "opis_number": 1, "unit_number": 3, "note": "",
                   "end_date": d("09.02.2019")}),
        SourceRow({"date": d("18.12.2018"), "case_number": "2-7/2019",
                   "applicants": "Чернова Наталья Олеговна",
                   "respondents": "Чернов Александр Сергеевич",
                   "category": DIVORCE_KIDS,
                   "opis_number": 1, "unit_number": 4, "note": "",
                   "end_date": d("18.01.2019")}),
        SourceRow({"date": d("09.01.2019"), "case_number": "2-8/2019",
                   "applicants": "Китаева Наталья Александровна",
                   "respondents": "Китаев Сергей Валерьевич",
                   "category": DIVORCE_KIDS,
                   "opis_number": 1, "unit_number": 5, "note": "",
                   "end_date": d("09.02.2019")}),
        SourceRow({"date": d("18.12.2018"), "case_number": "2-9/2019",
                   "applicants": "Суздальцева Юлия Михайловна",
                   "respondents": "Терентьев Юрий Юрьевич",
                   "category": DIVORCE_KIDS,
                   "opis_number": 1, "unit_number": 6, "note": "",
                   "end_date": d("18.01.2019")}),
        SourceRow({"date": d("09.01.2019"), "case_number": "2-10/2019",
                   "applicants": "Зверева Галина Евгеньевна",
                   "respondents": "Зверев Алексей Владимирович",
                   "category": DIVORCE_NO_KIDS,
                   "opis_number": 1, "unit_number": 7, "note": "",
                   "end_date": d("09.02.2019")}),
        SourceRow({"date": d("14.12.2018"), "case_number": "2-11/2019",
                   "applicants": "Голованова Владимир Валерьевич",
                   "respondents": 'ООО "Сеть Связной"',
                   "category": "Исковое заявление о защите прав потребителей - из договоров в сфере услуги торговли",
                   "opis_number": 1, "unit_number": 8, "note": "",
                   "end_date": d("14.01.2019")}),
        SourceRow({"date": d("21.12.2018"), "case_number": "2-12/2019",
                   "applicants": 'АО "МАКС"',
                   "respondents": "Гринчева Оксана Геннадьевна",
                   "category": "Исковое заявление о возмещении имущественного вреда",
                   "opis_number": 1, "unit_number": 9, "note": "",
                   "end_date": d("21.01.2019")}),
        # Алиментное дело (для проверки фильтра)
        SourceRow({"date": d("05.01.2019"), "case_number": "2-13/2019",
                   "applicants": "Петрова Анна Сергеевна",
                   "respondents": "Петров Игорь Николаевич",
                   "category": "Исковое заявление о взыскании алиментов на содержание несовершеннолетнего ребенка",
                   "opis_number": 1, "unit_number": 10, "note": "",
                   "end_date": d("05.02.2019")}),
    ]
    return rows


def test_validators():
    print("\n[1] Валидация и парсинг")
    check("Валидный номер", is_valid_case_number("2-3/2019", "2019"), True)
    check("Не тот год", is_valid_case_number("2-3/2018", "2019"), False)
    check("Без '-'", is_valid_case_number("2/2019", "2019"), False)
    check("Без '/'", is_valid_case_number("2-3", "2019"), False)
    check("None", is_valid_case_number(None, "2019"), False)
    # fix_04: строгая валидация
    check("fix_04: буквенный префикс", is_valid_case_number("abc-def/2023", "2023"), False)
    check("fix_04: лишний дефис", is_valid_case_number("2-3-4/2023", "2023"), False)
    check("fix_04: нечисловой номер", is_valid_case_number("2-хх/2023", "2023"), False)
    check("fix_04: пробел по краям — валидно",
          is_valid_case_number("  2-3/2023  ", "2023"), True)
    check("fix_04: parse мусора -> 0", parse_case_number("abc-def/2023"), 0)
    check("fix_04: prefix мусора -> ''", get_case_prefix("abc-def/2023"), "")
    check("parse 2-3/2019 -> 3", parse_case_number("2-3/2019"), 3)
    check("parse 2-123/2023 -> 123", parse_case_number("2-123/2023"), 123)
    check("Алименты в категории", contains_alimony("О взыскании алиментов"), True)
    check("Без алиментов", contains_alimony("О расторжении брака"), False)
    check("ExtractCaseType ('... о ...')",
          extract_case_type("Исковое заявление о расторжении брака супругов"),
          "о расторжении брака супругов")
    check("ExtractCaseType начинается с 'О ' -> '' (как VBA)",
          extract_case_type("О расторжении брака супругов"), "")
    check("ExtractCaseType без 'О'", extract_case_type("Расторжение брака"), "")
    check("IsOrganization ООО", is_organization('ООО "Ромашка"', EXCLUSIONS), True)
    check("IsOrganization физлицо",
          is_organization("Саркисян Юлия Геннадьевна", EXCLUSIONS), False)


def test_names_and_prefix():
    print("\n[2] Склонение списков и префикс")
    gen = process_names_list("Саркисян Юлия Геннадьевна; Иванов Иван", "Genitive", EXCLUSIONS)
    check("Заявители род. падеж", gen,
          "Саркисян Юлии Геннадьевны; Иванова Ивана")
    dat = process_names_list('ООО "Сеть Связной"; Петров Пётр', "Dative", EXCLUSIONS)
    check("Ответчики дат. падеж (аббревиатура-организация не меняется)", dat,
          'ООО "Сеть Связной"; Петрову Петру')
    dat_org = process_names_list("Администрация города; Петров Пётр", "Dative", EXCLUSIONS)
    check("Ответчики дат. падеж (организация: родовое слово склоняется)", dat_org,
          "Администрации города; Петрову Петру")
    gen_org = process_names_list("Администрация города", "Genitive", EXCLUSIONS)
    check("Заявители род. падеж (организация: родовое слово склоняется)", gen_org,
          "Администрации города")
    gen_org2 = process_names_list('Муниципальное унитарное предприятие "Водоканал"',
                                  "Genitive", EXCLUSIONS + ["Муниципальное"])
    check("Заявители род. (прилагательное+сущ. перед кавычками)", gen_org2,
          'Муниципального унитарного предприятия "Водоканал"')
    check("Префикс: физлицо -> по заявлению",
          get_case_type_prefix("Саркисян Юлия Геннадьевна", ORGANIZATIONS, EXCLUSIONS),
          "по заявлению")
    check("Префикс: АО -> по иску",
          get_case_type_prefix('АО "МАКС"', ORGANIZATIONS, EXCLUSIONS),
          "по иску")
    check("Префикс: пусто -> по заявлению",
          get_case_type_prefix(None, ORGANIZATIONS, EXCLUSIONS),
          "по заявлению")


def test_process_cases_without_alimony():
    print("\n[3] Обработка без алиментных дел (год 2019)")
    rows = make_rows()
    records, stats = process_cases(rows, 2019, False, ORGANIZATIONS, EXCLUSIONS)
    # Диапазон 3..13 = 11 номеров; пропущен 2-4; 2-13 (алименты) исключён -> пустая строка
    check("Всего записей (11 номеров)", len(records), 11)
    check("valid_count = 9", stats["valid_count"], 9)
    check("Пропущенных номеров = 1 (2-4)", stats["skipped_numbers"], 1)
    check("Исключено алиментных = 1", stats["alimony_excluded"], 1)
    check("Префикс '2'", stats["case_prefix"], "2")

    r0 = records[0]
    check("№2-3 заголовок",
          r0["title"],
          "Гражданское дело №2-3/2019 по заявлению Саркисян Юлии Геннадьевны "
          "к Саркисяну Давиду Сергеевичу о расторжении брака супругов - имеющих детей")
    check("№2-3 даты", r0["dates"], "26.11.2018\n26.12.2018")
    check("№2-3 срок хранения", r0["retention"], "3 года ЭК Ст. 137")
    check("№2-3 порядковый", r0["sequential"], 1)
    check("№2-3 кол-во ед.хр.", r0["count"], 1)

    # Пустая строка для пропущенного 2-4
    r1 = records[1]
    check("№2-4 пустая строка (только номер)", r1["sequential"], 2)
    check("№2-4 заголовок пуст", r1["title"], "")
    check("№2-4 срок пуст", r1["retention"], "")

    # №2-11 — потребители
    r8 = records[8]
    check("№2-11 заголовок (потребители, организация-ответчик)",
          r8["title"],
          'Гражданское дело №2-11/2019 по заявлению Голованова Владимира Валерьевича '
          'к ООО "Сеть Связной" о защите прав потребителей - из договоров '
          "в сфере услуги торговли")
    check("№2-11 срок хранения", r8["retention"], "3 года ЭПК Ст. 208")

    # №2-12 — АО "МАКС" (по иску)
    r9 = records[9]
    check("№2-12 заголовок (АО -> по иску)",
          r9["title"],
          'Гражданское дело №2-12/2019 по иску АО "МАКС" к Гринчевой Оксане '
          "Геннадьевне о возмещении имущественного вреда")
    check("№2-12 срок (нет ключа -> 227)", r9["retention"], "3 года Ст. 227")

    # №2-13 исключён: последняя запись пустая
    r10 = records[10]
    check("№2-13 пустая строка (алиментное исключено)", r10["title"], "")
    check("№2-13 порядковый 11", r10["sequential"], 11)


def test_process_cases_with_alimony():
    print("\n[4] Обработка с алиментными делами")
    rows = make_rows()
    records, stats = process_cases(rows, 2019, True, ORGANIZATIONS, EXCLUSIONS)
    check("valid_count = 10 (алиментные включены)", stats["valid_count"], 10)
    check("Пропущенных = 1 (2-4)", stats["skipped_numbers"], 1)
    check("Алиментных исключено = 0", stats["alimony_excluded"], 0)
    r_last = records[-1]
    check("Последняя запись — №2-13 (алиментное)",
          r_last["title"].startswith("Гражданское дело №2-13/2019"), True)
    check("№2-13 срок (collection -> 227)", r_last["retention"], "3 года Ст. 227")


def test_year_filter_and_invalid():
    print("\n[5] Год и невалидные номера")
    rows = make_rows()
    # Дело 2020 года — пропущено
    rows.append(SourceRow({"date": d("01.01.2020"), "case_number": "2-50/2020",
                           "applicants": "X", "respondents": "Y",
                           "category": "О расторжении брака",
                           "opis_number": None, "unit_number": None, "note": "",
                           "end_date": None}))
    # Невалидный номер — пропущен
    rows.append(SourceRow({"date": d("01.01.2019"), "case_number": "ОШИБКА",
                           "applicants": "X", "respondents": "Y",
                           "category": "Что-то", "opis_number": None,
                           "unit_number": None, "note": "", "end_date": None}))
    records, stats = process_cases(rows, 2019, False, ORGANIZATIONS, EXCLUSIONS)
    titles = [r["title"] for r in records]
    check("Дело 2020 не попало", "Гражданское дело №2-50/2020" not in titles, True)
    check("Невалидный номер не попал", "ОШИБКА" not in titles, True)
    check("Диапазон прежний (3..13)", stats["total_in_range"], 11)


def test_no_valid_cases():
    print("\n[6] Нет дел за указанный год")
    rows = make_rows()
    records, stats = process_cases(rows, 2025, False, ORGANIZATIONS, EXCLUSIONS)
    check("Записей нет", len(records), 0)
    check("valid_count = 0", stats["valid_count"], 0)


def make_bad_category_rows():
    """Дела с отсутствующей категорией (Доработка 6)."""
    return [
        SourceRow({"date": d("01.01.2019"), "case_number": "2-1/2019",
                   "applicants": "ООО Сбербанк",
                   "respondents": "Иванов Иван Иванович",
                   "category": "", "opis_number": 1, "unit_number": 1,
                   "note": "", "end_date": d("05.01.2019")}),
        SourceRow({"date": d("02.01.2019"), "case_number": "2-2/2019",
                   "applicants": "ООО Сбербанк",
                   "respondents": "Петров Пётр Петрович",
                   "category": None, "opis_number": 1, "unit_number": 2,
                   "note": "", "end_date": d("06.01.2019")}),
    ]


def test_category_fixes():
    print("\n[7] Исправление отсутствующих категорий (Доработка 6)")
    rows = make_bad_category_rows()

    # Без исправлений — заголовок обрублен, срок 227
    rec0, st0 = process_cases(rows, 2019, False, ORGANIZATIONS, EXCLUSIONS)
    check("Без исправлений: в заголовке нет типа",
          "о взыскании" not in rec0[0]["title"], True)
    check("Без исправлений: срок 227", rec0[0]["retention"], "3 года Ст. 227")
    check("Автоподстановок нет", st0["auto_fixed"], 0)

    # Явное исправление (номер -> категория) + автословарь.
    # ВНИМАНИЕ: категории, начинающиеся со слова «взыскании», дают 227
    # (особенность VBA «взыскани» -> collection, сохранена 1:1),
    # поэтому для проверки срока берём категорию «о защите прав потребителей».
    fixes = {"2-1/2019": "о защите прав потребителей"}
    auto_map = {"ооо": ["о взыскании процентов"]}
    records, stats = process_cases(
        rows, 2019, False, ORGANIZATIONS, EXCLUSIONS,
        category_fixes=fixes, auto_fix_map=auto_map)

    check("№2-1: исправленный заголовок",
          records[0]["title"],
          "Гражданское дело №2-1/2019 по иску ООО Сбербанк к Иванову Ивану "
          "Ивановичу о защите прав потребителей")
    check("№2-1: срок по исправленной категории (потребители -> 208)",
          records[0]["retention"], "3 года ЭПК Ст. 208")
    check("№2-2: автоподстановка из словаря (мода)",
          records[1]["title"].endswith("о взыскании процентов"), True)
    check("№2-2: срок по автоподставленной (прочее -> 227)",
          records[1]["retention"], "3 года Ст. 227")
    check("Статистика: автоподставлено 1", stats["auto_fixed"], 1)

    # fix_02: ключ с хвостовым пробелом в исходных данных
    rows_sp = [
        SourceRow({"date": d("01.01.2019"), "case_number": "2-1/2019 ",
                   "applicants": "ООО Сбербанк",
                   "respondents": "Иванов Иван Иванович",
                   "category": "", "opis_number": 1, "unit_number": 1,
                   "note": "", "end_date": d("05.01.2019")}),
    ]
    rec_sp, _ = process_cases(
        rows_sp, 2019, False, ORGANIZATIONS, EXCLUSIONS,
        category_fixes={"2-1/2019": "о защите прав потребителей"})
    check("fix_02: исправление применяется при пробеле в номере Excel",
          rec_sp[0]["title"].endswith("о защите прав потребителей"), True)

    # fix_02: ключ в category_fixes с хвостовым пробелом
    rec_sp2, _ = process_cases(
        rows_sp, 2019, False, ORGANIZATIONS, EXCLUSIONS,
        category_fixes={"  2-1/2019  ": "о расторжении брака"})
    check("fix_02: ключ в fixes нормализуется (.strip)",
          rec_sp2[0]["title"].endswith("о расторжении брака"), True)

    # Приоритет: явное исправление важнее словаря
    records2, stats2 = process_cases(
        rows, 2019, False, ORGANIZATIONS, EXCLUSIONS,
        category_fixes={"2-1/2019": "о расторжении брака"},
        auto_fix_map={"ооо": ["о взыскании процентов"]})
    check("Приоритет явного исправления над словарём",
          records2[0]["title"].endswith("о расторжении брака"), True)
    check("Срок по явному исправлению (развод -> 137)",
          records2[0]["retention"], "3 года ЭК Ст. 137")


if __name__ == "__main__":
    test_validators()
    test_names_and_prefix()
    test_process_cases_without_alimony()
    test_process_cases_with_alimony()
    test_year_filter_and_invalid()
    test_no_valid_cases()
    test_category_fixes()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)