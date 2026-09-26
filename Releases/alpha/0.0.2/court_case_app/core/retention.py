# -*- coding: utf-8 -*-
"""
Определение срока хранения и статьи (порт GetRetentionInfo из Module1.bas).

Порядок ключевых слов критичен (в VBA — Scripting.Dictionary с порядком
вставки): «пенси» перекрывает более длинные корни, поэтому ключи заданы
списком кортежей.

Правила могут переопределяться из базы данных SQLite (таблица
retention_rules): keywords — список (root, code); texts — словарь
code -> текст результата. При keywords/texts=None используются значения
по умолчанию (1:1 с VBA).
"""

# Корень слова -> условный код типа (порядок важен!)
DEFAULT_KEYWORDS = [
    ("алимент", "aliens"),
    ("алиментн", "aliens"),
    ("алиментны", "aliens"),
    ("расторжен", "divorce"),
    ("брак", "divorce"),
    ("жилищн", "housing"),
    ("коммунальн", "housing"),
    ("платеж", "housing"),
    ("страхов", "insurance"),
    ("взнос", "insurance"),
    ("пенсион", "pension"),
    ("пенси", "pension"),
    ("выплат", "pension"),
    ("перерасчет", "pension_recalc"),
    ("потребител", "consumer"),
    ("потребит", "consumer"),
    ("налог", "tax"),
    ("налого", "tax"),
    ("займ", "loan_debt"),
    ("займа", "loan_debt"),
    ("долг", "loan_debt"),
    ("кредит", "credit_loan"),
    ("кредитн", "credit_loan"),
    ("взыскани", "collection"),
]

# Код типа -> итоговая строка
DEFAULT_RETENTION_TEXT = {
    "aliens": "1 год ЭК Ст. 139",
    "divorce": "3 года ЭК Ст. 137",
    "housing": "3 года Ст. 179",
    "insurance": "3 года Ст. 201",
    "pension_recalc": "5 лет ЭПК Ст. 202",
    "pension": "5 лет ЭПК Ст. 203",
    "consumer": "3 года ЭПК Ст. 208",
    "tax": "3 года Ст. 221",
    "loan_debt": "3 года Ст. 222",
    "credit_loan": "3 года Ст. 223",
    "collection": "3 года Ст. 227",
}

DEFAULT_TEXT = "3 года Ст. 227"


def get_retention_info(case_category, keywords=None, texts=None) -> str:
    """
    Определяет срок хранения и статью по тексту категории дела.

    Возвращает строку вида «<срок> Ст. <номер>» (ЭК/ЭПК при необходимости).
    Параметры keywords/texts позволяют подставить правила из базы данных.
    """
    if case_category is None:
        return DEFAULT_TEXT
    if isinstance(case_category, str) and not case_category.strip():
        return DEFAULT_TEXT

    search_text = str(case_category).strip().lower()
    kws = keywords if keywords is not None else DEFAULT_KEYWORDS
    txts = texts if texts is not None else DEFAULT_RETENTION_TEXT

    # Поиск первого совпавшего корня по словам (Len(word) > 3, как в VBA)
    found_type = ""
    for word in search_text.split():
        word = word.strip()
        if len(word) > 3:
            for root, code in kws:
                if root in word:
                    found_type = code
                    break
            if found_type:
                break

    if found_type == "aliens":
        if "изменен" in search_text or "размер" in search_text:
            return "1 год ЭК Ст. 139"
        if "друг" in search_text:
            return "1 год ЭК Ст. 140"
        return "1 год ЭК Ст. 139"

    if found_type == "pension":
        if "перерасчет" in search_text:
            return "5 лет ЭПК Ст. 202"
        if "нарушен" in search_text:
            return "5 лет ЭПК Ст. 203"
        return "5 лет ЭПК Ст. 203"

    if found_type:
        return txts.get(found_type, DEFAULT_TEXT)

    return DEFAULT_TEXT