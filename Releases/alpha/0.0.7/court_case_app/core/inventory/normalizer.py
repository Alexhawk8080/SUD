# -*- coding: utf-8 -*-
"""
Нормализация наименования -> столбец C «Таблицы» (этап 14b, решение 3).

Целевые значения (7):
    Постановление по делу об административном правонарушении
    Решение по делу об административном правонарушении
    Определение по делу об административном правонарушении
    Судебный приказ по гражданскому делу
    Определение по гражданскому делу
    Заочное решение по гражданскому делу
    Решение по гражданскому делу

Правило: сначала тип документа по ключевому слову (с приоритетом),
затем тип дела (гражданское / административное).

Приоритет ключевых слов типа документа (сверху вниз):
    1. Заочное решение
    2. Решение
    3. Определение
    4. Постановление
    5. Судебный приказ

Квалификаторы НЕ влияют на категорию (игнорируются):
    «резолютивная часть», «апелляционное», «частное»,
    «о прекращении», «об исправлении описки», «о предоставлении отсрочки».
"""

import re

# --- Типы документов (значения столбца C) ----------------------------------

DOC_POSTANOVLENIE = "Постановление по делу об административном правонарушении"
DOC_RESHENIE_ADM = "Решение по делу об административном правонарушении"
DOC_OPREDELENIE_ADM = "Определение по делу об административном правонарушении"
DOC_SUDEBNY_PRIKAZ = "Судебный приказ по гражданскому делу"
DOC_OPREDELENIE_GRAZHD = "Определение по гражданскому делу"
DOC_ZAOCHNOE = "Заочное решение по гражданскому делу"
DOC_RESHENIE_GRAZHD = "Решение по гражданскому делу"
ALL_DOC_TYPES = (
    DOC_POSTANOVLENIE, DOC_RESHENIE_ADM, DOC_OPREDELENIE_ADM,
    DOC_SUDEBNY_PRIKAZ, DOC_OPREDELENIE_GRAZHD, DOC_ZAOCHNOE,
    DOC_RESHENIE_GRAZHD,
)

# --- Типы дел ---------------------------------------------------------------

CASE_CIVIL = "civil"
CASE_ADMIN = "admin"

_ADMIN_RE = re.compile(r"административн|\bАП\b", re.IGNORECASE)
_CIVIL_RE = re.compile(r"гражданск", re.IGNORECASE)


def detect_case_type(name) -> str:
    """
    Тип дела по тексту «Наименования»: CASE_ADMIN / CASE_CIVIL / "".

    «об административном правонарушении» или «АП» -> административное;
    «гражданскому» -> гражданское.
    """
    text = " ".join(str(name or "").split())
    if _ADMIN_RE.search(text):
        return CASE_ADMIN
    if _CIVIL_RE.search(text):
        return CASE_CIVIL
    return ""


# Приоритет типа документа (сверху вниз).
_DOC_PRIORITY = (
    ("zaoch", re.compile(r"заочн\w*\s+решен", re.IGNORECASE)),
    ("reshen", re.compile(r"решен", re.IGNORECASE)),
    ("opred", re.compile(r"определен", re.IGNORECASE)),
    ("postan", re.compile(r"постановлен", re.IGNORECASE)),
    ("prikaz", re.compile(r"судебн\w*\s+приказ|приказ", re.IGNORECASE)),
)


def detect_doc_kind(name) -> str:
    """
    Тип документа по приоритету ключевых слов:
    zaoch / reshen / opred / postan / prikaz / "" (не распознан).
    """
    text = " ".join(str(name or "").split())
    for kind, rx in _DOC_PRIORITY:
        if rx.search(text):
            return kind
    return ""


# Соответствие (тип документа, тип дела) -> значение столбца C.
_DOC_MAP = {
    ("zaoch", CASE_CIVIL): DOC_ZAOCHNOE,
    ("reshen", CASE_CIVIL): DOC_RESHENIE_GRAZHD,
    ("reshen", CASE_ADMIN): DOC_RESHENIE_ADM,
    ("opred", CASE_CIVIL): DOC_OPREDELENIE_GRAZHD,
    ("opred", CASE_ADMIN): DOC_OPREDELENIE_ADM,
    ("postan", CASE_ADMIN): DOC_POSTANOVLENIE,
    ("prikaz", CASE_CIVIL): DOC_SUDEBNY_PRIKAZ,
}


def normalize_name(name):
    """
    Возвращает нормализованное значение столбца C или None,
    если тип документа/дела не распознан.

    Квалификаторы (резолютивная часть, апелляционное, частное,
    о прекращении и т.п.) не влияют на результат.
    """
    kind = detect_doc_kind(name)
    case = detect_case_type(name)
    if not kind or not case:
        return None
    return _DOC_MAP.get((kind, case))