# -*- coding: utf-8 -*-
"""
Проверка API доработки 6 (проверка категорий) на реальных файлах.

Запуск: .venv\\Scripts\\python.exe court_case_app\\tools\\check_categories_api.py
Проверяет: /check_page, /check_categories (source + legacy), /apply_corrections.
"""

import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

from app import app  # noqa: E402


def main():
    client = app.test_client()

    r = client.get("/check_page")
    print("GET /check_page:", r.status_code)

    # 1. Исходная таблица (реальный файл пользователя)
    src = os.path.join(BASE, "uploads", "2020 гр.xlsx")
    if not os.path.exists(src):
        print("НЕТ файла uploads/2020 гр.xlsx — пропуск source-проверки")
    else:
        with open(src, "rb") as f:
            data = {"file": (f, "2020 гр.xlsx"), "file_type": "source",
                    "year": "2020", "alimony": "0", "header_row": ""}
            resp = client.post("/check_categories", data=data,
                               content_type="multipart/form-data")
        print("POST /check_categories (source):", resp.status_code)
        if resp.status_code == 200:
            j = resp.get_json()
            st = j.get("stats", {})
            print("  cases_total:", j.get("cases_total"),
                  "| problematic:", st.get("total"),
                  "| with_analogs:", st.get("with_analogs"),
                  "| from_dictionary:", st.get("from_dictionary"),
                  "| no_analog:", st.get("no_analog"),
                  "| groups:", st.get("groups"),
                  "| auto_fix_enabled:", j.get("auto_fix_enabled"))
            if j.get("problematic"):
                p0 = j["problematic"][0]
                print("  Пример:", p0["case_number"], "|", p0["plaintiff_label"],
                      "| предложено:", p0["suggested"] or "-",
                      "| источник:", p0["source"])
        else:
            print("  ОШИБКА:", resp.get_json())

    # 2. Готовый результат (последний файл из output/)
    outp = os.path.join(BASE, "output")
    legacy = sorted(n for n in os.listdir(outp)
                    if n.startswith("результат_обработки") and n.endswith(".xlsx"))
    if not legacy:
        print("НЕТ файлов-результатов в output/ — пропуск legacy-проверки")
    else:
        path = os.path.join(outp, legacy[-1])
        with open(path, "rb") as f:
            data = {"file": (f, os.path.basename(path)), "file_type": "legacy",
                    "year": "2020", "alimony": "0"}
            resp2 = client.post("/check_categories", data=data,
                                content_type="multipart/form-data")
        print("POST /check_categories (legacy:", os.path.basename(path), "):",
              resp2.status_code)
        if resp2.status_code == 200:
            j2 = resp2.get_json()
            st2 = j2.get("stats", {})
            print("  cases_total:", j2.get("cases_total"),
                  "| problematic:", st2.get("total"),
                  "| no_analog:", st2.get("no_analog"),
                  "| groups:", st2.get("groups"))
        else:
            print("  ОШИБКА:", resp2.get_json())

    # 3. Сохранение в словарь + очистка тестовой записи
    r3 = client.post("/apply_corrections", json={"saves": [{
        "key": "тестключ", "label": "Тест", "category": "о взыскании теста",
        "is_organization": False}]})
    print("POST /apply_corrections:", r3.status_code, r3.get_json())
    conn = sqlite3.connect(os.path.join(BASE, "database", "app.db"))
    conn.execute("DELETE FROM case_categories WHERE plaintiff_key='тестключ'")
    conn.commit()
    conn.close()
    print("Тестовая запись словаря удалена")

    # 4. Обработка с исправлениями (fixes) — реальный файл
    if os.path.exists(src):
        with open(src, "rb") as f:
            data = {"file": (f, "2020 гр.xlsx"), "year": "2020",
                    "alimony": "0", "header_row": "", "format": "excel",
                    "fixes": '{"2-1/2020": "о взыскании задолженности по '
                             'кредитному договору"}',
                    "auto_fix": "1"}
            resp4 = client.post("/process", data=data,
                                content_type="multipart/form-data")
        print("POST /process (with fixes):", resp4.status_code)
        if resp4.status_code == 200:
            j4 = resp4.get_json()
            print("  filename:", j4.get("filename"))
            rec = next((x for x in j4["records"]
                        if "2-1/2020" in (x.get("title") or "")), None)
            print("  2-1/2020 title:", (rec or {}).get("title"))
        else:
            print("  ОШИБКА:", resp4.get_json())

    # 5. Скачивание таблицы «Без аналогов»
    r5 = client.post("/download_no_analog_table", json={
        "groups": [{"label": "Тест", "cases": [{"case_number": "2-9/2020"}]}],
        "year": "2020"})
    print("POST /download_no_analog_table:", r5.status_code,
          "| content-type:", r5.content_type)

    # 6. Обработка готового результата (legacy) — раньше давала 400
    if legacy:
        path = os.path.join(outp, legacy[-1])
        with open(path, "rb") as f:
            data = {"file": (f, os.path.basename(path)), "file_type": "legacy",
                    "year": "2020", "alimony": "0", "format": "excel",
                    "fixes": "{}", "auto_fix": "1"}
            resp6 = client.post("/process", data=data,
                                content_type="multipart/form-data")
        print("POST /process (legacy):", resp6.status_code)
        if resp6.status_code == 200:
            j6 = resp6.get_json()
            print("  filename:", j6.get("filename"))
            print("  stats_message:", (j6.get("stats_message") or "")[:200])
        else:
            print("  ОШИБКА:", resp6.get_json())


if __name__ == "__main__":
    main()