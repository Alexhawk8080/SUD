# -*- coding: utf-8 -*-
"""Сравнение двух реализаций склонения:
A) наша (порт VBA 1:1: core.genitive / core.dative / справочник организаций);
B) предложенная на pymorphy3 (код пользователя).

Прогоняет обе на тестовых ФИО из test_names.py + примерах организаций.
"""
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.genitive import genitive_case
from core.dative import dative_case
from core.case_processor import is_organization as our_is_org

# ---------- Реализация B (pymorphy3, код пользователя) ----------
import pymorphy3
morph = pymorphy3.MorphAnalyzer()

ORG_MARKERS = re.compile(
    r'\b(ООО|ОАО|ЗАО|ПАО|АО|ИП|НКО|МУП|ГУП|ФГУП|банк|компания|организация|учреждение|'
    r'администрация|департамент|министерство|фонд|ассоциация|союз|предприятие|фирма|'
    r'корпорация|холдинг|группа)\b',
    re.IGNORECASE
)


def py_is_organization(text: str) -> bool:
    if ORG_MARKERS.search(text):
        return True
    if any(q in text for q in ('«', '»', '"')):
        return True
    words = re.findall(r'[А-ЯЁа-яё-]+', text)
    if not words:
        return True
    fio_tags = 0
    for w in words:
        p = morph.parse(w)[0]
        if {'Surn', 'Name', 'Patr', 'Init'} & set(p.tag.grammemes):
            fio_tags += 1
    return not (fio_tags >= 2 and len(words) <= 3)


def py_inflect_word(word, target_case, gender=None, number=None):
    if re.fullmatch(r'[А-ЯЁ]\.', word):
        return word
    parses = morph.parse(word)
    best = None
    for p in parses:
        if gender and gender not in p.tag.grammemes:
            continue
        if number and number not in p.tag.grammemes:
            continue
        best = p
        break
    if not best:
        best = parses[0]
    inflected = best.inflect({target_case})
    return inflected.word if inflected else best.word


def py_decline_person(text, target_case):
    words = text.split()
    gender = number = None
    for w in words:
        if re.fullmatch(r'[А-ЯЁ]\.', w):
            continue
        for p in morph.parse(w):
            if 'Name' in p.tag.grammemes or 'Patr' in p.tag.grammemes:
                if 'masc' in p.tag.grammemes:
                    gender = 'masc'
                elif 'femn' in p.tag.grammemes:
                    gender = 'femn'
                if 'sing' in p.tag.grammemes:
                    number = 'sing'
                elif 'plur' in p.tag.grammemes:
                    number = 'plur'
                break
        if gender:
            break
    result = []
    for w in words:
        if re.fullmatch(r'[А-ЯЁ]\.', w):
            result.append(w)
        else:
            result.append(py_inflect_word(w, target_case, gender, number))
    return ' '.join(result)


def py_decline_organization(text, target_case):
    parts = re.split(r'([«»"])', text)
    in_quotes = False
    result = []
    for part in parts:
        if part in ('«', '»', '"'):
            if part == '«':
                in_quotes = True
            elif part == '»':
                in_quotes = False
            elif part == '"':
                in_quotes = not in_quotes
            result.append(part)
            continue
        if in_quotes:
            result.append(part)
        else:
            tokens = re.split(r'(\s+|[.,;])', part)
            for token in tokens:
                if re.fullmatch(r'[А-ЯЁ]{2,}', token):
                    result.append(token)
                elif re.fullmatch(r'[А-ЯЁа-яё-]+', token):
                    result.append(py_inflect_word(token, target_case))
                else:
                    result.append(token)
    return ''.join(result)


def py_decline_entity(entity, target_case):
    entity = entity.strip()
    if py_is_organization(entity):
        return py_decline_organization(entity, target_case)
    return py_decline_person(entity, target_case)


def py_decline_list(s, target_case='nomn'):
    items = [item.strip() for item in s.split(';') if item.strip()]
    declined = [py_decline_entity(item, target_case) for item in items]
    return '; '.join(declined)


# ---------- Данные для сравнения ----------
GEN_CASES = [
    ("Саркисян Юлия Геннадьевна", "Саркисян Юлии Геннадьевны"),
    ("Орехова Людмила Николаевна", "Ореховой Людмилы Николаевны"),
    ("Сурков Эдуард Владимирович", "Суркова Эдуарда Владимировича"),
    ("Чернова Наталья Олеговна", "Черновой Натальи Олеговны"),
    ("Китаева Наталья Александровна", "Китаевой Натальи Александровны"),
    ("Суздальцева Юлия Михайловна", "Суздальцевой Юлии Михайловны"),
    ("Зверева Галина Евгеньевна", "Зверевой Галины Евгеньевны"),
    ("Голованова Владимир Валерьевич", "Голованова Владимира Валерьевича"),
    ("Иванов (Петрова) Иван Иванович", "Иванова (Петрова) Ивана Ивановича"),
    ("Алиев Али оглы", "Алиева Али Оглы"),
    ("Петров Павел Петрович", "Петрова Павла Петровича"),
    ("Толстой Лев Николаевич", "Толстого Льва Николаевича"),
    ("Петров Пётр Иванович", "Петрова Петра Ивановича"),
    ("Иванова Любовь Андреевна", "Ивановой Любови Андреевны"),
]
DAT_CASES = [
    ("Саркисян Юлия Геннадьевна", "Саркисян Юлии Геннадьевне"),
    ("Саркисян Давид Сергеевич", "Саркисяну Давиду Сергеевичу"),
    ("Орехов Игорь Анатольевич", "Орехову Игорю Анатольевичу"),
    ("Гринчева Оксана Геннадьевна", "Гринчевой Оксане Геннадьевне"),
    ("Суздальцева Юлия Михайловна", "Суздальцевой Юлии Михайловне"),
    ("Голованова Владимир Валерьевич", "Голованову Владимиру Валерьевичу"),
    ("Иванов (Петрова) Иван Иванович", "Иванову (Петрову) Ивану Ивановичу"),
    ("Алиев Али оглы", "Алиеву Али Оглы"),
    ("Петров Павел Петрович", "Петрову Павлу Петровичу"),
    ("Толстой Лев Николаевич", "Толстому Льву Николаевичу"),
    ("Петров Пётр Иванович", "Петрову Петру Ивановичу"),
]

ORG_SAMPLES = [
    "ООО \"Ромашка\"",
    "АО «Сбербанк»",
    "Администрация города",
    "ПАО «Сбербанк России»",
    "ИП Иванов",
    "СБЕРБАНК",
    "НАО",
    "МФК «Займер»",
]

PERSON_SAMPLES = [
    "Иванов Иван Иванович",
    "Иванова Мария Петровна",
]

# ---------- Сравнение ----------
print("=" * 78)
print("Склонение ФИО (родительный). Ожидаемое = наша (VBA 1:1)")
print("=" * 78)
diff_cnt = 0
for inp, expected in GEN_CASES:
    ours = genitive_case(inp)
    theirs = py_decline_entity(inp, 'gent')
    mark = "  " if ours == theirs == expected else "!!"
    if ours != theirs:
        diff_cnt += 1
    print(f"{mark} {inp!r}")
    print(f"    ожид: {expected!r}")
    print(f"    наши: {ours!r}")
    print(f"    pym3: {theirs!r}")

print()
print("=" * 78)
print("Склонение ФИО (дательный). Ожидаемое = наша (VBA 1:1)")
print("=" * 78)
for inp, expected in DAT_CASES:
    ours = dative_case(inp)
    theirs = py_decline_entity(inp, 'datv')
    mark = "  " if ours == theirs == expected else "!!"
    if ours != theirs:
        diff_cnt += 1
    print(f"{mark} {inp!r}")
    print(f"    ожид: {expected!r}")
    print(f"    наши: {ours!r}")
    print(f"    pym3: {theirs!r}")

print()
print("=" * 78)
print("Определение организации: наша (справочник БД/VBA) vs pymorphy3-эвристика")
print("=" * 78)
# Наши исключения/организации (как в БД после наполнения): первые слова
our_org_first_words = {
    "ооо", "ао", "зао", "оао", "пао", "нао", "ип", "гк", "гск", "тсж", "уо",
    "упф", "ифнс", "пко", "мфк", "мфо", "кпк", "сбербанк", "связной", "банк",
}
for s in ORG_SAMPLES + PERSON_SAMPLES:
    first = s.split(" ", 1)[0].strip("«»\"").lower()
    ours = our_is_org(s, our_org_first_words)
    theirs = py_is_organization(s)
    mark = "  " if ours == theirs else "!!"
    print(f"{mark} {s!r}: наша(справочник)={ours}, pym3={theirs}")

print()
print("Склонение организаций pymorphy3 (наша версия НЕ склоняет организации вообще):")
for s in ORG_SAMPLES:
    print(f"  {s!r} (род.) -> {py_decline_entity(s, 'gent')!r}")

print()
print(f"РАСХОЖДЕНИЙ (наши vs pym3) по ФИО: {diff_cnt}")