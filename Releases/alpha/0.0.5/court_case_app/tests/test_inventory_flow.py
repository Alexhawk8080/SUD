# -*- coding: utf-8 -*-
"""
Тесты сборки потока из нескольких docx (этап 14c).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_inventory_flow.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.inventory.flow import (
    build_flow,
    combine_type,
    doc_case_type,
    doc_numbers,
    doc_range,
    stitch_docs,
)
from core.inventory.normalizer import CASE_ADMIN, CASE_CIVIL
from core.inventory.exceptions import FlowBreakError, MixedTypesError

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


def make_doc(file_name, numbers, kind="civil"):
    """Фейковый doc: номера -> строки с «Наименование»."""
    word = "гражданскому" if kind == "civil" else "об административном правонарушении"
    rows = []
    for i, n in enumerate(numbers):
        rows.append({
            "file": file_name,
            "word_row": i + 1,
            "name": f"Решение по {word} делу № 2-{n}/2018",
        })
    return {"file": file_name, "rows": rows, "attention": []}


def main():
    print("[1] doc_numbers / doc_range")
    d1 = make_doc("a.docx", [14, 15, 16])
    check("номера", [n["number"] for n in doc_numbers(d1)], [14, 15, 16])
    check("диапазон", doc_range(d1), (14, 16))
    check("пустой документ", doc_range({"file": "x", "rows": []}),
          (None, None))

    print("\n[2] doc_case_type")
    check("гражданские", doc_case_type(make_doc("c.docx", [1], "civil")),
          CASE_CIVIL)
    check("административные", doc_case_type(make_doc("a.docx", [1], "admin")),
          CASE_ADMIN)
    check("нет данных", doc_case_type({"file": "e", "rows": []}), "")
    mixed = {"file": "m.docx", "rows": [
        {"name": "Решение по гражданскому делу"},
        {"name": "Постановление по делу об АП"},
        {"name": "Решение по гражданскому делу"},
    ]}
    expect_error("смешение в файле", lambda: doc_case_type(mixed),
                 MixedTypesError)

    print("\n[3] stitch_docs")
    check("один файл", [d["file"] for d in stitch_docs([d1])], ["a.docx"])
    check("пусто", stitch_docs([]), [])

    f2 = make_doc("vol2.docx", [17, 18, 19])
    check("стыковка не по алфавиту",
          [d["file"] for d in stitch_docs([f2, d1])],
          ["a.docx", "vol2.docx"])
    check("продолжение (равные границы)",
          [d["file"] for d in stitch_docs([make_doc("v2.docx", [16, 17]),
                                           d1])],
          ["a.docx", "v2.docx"])

    print("\n[4] stitch_docs: ошибки")
    expect_error("разрыв потока",
                 lambda: stitch_docs([d1, make_doc("g.docx", [30, 31])]),
                 FlowBreakError)
    expect_error("пересечение",
                 lambda: stitch_docs([d1, make_doc("o.docx", [10, 11])]),
                 FlowBreakError)

    print("\n[5] combine_type: смешение файлов")
    check("гражданские", combine_type([d1, f2]), CASE_CIVIL)
    adm = make_doc("adm.docx", [17, 18], "admin")
    expect_error("смешение АП и гражд.",
                 lambda: combine_type([d1, adm]), MixedTypesError)
    ok = stitch_docs([d1, f2])
    expect_error("build_flow при смешении",
                 lambda: build_flow([d1, adm]), MixedTypesError)

    print("\n[6] build_flow: единый поток")
    flow = build_flow([f2, d1])
    check("порядок файлов", flow["files"], ["a.docx", "vol2.docx"])
    check("тип", flow["type"], CASE_CIVIL)
    check("f4", flow["f4"], 14)
    check("год", flow["year"], 2018)
    check("число строк", len(flow["rows"]), 6)
    check("номера потока", [r["F"] for r in flow["stream"]["rows"]],
          [14, 15, 16, 17, 18, 19])

    print("\n" + "=" * 60)
    print(f"ИТОГО: PASSED = {PASSED}, FAILED = {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
