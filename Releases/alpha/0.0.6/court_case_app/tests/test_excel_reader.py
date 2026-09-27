# -*- coding: utf-8 -*-
"""
Тесты чтения исходной таблицы Excel (Этап 4).

Создаёт временный .xlsx, проверяет автоопределение ролей, чтение значений,
ручной маппинг, обработку пустых ячеек и номера строки заголовков.

Запуск: .venv\\Scripts\\python.exe court_case_app\\tests\\test_excel_reader.py
"""

import sys
import os
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openpyxl import Workbook
from core.excel_reader import read_source_table, auto_detect_roles, ROLES

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


def make_test_file(path):
    """Создаёт тестовый файл со стандартными заголовками и двумя строками."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "№ дела", "Заявители", "Ответчики", "Категория",
               "№ описи", "№ ед.хр.", "Запасной столбец", "Примечание",
               "Ещё один", "Дата окончания"])
    ws.append([datetime(2023, 1, 10), "2-3/2023",
               "Саркисян Юлия Геннадьевна", "Саркисян Давид Сергеевич",
               "О расторжении брака", 1, 1, "запас", "дело закрыто", None,
               datetime(2023, 2, 10)])
    # Строка с пустыми ячейками
    ws.append([None, "2-5/2023", None, None, None, None, None, None, None, None, None])
    wb.save(path)


def make_no_headers_file(path):
    """Файл без заголовков: данные начинаются с первой строки."""
    wb = Workbook()
    ws = wb.active
    ws.append([datetime(2023, 1, 10), "2-3/2023", "Иванов Иван Иванович",
               "Петров Пётр Петрович", "О взыскании долга", 2, 5, "", "", ""])
    wb.save(path)


def main():
    tmp_dir = tempfile.mkdtemp(prefix="cases_")
    filepath = os.path.join(tmp_dir, "source.xlsx")
    noheaders = os.path.join(tmp_dir, "no_headers.xlsx")
    make_test_file(filepath)
    make_no_headers_file(noheaders)

    print("[1] Автоопределение ролей по заголовкам")
    headers_example = ["Дата", "№ дела", "Заявители", "Ответчики", "Категория",
                       "№ описи", "№ ед.хр.", "Примечание", "Дата окончания"]
    mapping = auto_detect_roles(headers_example)
    check("Все 9 ролей определены",
          sorted(mapping.keys()), sorted(ROLES))
    check("date -> столбец 1", mapping["date"], 1)
    check("case_number -> столбец 2", mapping["case_number"], 2)
    check("applicants -> столбец 3", mapping["applicants"], 3)
    check("respondents -> столбец 4", mapping["respondents"], 4)
    check("category -> столбец 5", mapping["category"], 5)
    check("opis_number -> столбец 6", mapping["opis_number"], 6)
    check("unit_number -> столбец 7", mapping["unit_number"], 7)
    check("note -> столбец 8", mapping["note"], 8)
    check("end_date -> столбец 9", mapping["end_date"], 9)

    print("\n[2] Чтение файла со стандартными заголовками")
    headers, rows, used = read_source_table(filepath)
    check("Количество строк данных", len(rows), 2)
    check("Маппинг date", used["date"], 1)
    check("Маппинг case_number", used["case_number"], 2)
    check("Маппинг end_date (колонка 11)", used["end_date"], 11)
    row0 = rows[0]
    check("Номер дела первой строки", row0.get("case_number"), "2-3/2023")
    check("Заявители первой строки",
          row0.get("applicants"), "Саркисян Юлия Геннадьевна")
    check("Категория первой строки",
          row0.get("category"), "О расторжении брака")
    check("Дата начала (datetime)", row0.get("date"), datetime(2023, 1, 10))
    check("Дата окончания (datetime)", row0.get("end_date"), datetime(2023, 2, 10))
    check("Примечание", row0.get("note"), "дело закрыто")

    print("\n[3] Пустые ячейки -> None")
    row1 = rows[1]
    check("Пустой номер дела не None?", row1.get("case_number") is None, False)
    check("Пустая категория -> None", row1.get("category"), None)
    check("Пустая дата -> None", row1.get("date"), None)

    print("\n[4] Ручной маппинг (файл без заголовков)")
    manual = {"date": 1, "case_number": 2, "applicants": 3, "respondents": 4,
              "category": 5, "opis_number": 6, "unit_number": 7}
    headers2, rows2, used2 = read_source_table(noheaders, mapping=manual,
                                               header_row=0)
    check("Данные считаны (1 строка)", len(rows2), 1)
    check("Автоопределение по заголовкам не сработало (первая строка - данные)",
          auto_detect_roles(["10.01.2023", "2-3/2023"]), {})
    check("Ручной маппинг применён", used2 == manual, True)
    check("Заявитель по ручному маппингу",
          rows2[0].get("applicants"), "Иванов Иван Иванович")
    check("Отсутствующая роль end_date -> None", rows2[0].get("end_date"), None)


    print("\n[5] Регрессия fix_01: неоднозначные алиасы заголовков")
    # «Номер описи» не должен трактоваться как case_number (алиас «номер»)
    m = auto_detect_roles(["Номер описи", "Номер дела"])
    check("«Номер описи» -> opis_number, «Номер дела» -> case_number",
          (m.get("opis_number"), m.get("case_number")), (1, 2))

    # «Дата окончания» не должна трактоваться как date (алиас «дата»)
    m = auto_detect_roles(["Дата окончания", "Дата"])
    check("«Дата окончания» -> end_date, «Дата» -> date",
          (m.get("end_date"), m.get("date")), (1, 2))

    # Перестановка колонок не должна ломать маппинг
    m = auto_detect_roles(["№ описи", "№ дела", "Дата", "Заявители",
                           "Ответчики", "Категория", "№ ед.хр.",
                           "Примечание", "Дата окончания"])
    check("Перестановка: № описи -> 1", m.get("opis_number"), 1)
    check("Перестановка: № дела -> 2", m.get("case_number"), 2)
    check("Перестановка: Дата -> 3", m.get("date"), 3)
    check("Перестановка: Дата окончания -> 9", m.get("end_date"), 9)

    # Отсутствие колонки «Дата» не «съедает» end_date
    m = auto_detect_roles(["Номер дела", "Номер описи", "Дата окончания",
                           "Заявители", "Ответчики", "Категория",
                           "№ ед.хр.", "Примечание"])
    check("Без «Дата»: end_date = 3", m.get("end_date"), 3)
    check("Без «Дата»: date не назначен", m.get("date"), None)

    # Один столбец — не более одной роли
    m = auto_detect_roles(["№ дела"])
    check("Один столбец -> одна роль", len(m), 1)

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()