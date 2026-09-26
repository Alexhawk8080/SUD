# -*- coding: utf-8 -*-
"""
Тесты core.converter.year_detect (stage12a, под-этап B1).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_converter_year.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.converter.year_detect import (
    detect_year_from_numbers,
    detect_year_from_rows,
    extract_year,
    make_warning_message,
)
from core.converter.exceptions import NoValidCaseNumbers

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


def expect_error(name, fn, exc_type):
    global FAILED, PASSED
    try:
        fn()
    except exc_type:
        PASSED += 1
        print(f"  OK   {name}")
        return
    except Exception as exc:  # noqa: BLE001
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось {exc_type.__name__}, "
              f"получено {type(exc).__name__}: {exc}")
        return
    FAILED += 1
    print(f"  FAIL {name}\n       исключение не поднято")


def main():
    print("[1] extract_year")
    check("2-5/2019 -> 2019", extract_year("2-5/2019"), "2019")
    check("2-123/2020 -> 2020", extract_year("2-123/2020"), "2020")
    check("пробелы терпятся", extract_year("  2-5/2019 "), "2019")
    check("Без дефиса -> ''", extract_year("2/2019"), "")
    check("Буквы -> ''", extract_year("abc-def/2020"), "")
    check("None -> ''", extract_year(None), "")
    check("Пустая строка -> ''", extract_year(""), "")

    print("\n[2] detect_year_from_numbers: один год")
    r = detect_year_from_numbers(["2-1/2020", "2-2/2020", "2-3/2020"])
    check("year", r["year"], "2020")
    check("years", r["years"], {"2020": 3})
    check("others пусто", r["others"], [])
    check("total", r["total"], 3)

    print("\n[3] Самый частый год побеждает")
    r = detect_year_from_numbers(["2-1/2019", "2-2/2020", "2-3/2020"])
    check("year = 2020 (2 против 1)", r["year"], "2020")
    check("years", r["years"], {"2019": 1, "2020": 2})
    check("others содержит 2019", r["others"], [["2019", 1]])
    check("total = 3", r["total"], 3)

    print("\n[4] Равенство частот -> наибольший год")
    r = detect_year_from_numbers(["2-1/2019", "2-2/2021"])
    check("year = 2021", r["year"], "2021")
    r = detect_year_from_numbers(["2-1/2020", "2-2/2018", "2-3/2022", "2-4/2019"])
    check("year = 2022 (макс из равных)", r["year"], "2022")

    print("\n[5] Мусорные номера игнорируются")
    r = detect_year_from_numbers(["2-1/2020", "abc", "", None, "2-2"])
    check("year = 2020", r["year"], "2020")
    check("total = 1 (только валидные)", r["total"], 1)

    print("\n[6] Нет валидных номеров -> NoValidCaseNumbers")
    expect_error("Пустой список", lambda: detect_year_from_numbers([]),
                 NoValidCaseNumbers)
    expect_error("Только мусор",
                 lambda: detect_year_from_numbers(["abc", "2-3"]),
                 NoValidCaseNumbers)
    expect_error("None-совместимо",
                 lambda: detect_year_from_numbers([None, None]),
                 NoValidCaseNumbers)

    print("\n[7] detect_year_from_rows (dict)")
    rows = [
        {"case_number": "2-1/2020"},
        {"case_number": "2-2/2020"},
        {"case_number": "2-3/2019"},
    ]
    r = detect_year_from_rows(rows)
    check("year = 2020", r["year"], "2020")
    check("total = 3", r["total"], 3)

    print("\n[8] make_warning_message")
    r = detect_year_from_numbers(["2-1/2019", "2-2/2020", "2-3/2020"])
    msg = make_warning_message(r)
    check("Содержит победивший год", "2020" in msg, True)
    check("Содержит 'чужой' год 2019", "2019" in msg, True)
    check("Содержит '1 шт.'", "1 шт." in msg, True)

    r2 = detect_year_from_numbers(["2-1/2020"])
    check("Нет чужих -> пустое сообщение", make_warning_message(r2), "")

    print("\n[9] Несколько чужих годов")
    r3 = detect_year_from_numbers(
        ["2-1/2018", "2-2/2019", "2-3/2020", "2-4/2020", "2-5/2020"])
    check("year = 2020 (3 vs 1 vs 1)", r3["year"], "2020")
    check("others = 2 года", len(r3["others"]), 2)
    # Порядок others: сначала по частоте, при равенстве — по убыванию года
    check("Первый чужой — 2019", r3["others"][0][0], "2019")
    check("Второй чужой — 2018", r3["others"][1][0], "2018")

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
