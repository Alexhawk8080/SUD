# -*- coding: utf-8 -*-
"""
Тесты чтения административной таблицы Excel (D8a).

Создаёт временный .xlsx со структурой «2020 адм.xlsx» (шапка в строке 3),
проверяет автоопределение ролей, чтение значений, ручной маппинг и
обработку пустых ячеек.

Запуск: .venv\\Scripts\\python.exe court_case_app\\tests\\test_admin_reader.py
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openpyxl import Workbook
from core.admin_reader import (
    read_admin_table,
    auto_detect_admin_roles,
    detect_admin_header_row,
    ADMIN_ROLES,
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


def make_admin_file(path):
    """Файл со структурой admin-таблицы: 2 пустые строки, шапка в строке 3."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Адм"
    ws.append(["Отчёт по административным делам", None, None, None, None])
    ws.append([None, None, None, None, None])
    ws.append(["Вх. №", "Дата поступления", "№ Дела в производстве",
               "ФИО/наименование лица", "Статья", None, None,
               "Текущая задача", None, None, "Окончание производства",
               None, "Состояние акта"])
    ws.append([101, datetime(2020, 1, 10), "5-1/2020",
               "Иванов Иван Иванович", "ст. 15.6 ч. 1", None, None,
               "в работе", None, None, None, None, "не сформирован"])
    ws.append([102, datetime(2020, 2, 20), "5-2/2020",
               "ООО Ромашка", "1.1 ч.1 ЗСО №104", None, None,
               "завершено", None, None, None, None, "сформирован"])
    wb.save(path)


def main():
    tmp_dir = tempfile.mkdtemp(prefix="admin_reader_")
    filepath = os.path.join(tmp_dir, "2020 адм.xlsx")
    make_admin_file(filepath)

    print("[1] Автоопределение ролей по заголовкам")
    headers = ["Вх. №", "Дата поступления", "№ Дела в производстве",
               "ФИО/наименование лица", "Статья", "Текущая задача",
               "Окончание производства", "Состояние акта"]
    mapping = auto_detect_admin_roles(headers)
    check("Все 8 ролей определены",
          sorted(mapping.keys()), sorted(ADMIN_ROLES))
    check("in_number -> 1", mapping["in_number"], 1)
    check("date -> 2", mapping["date"], 2)
    check("case_number -> 3", mapping["case_number"], 3)
    check("person -> 4", mapping["person"], 4)
    check("article -> 5", mapping["article"], 5)
    check("task -> 6", mapping["task"], 6)
    check("end_date -> 7", mapping["end_date"], 7)
    check("act_state -> 8", mapping["act_state"], 8)

    print("[2] Автоопределение строки заголовков")
    wb_rows = [
        ["Отчёт по административным делам", None, None, None, None],
        [None, None, None, None, None],
        ["Вх. №", "Дата поступления", "№ Дела в производстве",
         "ФИО/наименование лица", "Статья", "Текущая задача",
         "Окончание производства", "Состояние акта"],
    ]
    check("header_row = 3", detect_admin_header_row(wb_rows), 3)

    print("[3] Чтение таблицы (автоопределение)")
    headers, rows, used = read_admin_table(filepath)
    check("строк данных = 2", len(rows), 2)
    check("person[0]", rows[0].get("person"), "Иванов Иван Иванович")
    check("case_number[0]", rows[0].get("case_number"), "5-1/2020")
    check("article[0]", rows[0].get("article"), "ст. 15.6 ч. 1")
    check("in_number[0]", rows[0].get("in_number"), 101)
    check("task[0]", rows[0].get("task"), "в работе")
    check("act_state[0]", rows[0].get("act_state"), "не сформирован")
    check("end_date[0] пусто", rows[0].get("end_date"), None)
    check("person[1] (организация)", rows[1].get("person"), "ООО Ромашка")
    check("article[1] (ЗСО)", rows[1].get("article"), "1.1 ч.1 ЗСО №104")

    print("[4] Ручной маппинг")
    manual = {"case_number": 3, "person": 4, "article": 5}
    _h, rows2, used2 = read_admin_table(
        filepath, mapping=manual, header_row=3)
    check("ручной маппинг применён", used2, manual)
    check("case_number[0] (ручной)", rows2[0].get("case_number"), "5-1/2020")
    check("person[0] (ручной)", rows2[0].get("person"), "Иванов Иван Иванович")

    print("[5] Нормализация заголовков (дефисы/слэши)")
    weird = ["Вх-№", "Дата поступления", "№ Дела в производстве",
             "ФИО/наименование лица", "Статья", "Текущая задача",
             "Окончание производства", "Состояние акта"]
    m2 = auto_detect_admin_roles(weird)
    check("in_number распознан с дефисом", m2.get("in_number"), 1)
    check("person распознан со слэшем", m2.get("person"), 4)

    print()
    print(f"Итого: {PASSED} OK, {FAILED} FAIL")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
