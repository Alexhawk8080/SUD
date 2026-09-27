# -*- coding: utf-8 -*-
"""
Тесты core.text_utils.sanitize_text (fix_10_v2).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_text_utils.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.text_utils import sanitize_text

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
    print("[1] _x000D_ -> \\n")
    check("Литерал _x000D_",
          sanitize_text("08.12.2017_x000D_08.01.2018"),
          "08.12.2017\n08.01.2018")
    check("Литерал _x000d_ (нижний)",
          sanitize_text("a_x000d_b"),
          "a\nb")

    print("\n[2] CR / CRLF -> \\n")
    check("\\r\\n",
          sanitize_text("a\r\nb"),
          "a\nb")
    check("\\r один",
          sanitize_text("a\rb"),
          "a\nb")
    check("\\v (vertical tab)",
          sanitize_text("a\vb"),
          "a\nb")

    print("\n[3] \\n остаётся без изменений")
    check("Простой \\n",
          sanitize_text("a\nb"),
          "a\nb")
    check("Два \\n",
          sanitize_text("a\nb\nc"),
          "a\nb\nc")

    print("\n[4] Обычный текст")
    check("Без переносов",
          sanitize_text("08.12.2017"),
          "08.12.2017")
    check("Русский текст",
          sanitize_text("Привет, мир"),
          "Привет, мир")

    print("\n[5] Граничные")
    check("None -> None",
          sanitize_text(None), None)
    check("Пустая строка",
          sanitize_text(""), "")
    check("Число -> число (не строка)",
          sanitize_text(42), 42)
    check("Смешанное: _x000D_ + \\r + \\n",
          sanitize_text("a_x000D_b\rc\nd"),
          "a\nb\nc\nd")

    print("\n[6] Интеграция: Excel -> Word не портит даты")
    # Симулируем дату с _x000D_ из «грязного» источника
    from datetime import datetime
    from core.case_processor import process_cases
    from core.excel_reader import SourceRow

    rows = [SourceRow({
        "date": "08.12.2017_x000D_08.01.2018",  # мусор как строка
        "case_number": "2-2/2018",
        "applicants": "Масленников Николай Александрович",
        "respondents": 'АО "Мегафон Ритейл"',
        "category": "Исковое заявление о защите прав потребителей",
        "opis_number": 1, "unit_number": 1, "note": "",
        "end_date": None,
    })]
    orgs = {"АО": "по иску"}
    excl = ["АО", "ООО"]
    records, _ = process_cases(rows, 2018, False, orgs, excl)
    rec = records[0]
    # sanitize в build_case_record должен убрать _x000D_
    check("В dates нет _x000D_", "_x000D_" in rec["dates"], False)
    check("В dates есть \\n",
          "08.12.2017" in rec["dates"] and "08.01.2018" in rec["dates"], True)

    print("\n[7] Интеграция: Excel-вывод санитизирует ячейки")
    from core.excel_writer import write_excel_result
    import tempfile
    from openpyxl import load_workbook

    tmp = tempfile.mkdtemp(prefix="sanitize_")
    out = os.path.join(tmp, "test.xlsx")
    write_excel_result([{
        "sequential": 1, "title": "a_x000D_b",
        "dates": "x\ry", "opis": 1, "unit": 1, "count": 1,
        "retention": "3 года Ст. 208", "note": "z\r\nw",
    }], out)
    wb = load_workbook(out)
    ws = wb.active
    check("title без _x000D_",
          "_x000D_" in str(ws.cell(row=2, column=2).value), False)
    check("dates с \\n",
          ws.cell(row=2, column=3).value, "x\ny")
    check("note с \\n",
          ws.cell(row=2, column=8).value, "z\nw")
    wb.close()

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
