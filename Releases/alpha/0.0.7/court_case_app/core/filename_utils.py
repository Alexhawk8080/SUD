# -*- coding: utf-8 -*-
"""
Формирование имени файла акта.

Формат:
    Акт уничтожения {тип дел} {участок}У {год}.{ext}

Примеры:
    Акт уничтожения гражданских дел 9У 2020.docx
    Акт уничтожения административных дел 5У 2019.xlsx
    Акт уничтожения гражданских дел 2020.docx  (если нет участка)
"""

# Отображаемый родительный падеж типа дел
_CASE_TYPE_LABEL = {
    "civil": "гражданских дел",
    "admin": "административных дел",
}


def make_act_filename(номер, case_type, year, ext) -> str:
    """
    Собирает имя файла акта.

    номер     — номер судебного участка (строка/число; пустое допустимо);
    case_type — 'civil' | 'admin' (или любое другое → по умолчанию civil);
    year      — год дел (число/строка);
    ext       — 'docx' | 'xlsx' (без точки).
    """
    type_part = _CASE_TYPE_LABEL.get(str(case_type or "civil").strip(),
                                     _CASE_TYPE_LABEL["civil"])
    num = str(номер or "").strip()
    parts = ["Акт уничтожения", type_part]
    if num:
        parts.append(f"{num} CУ")
    parts.append(str(year))
    ext_clean = str(ext or "").lstrip(".").strip()
    return " ".join(parts) + f".{ext_clean}"
