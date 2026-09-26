# -*- coding: utf-8 -*-
"""
Склонение ФИО в дательный падеж (кому? чему?).

Порт функции DativeCase() из модуля `дательный_падеж.bas` (VBA) 1:1.
"""

from .names_utils import (
    fix_parentheses_case,
    is_feminine_surname,
    is_male,
    masculinize_surname,
    normalize_hyphens,
    parse_full_name,
    proper_case,
)

# Гласные для проверок Like-паттернов VBA
_VOWELS = "уеыаоэяиюё"


def _is_vowel(ch: str) -> bool:
    return ch.lower() in _VOWELS


# Исключения имён: форма дательного падежа (ключ — в нижнем регистре)
_DATIVE_NAME_EXCEPTIONS = {
    "павел": "Павлу",
    "лев": "Льву",
    "пётр": "Петру",
}
# Имена, не склоняющиеся (возвращаются как есть)
_UNCHANGED_NAMES = {"али", "бали"}


def get_dative_exception(name: str) -> str:
    """Исключение для имени (GetDativeException). Пустая строка, если нет."""
    key = name.strip().lower()
    if key in _DATIVE_NAME_EXCEPTIONS:
        return _DATIVE_NAME_EXCEPTIONS[key]
    if key in _UNCHANGED_NAMES:
        return name.strip()
    return ""


def surname_to_dative(surname_part: str, male: bool) -> str:
    """Склонение фамилии в дательный падеж (SurnameToDative)."""
    s_part = surname_part
    s_res = s_part

    if male:
        last = s_part[-1]
        if last in "оиыуэею":
            s_res = s_part
        elif last in "ьй":
            s_res = s_part[:-1] + "ю"
        elif last in "яа":
            s_res = s_part[:-1] + "е"
        else:
            s_res = s_part + "у"

        last_two = s_part[-2:]
        if last_two == "ец":
            # Like "*[гласная]ец" — гласная непосредственно перед "ец"
            if len(s_part) >= 4 and _is_vowel(s_part[-3]):
                s_res = s_part[:-1] + "цу"
            # Like "*[!гласная][!гласная]ец" — два согласных перед "ец"
            elif len(s_part) >= 5 and not _is_vowel(s_part[-4]) and not _is_vowel(s_part[-3]):
                s_res = s_part + "у"
            else:
                s_res = s_part[:-2] + "цу"
        elif last_two in ("зе", "их", "ых"):
            s_res = s_part
        elif last_two == "ый":
            s_res = s_part[:-2] + "ому"
        elif last_two in ("ий", "ой"):
            s_res = s_part[:-2] + "ому"
            if len(s_part) <= 4:
                s_res = s_part[:-1] + "ю"
            if s_part[-3:] == "чий":
                s_res = s_part[:-2] + "ему"
        elif last_two == "уй":
            s_res = s_part[:-2] + "ую"
    else:
        last = s_part[-1]
        if last in "оеэиыуюбвгджзклмнпрстфхцчшщьй":
            s_res = s_part
        elif last == "я":
            s_res = s_part[:-2] + "ой"
        else:
            s_res = s_part[:-1] + "ой"

        last_two = s_part[-2:]
        if last_two in ("ха", "ла", "ее"):
            s_res = s_part[:-1] + "е"

    # Like "*[гласная]а" — фамилия на "гласная+а" не склоняется
    if len(s_part) >= 2 and s_part[-1] == "а" and _is_vowel(s_part[-2]):
        s_res = s_part

    return s_res


def dative_case(full_name: str) -> str:
    """
    Склонение ФИО в дательный падеж (DativeCase).

    Принимает полную строку «Фамилия Имя Отчество» (возможна старая фамилия
    в скобках), возвращает строку в дательном падеже.
    """
    surname = normalize_hyphens(full_name)

    surname_part, old_surname, name, patronymic = parse_full_name(surname)

    male = is_male(patronymic)

    # Приведение женской фамилии к мужской для мужчин
    if male and is_feminine_surname(surname_part):
        surname_part = masculinize_surname(surname_part)
    if male and old_surname and is_feminine_surname(old_surname):
        old_surname = masculinize_surname(old_surname)

    result = surname_to_dative(surname_part, male)
    if old_surname:
        result += " (" + surname_to_dative(old_surname, male) + ")"
    result += " "

    if name:
        exception = get_dative_exception(name)
        if exception:
            result += exception
        else:
            last = name[-1]
            if male:
                if last in "йь":
                    result += name[:-1] + "ю"
                elif last in "яа":
                    result += name[:-1] + "е"
                elif last in "оы":
                    result += name
                else:
                    result += name + "у"
            else:
                if last in "ая":
                    if len(name) >= 2 and name[-2] == "и":
                        result += name[:-1] + "и"
                    else:
                        result += name[:-1] + "е"
                elif last == "ь":
                    result += name[:-1] + "и"
                else:
                    result += name
        result += " "

    if patronymic:
        if patronymic.lower().endswith(("оглы", "кызы")):
            result += patronymic
        else:
            if male:
                result += patronymic + "у"
            else:
                result += patronymic[:-1] + "е"

    result = result.replace("-", "- ")
    result = proper_case(result)
    result = fix_parentheses_case(result)
    result = result.replace("- ", "-")
    return result