# -*- coding: utf-8 -*-
"""Сквозная проверка admin: загрузка -> обработка -> экспорт (D8)."""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "court_case_app")

from database import db
from core.db_pipeline import (
    process_year,
    save_year_source_from_xlsx,
    export_year_result_to_file,
)

tmp = tempfile.mkdtemp(prefix="d8_")
path = os.path.join(tmp, "app.db")
conn = db.init_db(path)

aid = db.add_court_area(conn, {"номер": "9"})
yid = db.add_court_year(conn, aid, 2020, {
    "судья": "Судья", "секретарь": "Сек", "номер_акта": "1",
    "дата_утверждения": "—", "дата_акта": "—", "дата_подписи": "—",
    "протокол_эк_дата": "—", "протокол_эк_номер": "1",
})

res = save_year_source_from_xlsx(
    conn, yid, r"2020 адм.xlsx", "2020 адм.xlsx",
    header_row=3, case_type="admin")
print("загрузка:", {k: res[k] for k in
                    ("row_count", "valid_count", "problematic_count")})

out = process_year(conn, yid, case_type="admin", court_area_id=aid)
print("обработка: record_count =", out["record_count"],
      "| stats:", out["stats"])

# Экспорт в Word
tpl_admin = r"court_case_app/docs/АКТ уничтожения административных дел.docx"
tpl_civil = r"court_case_app/docs/АКТ уничтожения гражданских дел.docx"
r = export_year_result_to_file(
    conn, out["result_id"], template_path=tpl_civil,
    template_path_admin=tpl_admin, output_dir=os.path.join(tmp, "out"),
    output_format="word")
print("экспорт:", r["filename"], "| записей:", r["record_count"])

# Проверим содержимое
from docx import Document
from docx.oxml.ns import qn
d = Document(r["path"])
text = " ".join(n.text or "" for n in d.element.body.iter(qn("w:t")))
print("остались плейсхолдеры:", "{{" in text)
print("есть 'административных дел за':", "административных дел за" in text)
print("есть 'количество_прописью':", "количество_прописью" in text)
print("есть 'пятьсот тридцать':", "пятьсот тридцать" in text)
conn.close()
