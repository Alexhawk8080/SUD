# -*- coding: utf-8 -*-
"""
Склонение ФИО в родительный падеж (кого? чего?).

Порт функции GenitiveCase() из модуля `родительный_падеж.bas` (VBA) 1:1.
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


# Исключения имён: форма родительного падежа (ключ — в нижнем регистре)
_GENITIVE_NAME_EXCEPTIONS = {
    "павел": "Павла",
    "лев": "Льва",
    "пётр": "Петра",
    "любовь": "Любови",
}
# Имена, не склоняющиеся (возвращаются как есть)
_UNCHANGED_NAMES = {"али", "бали"}


def get_genitive_exception(name: str) -> str:
    """Исключение для имени (GetGenitiveException). Пустая строка, если нет."""
    key = name.strip().lower()
    if key in _GENITIVE_NAME_EXCEPTIONS:
        return _GENITIVE_NAME_EXCEPTIONS[key]
    if key in _UNCHANGED_NAMES:
        return name.strip()
    return ""


def surname_to_genitive(surname_part: str, male: bool) -> str:
    """Склонение фамилии в родительный падеж (SurnameToGenitive)."""
    s_part = surname_part
    s_res = s_part

    if male:
        last = s_part[-1]
        if last in "оиыуэею":
            s_res = s_part
        elif last == "й":
            s_res = s_part[:-2] + "ого"
        elif last == "ь":
            s_res = s_part[:-1] + "я"
        elif last == "я":
            s_res = s_part[:-1] + "и"
        elif last == "а":
            s_res = s_part[:-1] + "ы"
        else:
            s_res = s_part + "а"

        last_two = s_part[-2:]
        if last_two == "ец":
            # Like "*[гласная]ец" — гласная непосредственно перед "ец"
            if len(s_part) >= 4 and _is_vowel(s_part[-3]):
                s_res = s_part[:-1] + "ца"
            # Like "*[!гласная][!гласная]ец" — два согласных перед "ец"
            elif len(s_part) >= 5 and not _is_vowel(s_part[-4]) and not _is_vowel(s_part[-3]):
                s_res = s_part + "а"
            else:
                s_res = s_part[:-2] + "ца"
        elif last_two in ("зе", "их", "ых"):
            s_res = s_part
        elif last_two == "ый":
            s_res = s_part[:-2] + "ого"
        elif last_two in ("ий", "ой"):
            s_res = s_part[:-2] + "ого"
            if len(s_part) <= 4:
                s_res = s_part[:-1] + "я"
            if s_part[-3:] == "чий":
                s_res = s_part[:-2] + "его"
        elif last_two == "уй":
            s_res = s_part[:-2] + "уя"
    else:
        last = s_part[-1]
        if last in "оеэиыуюбвгджзклмнпрстфхцчшщьй":
            s_res = s_part
        elif last == "а":
            s_res = s_part[:-1] + "ой"
        elif last == "я":
            s_res = s_part[:-2] + "ю"
        else:
            s_res = s_part[:-1] + "у"

        last_two = s_part[-2:]
        if last_two == "ха":
            s_res = s_part[:-2] + "хи"
        elif last_two == "ла":
            s_res = s_part[:-2] + "лы"
        elif last_two == "ая":
            s_res = s_part[:-2] + "ой"

    # Like "*[гласная]а" — фамилия на "гласная+а" не склоняется
    if len(s_part) >= 2 and s_part[-1] == "а" and _is_vowel(s_part[-2]):
        s_res = s_part

    return s_res


def genitive_case(full_name: str) -> str:
    """
    Склонение ФИО в родительный падеж (GenitiveCase).

    Принимает полную строку «Фамилия Имя Отчество» (возможна старая фамилия
    в скобках), возвращает строку в родительном падеже.
    """
    surname = normalize_hyphens(full_name)

    surname_part, old_surname, name, patronymic = parse_full_name(surname)

    male = is_male(patronymic)

    # Приведение женской фамилии к мужской для мужчин
    if male and is_feminine_surname(surname_part):
        surname_part = masculinize_surname(surname_part)
    if male and old_surname and is_feminine_surname(old_surname):
        old_surname = masculinize_surname(old_surname)

    result = surname_to_genitive(surname_part, male)
    if old_surname:
        result += " (" + surname_to_genitive(old_surname, male) + ")"
    result += " "

    if name:
        exception = get_genitive_exception(name)
        if exception:
            result += exception
        else:
            last = name[-1]
            if male:
                if last in "йь":
                    result += name[:-1] + "я"
                elif last == "а":
                    result += name[:-1] + "ы"
                elif last == "я":
                    result += name[:-1] + "и"
                elif last == "о":
                    result += name
                else:
                    result += name + "а"
            else:
                if last == "а":
                    result += name[:-1] + "ы"
                elif last == "я":
                    result += name[:-1] + "и"
                else:
                    result += name
        result += " "

    if patronymic:
        if patronymic.lower().endswith(("оглы", "кызы")):
            result += patronymic
        else:
            if male:
                result += patronymic + "а"
            else:
                result += patronymic[:-1] + "ы"

    result = result.replace("-", "- ")
    result = proper_case(result)
    result = fix_parentheses_case(result)
    result = result.replace("- ", "-")
    return result