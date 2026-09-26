# -*- coding: utf-8 -*-
"""
Общие функции работы с ФИО.

Порт логики модулей `родительный_падеж.bas` и `дательный_падеж.bas`
(VBA): парсинг строки ФИО, определение пола по отчеству, маскулинизация
женских фамилий, капитализация буквы после скобки.

Логика перенесена 1:1, чтобы результаты совпадали с VBA-версией.
"""

# Буквы-гласные для проверок окончаний (как в VBA-паттернах Like)
VOWELS = "уеыаоэяиюё"


def normalize_hyphens(text: str) -> str:
    """Нормализация дефисов: ' - ', ' -', '- ' -> '-' (как Replace в VBA)."""
    text = text.replace(" - ", "-")
    text = text.replace(" -", "-")
    text = text.replace("- ", "-")
    return text


def parse_full_name(full_name: str):
    """
    Разбор строки ФИО на части.

    Возвращает кортеж (surname, old_surname, name, patronymic).
    old_surname — фамилия в круглых скобках (может быть пустой).

    Соответствует блоку парсинга из VBA-функций GenitiveCase/DativeCase.
    """
    surname = ""
    old_surname = ""
    name = ""
    patronymic = ""

    parts = full_name.strip().split()

    if len(parts) >= 3:
        # Старая фамилия в скобках: Иванов (Петрова) Иван Иванович
        if parts[1].startswith("(") and parts[1].endswith(")"):
            surname = parts[0]
            old_surname = parts[1][1:-1]  # убираем скобки
            name = parts[2]
            if len(parts) >= 4:
                patronymic = parts[3].replace(".", "")
        else:
            last_part = parts[-1].lower()
            # Частицы «оглы»/«кызы» в конце: Алиев Али оглы
            if (last_part in ("оглы", "кызы")) and len(parts) >= 4:
                surname = parts[0]
                name = parts[1]
                patronymic = parts[2] + " " + parts[3]
            else:
                surname = parts[0]
                name = parts[1]
                patronymic = parts[2].replace(".", "")
    elif len(parts) == 2:
        surname = parts[0]
        name = parts[1]
    else:
        surname = parts[0] if parts else ""

    return surname, old_surname, name, patronymic


def is_male(patronymic: str) -> bool:
    """
    Определение пола по отчеству (как в VBA):
    bMaleSex = Not (Right(patronymic, 2) = "на" Or Right(patronymic, 4) = "кызы")
    Сравнение без учёта регистра (Option Compare Text).
    """
    p = patronymic.lower()
    if p.endswith("на") or p.endswith("кызы"):
        return False
    return True


def is_feminine_surname(surname: str) -> bool:
    """Проверка, что фамилия имеет женскую форму (как IsFeminineSurname)."""
    s = surname.lower()
    return (
        s.endswith(("ова", "ева", "ёва", "ина", "ая", "яя", "ская", "цкая"))
    )


def masculinize_surname(surname: str) -> str:
    """Приведение женской фамилии к мужской форме (MasculinizeSurname)."""
    s = surname.lower()
    if s.endswith(("ская", "цкая")):
        return surname[:-2] + "ий"
    if s.endswith(("ова", "ева", "ёва")):
        return surname[:-1]
    if s.endswith("ина"):
        return surname[:-1]
    if s.endswith(("ая", "яя")):
        stem = surname[:-2]
        if stem:
            last_stem = stem[-1].lower()
            if last_stem in "шжчщ":
                return stem + "ий"
            return stem + "ый"
        return surname
    return surname


def fix_parentheses_case(text: str) -> str:
    """Капитализация буквы сразу после '(' (FixParenthesesCase)."""
    result = list(text)
    pos = text.find("(")
    while pos != -1:
        if pos + 1 < len(text):
            result[pos + 1] = text[pos + 1].upper()
        pos = text.find("(", pos + 1)
    return "".join(result)


def proper_case(text: str) -> str:
    """
    Аналог StrConv(text, vbProperCase): каждое слово с заглавной буквы,
    остальные буквы слова — строчные.
    Используется str.title(): корректно обрабатывает слова со скобками
    («(петрова)» -> «(Петрова)») и после дефиса, как vbProperCase.
    """
    return text.title()