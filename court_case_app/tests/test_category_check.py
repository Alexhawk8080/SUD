# -*- coding: utf-8 -*-
"""
Тесты проверки и исправления категорий дел (Доработка 6).

Запуск: .venv\\Scripts\\python.exe court_case_app\\tests\\test_category_check.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.category_check import (
    normalize_text,
    has_category_phrase,
    is_problematic,
    extract_phrase,
    build_organization_lookup,
    get_plaintiff_key,
    most_frequent,
    unique_preserve_order,
    analyze,
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


def main():
    print("[1] normalize_text")
    check("Регистр и пробелы", normalize_text("  ООО \"СБЕРБАНК\" "), "ооо сбербанк")
    check("Пунктуация удаляется", normalize_text("Иванов Иван; Петров, Пётр!"),
          "иванов иван петров петр")
    check("ё -> е", normalize_text("Пётр"), "петр")
    check("None -> пусто", normalize_text(None), "")
    check("Дефис убирается", normalize_text("о взыскании сумм по договору займа"),
          "о взыскании сумм по договору займа")

    print("\n[2] has_category_phrase")
    check("«о взыскании...»", has_category_phrase("о взыскании сумм по договору займа"), True)
    check("«О» в начале строки", has_category_phrase("О защите прав потребителей"), True)
    check("«об»", has_category_phrase("об оплате коммунальных услуг"), True)
    check("В середине фразы", has_category_phrase("Гражданское дело о расторжении брака"), True)
    check("Пусто", has_category_phrase(""), False)
    check("None", has_category_phrase(None), False)
    check("Без «о/об»", has_category_phrase("Взыскание задолженности"), False)
    check("Аббревиатура ООО не матчится", has_category_phrase("ООО Ромашка"), False)
    check("Слово «оборот» не матчится", has_category_phrase("оборот средств"), False)

    print("\n[3] is_problematic")
    check("None -> проблемное", is_problematic(None), True)
    check("Пустая строка -> проблемное", is_problematic("  "), True)
    check("Текст без «о/об» -> проблемное", is_problematic("Взыскание задолженности"), True)
    check("«о ...» -> не проблемное", is_problematic("о взыскании задолженности"), False)
    check("«О ...» в начале -> не проблемное",
          is_problematic("О защите прав потребителей"), False)

    print("\n[4] extract_phrase")
    check("Из середины", extract_phrase("Исковое заявление о расторжении брака супругов"),
          "о расторжении брака супругов")
    check("Из начала", extract_phrase("О защите прав потребителей"),
          "О защите прав потребителей")
    check("«об»", extract_phrase("дело об оплате услуг"), "об оплате услуг")
    check("Без «о/об» -> пусто", extract_phrase("Взыскание задолженности"), "")
    check("Пусто -> пусто", extract_phrase(None), "")

    print("\n[5] get_plaintiff_key")
    org_lookup = build_organization_lookup(["СБЕРБАНК", "ВТБ", "ООО", "АО"])
    check("Организация по справочнику", get_plaintiff_key("СБЕРБАНК", org_lookup),
          ("сбербанк", "СБЕРБАНК", True))
    check("Организация по аббревиатуре ООО",
          get_plaintiff_key('ООО "Ромашка"', org_lookup),
          ("ооо", 'ООО "Ромашка"', True))
    check("Организация по аббревиатуре ПАО (вне справочника)",
          get_plaintiff_key("ПАО Сбербанк", org_lookup), ("пао", "ПАО Сбербанк", True))
    check("МУП (вне справочника)", get_plaintiff_key("МУП ЖКХ", org_lookup),
          ("муп", "МУП ЖКХ", True))
    check("Физическое лицо", get_plaintiff_key("Иванов Иван Иванович", org_lookup),
          ("иванов иван иванович", "Иванов Иван Иванович", False))
    check("Несколько физлиц",
          get_plaintiff_key("Иванов Иван; Петров Пётр", org_lookup),
          ("иванов иван петров петр", "Иванов Иван; Петров Пётр", False))
    check("Пусто", get_plaintiff_key_empty(org_lookup), ("", "", False))
    check("Регистр аббревиатуры", get_plaintiff_key("ооо ромашка", org_lookup),
          ("ооо", "ооо ромашка", True))

    print("\n[6] most_frequent / unique_preserve_order")
    check("Мода", most_frequent([
        "о взыскании задолженности по кредитному договору",
        "о взыскании процентов",
        "о взыскании задолженности по кредитному договору",
    ]), "о взыскании задолженности по кредитному договору")
    check("Мода по нормализации (регистр)",
          most_frequent(["О взыскании", "о взыскании"]), "О взыскании")
    check("Мода пустого списка", most_frequent([]), "")
    check("Уникальные с сохранением порядка", unique_preserve_order([
        "о взыскании", "О ВЗЫСКАНИИ", "об оплате"]),
        ["о взыскании", "об оплате"])

    print("\n[7] analyze: аналоги, мода, группы, словарь")
    rows = [
        # (номер, заявители, категория)
        {"case_number": "2-1/2023", "applicants": "ООО Сбербанк",
         "category": "Исковое заявление о взыскании задолженности по кредитному договору"},
        {"case_number": "2-2/2023", "applicants": "СБЕРБАНК",
         "category": "о взыскании задолженности по кредитному договору"},
        {"case_number": "2-3/2023", "applicants": "ООО Сбербанк",
         "category": "о взыскании процентов по кредитному договору"},
        {"case_number": "2-4/2023", "applicants": "ООО Сбербанк",
         "category": ""},
        {"case_number": "2-5/2023", "applicants": "Иванов Иван Иванович",
         "category": None},
        {"case_number": "2-6/2023", "applicants": "Иванов Иван Иванович",
         "category": "Взыскание сумм по договору займа"},
        {"case_number": "2-7/2023", "applicants": "ООО Сбербанк",
         "category": "о взыскании задолженности по кредитному договору"},
    ]
    org_names = ["ООО", "СБЕРБАНК"]

    res = analyze(rows, org_names, categories_map={})
    st = res["stats"]
    check("Проблемных дел: 3 (2-4, 2-5, 2-6)", st["total"], 3)
    check("С аналогами: 1 (2-4)", st["with_analogs"], 1)
    check("Из словаря: 0", st["from_dictionary"], 0)
    check("Без аналогов: 2 (2-5, 2-6)", st["no_analog"], 2)
    check("Групп «Без аналогов»: 1 (Иванов)", st["groups"], 1)

    p24 = next(p for p in res["problematic"] if p["case_number"] == "2-4/2023")
    check("2-4: ключ истца", p24["plaintiff_key"], "ооо")
    check("2-4: предложена мода", p24["suggested"],
          "о взыскании задолженности по кредитному договору")
    check("2-4: источник — аналог", p24["source"], "analog")
    check("2-4: вариантов 2", len(p24["options"]), 2)
    # «СБЕРБАНК» (2-2) имеет ключ «сбербанк» по первому слову —
    # он не аналог для ключа «ооо» (комбинированный критерий)
    check("2-4: аналогов 3", len(p24["analogs"]), 3)
    check("2-4: номера аналогов",
          sorted(a["case_number"] for a in p24["analogs"]),
          ["2-1/2023", "2-3/2023", "2-7/2023"])

    p25 = next(p for p in res["problematic"] if p["case_number"] == "2-5/2023")
    check("2-5: источник отсутствует", p25["source"], None)
    check("2-5: предложения нет", p25["suggested"], "")
    p26 = next(p for p in res["problematic"] if p["case_number"] == "2-6/2023")
    check("2-6: текст без «о/об» проблемный", p26["current_category"],
          "Взыскание сумм по договору займа")

    grp = res["groups"][0]
    check("Группа: ключ", grp["key"], "иванов иван иванович")
    check("Группа: 2 дела", len(grp["cases"]), 2)
    check("Группа: физлицо", grp["is_organization"], False)

    print("\n[8] analyze: словарь БД как источник")
    res2 = analyze(rows, org_names, categories_map={
        "иванов иван иванович": ["о взыскании сумм по договору займа"],
    })
    p25b = next(p for p in res2["problematic"] if p["case_number"] == "2-5/2023")
    check("2-5: предложение из словаря", p25b["suggested"],
          "о взыскании сумм по договору займа")
    check("2-5: источник — словарь", p25b["source"], "dictionary")
    grp2 = res2["groups"][0]
    check("Группа хранит варианты из словаря",
          grp2["dictionary_options"], ["о взыскании сумм по договору займа"])

    print("\n[9] analyze: разные ключи организаций по первому слову")
    res_x = analyze([
        {"case_number": "2-2/2023", "applicants": "СБЕРБАНК",
         "category": "о взыскании задолженности по кредитному договору"},
        {"case_number": "2-9/2023", "applicants": "СБЕРБАНК",
         "category": ""},
    ], org_names, categories_map={})
    p29 = res_x["problematic"][0]
    check("2-9: ключ «сбербанк»", p29["plaintiff_key"], "сбербанк")
    check("2-9: найден аналог 2-2",
          [a["case_number"] for a in p29["analogs"]], ["2-2/2023"])

    print("\n[10] analyze: приоритет аналогов над словарём")
    res3 = analyze(rows, org_names, categories_map={
        "ооо": ["о взыскании процентов"],
    })
    p24c = next(p for p in res3["problematic"] if p["case_number"] == "2-4/2023")
    check("2-4: мода аналогов важнее словаря", p24c["suggested"],
          "о взыскании задолженности по кредитному договору")
    check("2-4: источник — аналог", p24c["source"], "analog")

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


def get_plaintiff_key_empty(org_lookup):
    return get_plaintiff_key(None, org_lookup)


if __name__ == "__main__":
    main()