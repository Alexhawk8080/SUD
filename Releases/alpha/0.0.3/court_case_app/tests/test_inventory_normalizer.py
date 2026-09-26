# -*- coding: utf-8 -*-
"""
Тесты нормализации наименования (столбец C) — этап 14b.

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_inventory_normalizer.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.inventory.normalizer import (
    CASE_ADMIN,
    CASE_CIVIL,
    DOC_OPREDELENIE_ADM,
    DOC_OPREDELENIE_GRAZHD,
    DOC_POSTANOVLENIE,
    DOC_RESHENIE_ADM,
    DOC_RESHENIE_GRAZHD,
    DOC_SUDEBNY_PRIKAZ,
    DOC_ZAOCHNOE,
    detect_case_type,
    detect_doc_kind,
    normalize_name,
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
    print("[1] detect_case_type")
    check("гражданское", detect_case_type("Решение по гражданскому делу"),
          CASE_CIVIL)
    check("административное",
          detect_case_type("Постановление по делу об административном правонарушении"),
          CASE_ADMIN)
    check("АП", detect_case_type("Определение по делу об АП"), CASE_ADMIN)
    check("не распознан", detect_case_type("Исковое заявление"), "")
    check("None", detect_case_type(None), "")

    print("\n[2] detect_doc_kind (приоритет)")
    check("заочное", detect_doc_kind("Заочное решение по гражданскому делу"),
          "zaoch")
    check("решение", detect_doc_kind("Решение по гражданскому делу"), "reshen")
    check("определение",
          detect_doc_kind("Апелляционное определение по гражданскому делу"),
          "opred")
    check("постановление",
          detect_doc_kind("Постановление по делу об АП"), "postan")
    check("приказ",
          detect_doc_kind("Судебный приказ по гражданскому делу"), "prikaz")
    check("не распознан", detect_doc_kind("Справка"), "")

    print("\n[3] normalize_name: 7 целевых значений")
    check("постановление АП",
          normalize_name("Постановление по делу об административном правонарушении"),
          DOC_POSTANOVLENIE)
    check("решение АП",
          normalize_name("Решение по делу об административном правонарушении"),
          DOC_RESHENIE_ADM)
    check("определение АП",
          normalize_name("Определение по делу об административном правонарушении"),
          DOC_OPREDELENIE_ADM)
    check("судебный приказ",
          normalize_name("Судебный приказ по гражданскому делу"),
          DOC_SUDEBNY_PRIKAZ)
    check("определение гражд.",
          normalize_name("Определение по гражданскому делу"),
          DOC_OPREDELENIE_GRAZHD)
    check("заочное решение",
          normalize_name("Заочное решение по гражданскому делу"),
          DOC_ZAOCHNOE)
    check("решение гражд.",
          normalize_name("Решение по гражданскому делу"),
          DOC_RESHENIE_GRAZHD)

    print("\n[4] normalize_name: квалификаторы не влияют")
    check("постановление о прекращении",
          normalize_name("Постановление о прекращении по делу об АП"),
          DOC_POSTANOVLENIE)
    check("определение об исправлении описки",
          normalize_name("Определение об исправлении описки по делу об АП"),
          DOC_OPREDELENIE_ADM)
    check("апелляционное определение",
          normalize_name("Апелляционное определение по гражданскому делу"),
          DOC_OPREDELENIE_GRAZHD)
    check("частное определение",
          normalize_name("Частное определение по гражданскому делу"),
          DOC_OPREDELENIE_GRAZHD)
    check("резолютивная часть",
          normalize_name("Решение (резолютивная часть) по гражданскому делу"),
          DOC_RESHENIE_GRAZHD)
    check("приоритет заочного",
          normalize_name("Заочное решение по гражданскому делу"),
          DOC_ZAOCHNOE)

    print("\n[5] normalize_name: не распознано")
    check("без типа дела", normalize_name("Решение по делу"), None)
    check("без типа документа",
          normalize_name("По гражданскому делу"), None)
    check("None", normalize_name(None), None)

    print("\n" + "=" * 60)
    print(f"ИТОГО: PASSED = {PASSED}, FAILED = {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
