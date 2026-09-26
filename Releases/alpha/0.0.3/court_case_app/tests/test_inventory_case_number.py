# -*- coding: utf-8 -*-
"""
Тесты разбора номеров дел и потока (столбцы D/E/F/G) — этап 14b.

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_inventory_case_number.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.inventory.case_number import (
    build_from_rows,
    build_stream,
    choose_number,
    detect_flow_year,
    parse_numbers,
    resolve_chosen_list,
)

FAILED = 0
PASSED = 0


def check(name, actual, expected):
    global FAILED, PASSED
    if actual == expected:
        PASSED += 1
        print(f"  OK   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось: {expected!r}\n"
              f"       получено:  {actual!r}")


def main():
    print("[1] parse_numbers")
    check("один номер", parse_numbers("Решение по делу № 2-14/2018"),
          [{"prefix": "2", "number": 14, "year": 2018, "raw": "2-14/2018"}])
    check("двойной номер",
          parse_numbers("№ 11-47/2018 (№ 2-14/2018)"),
          [{"prefix": "11", "number": 47, "year": 2018, "raw": "11-47/2018"},
           {"prefix": "2", "number": 14, "year": 2018, "raw": "2-14/2018"}])
    check("буквенный префикс",
          [{k: v for k, v in d.items() if k != "raw"}
           for d in parse_numbers("№ 2а-3/2018")],
          [{"prefix": "2а", "number": 3, "year": 2018}])
    check("нет номера", parse_numbers("Просто текст"), [])
    check("None", parse_numbers(None), [])

    print("\n[2] choose_number: двойные номера")
    prev = {"prefix": "2", "number": 13}
    nxt = {"prefix": "2", "number": 15}
    nums = parse_numbers("№ 11-47/2018 (№ 2-14/2018)")
    r = choose_number(nums, prev, nxt)
    check("первый выпал (префикс) -> второй",
          (r["chosen"]["prefix"], r["chosen"]["number"], r["fell_out"]),
          ("2", 14, True))
    check("причина", r["reason"],
          "первый номер выпал из потока — взят второй")

    nums2 = parse_numbers("№ 2-14/2018 (№ 2-40/2018)")
    r2 = choose_number(nums2, prev, nxt)
    check("первый в потоке",
          (r2["chosen"]["number"], r2["fell_out"]), (14, False))

    nums3 = parse_numbers("№ 5-100/2018 (№ 5-200/2018)")
    r3 = choose_number(nums3, prev, nxt)
    check("оба выпали -> первый",
          (r3["chosen"]["number"], r3["reason"]),
          (100, "оба номера выпали из потока — взят первый"))

    check("один номер",
          choose_number(nums[:1], prev, nxt)["chosen"]["number"], 47)
    check("пусто", choose_number([], prev, nxt)["chosen"], None)
    check("первая строка (prev=None)",
          choose_number(nums, None, nxt)["chosen"]["number"], 14)

    print("\n[3] detect_flow_year")
    y1 = detect_flow_year([2018, 2018, 2018])
    check("все одинаковы", (y1["year"], y1["needs_choice"]), (2018, False))
    y2 = detect_flow_year([2018] * 19 + [2015])
    check("доминирующий (>=90%)",
          (y2["year"], y2["dominant"], y2["attention"]),
          (2018, True, [2015]))
    y3 = detect_flow_year([2018] * 8 + [2017] * 2)
    check("второй значимый (>=10%)",
          (y3["year"], y3["needs_choice"], y3["attention"]),
          (2018, True, [2017]))
    check("пусто", detect_flow_year([])["year"], None)
    check("без годов", detect_flow_year([None, None])["year"], None)

    print("\n[4] build_stream: D/E/F/G")
    chosen = [
        {"prefix": "2", "number": 14, "year": 2018},
        {"prefix": "2", "number": 15, "year": 2018},
        {"prefix": "2", "number": 15, "year": 2018},
        {"prefix": "3", "number": 20, "year": 2018},
    ]
    st = build_stream(chosen)
    check("f4", st["f4"], 14)
    check("год потока", st["year"], 2018)
    check("E4 не заполнен", st["rows"][0]["E"], None)
    check("E приращение +1", st["rows"][1]["E"], 1)
    check("продолжение дела E=0", st["rows"][2]["E"], 0)
    check("префиксы D как есть", [r["D"] for r in st["rows"]],
          ["2", "2", "2", "3"])
    check("F абсолютные", [r["F"] for r in st["rows"]], [14, 15, 15, 20])

    print("\n[5] build_stream: исправление года")
    chosen_y = [{"prefix": "2", "number": 1, "year": 2015},
                {"prefix": "2", "number": 2, "year": 2018}]
    sty = build_stream(chosen_y, flow_year=2018)
    check("год заменён на поток", sty["rows"][0]["G"], 2018)
    check("пометка года", bool(sty["rows"][0]["attention"]), True)
    check("второй год не тронут", sty["rows"][1]["attention"], "")

    print("\n[6] build_from_rows: двойной номер в потоке")
    rows = [{"name": "Решение № 2-14/2018"},
            {"name": "№ 11-47/2018 (№ 2-15/2018)"},
            {"name": "Решение № 2-16/2018"}]
    res = build_from_rows(rows)
    check("f4", res["f4"], 14)
    check("номера потока", [r["F"] for r in res["rows"]], [14, 15, 16])
    check("выбран второй номер (в потоке)",
          res["rows"][1]["D"], "2")
    check("E приращение", [r["E"] for r in res["rows"][1:]], [1, 1])

    print("\n" + "=" * 60)
    print(f"ИТОГО: PASSED = {PASSED}, FAILED = {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
