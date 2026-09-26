# -*- coding: utf-8 -*-
"""
Грамотное склонение РОДОВЫХ СЛОВ в названиях организаций.

Ядро склонения ФИО (порт VBA 1:1) не затрагивается: этот модуль применяется
ТОЛЬКО к строкам, опознанным как организации (справочник из БД/VBA),
и склоняет лишь начальную группу «прилагательные + определяемое
существительное» (например: «Администрация города» -> род. «Администрации
города», дат. «Администрации города»).

НЕ склоняются (остаются как в источнике):
  - аббревиатуры и сокращения (ООО, АО, СБЕРБАНК, НАО, ...);
  - названия в кавычках («...», "...");
  - часть названия ПОСЛЕ определяемого слова («... с ограниченной
    ответственностью», «... города», «... образования» и т.п.);
  - фамилии/имена в составе названия (Surn/Name/Patr) — во избежание
    искажений («ИП Иванов» -> без изменений, т.к. «ИП» — аббревиатура).

Используется pymorphy3 (морфологический словарь). Если пакет недоступен,
функции возвращают исходный текст без изменений (мягкий откат).
"""

import re

# Сопоставление наших меток падежа с граммемами pymorphy3
_CASE_MAP = {
    "Genitive": "gent",  # родительный: заявители
    "Dative": "datv",    # дательный: ответчики
}

# Токенизация: слова (буквы/цифры/дефис) и разделители (пробелы, пунктуация, кавычки, скобки)
_TOKEN_RE = re.compile(r"([\s,.;:!?«»\"()/\\]+)", re.UNICODE)
# Слово, похожее на аббревиатуру (все буквы заглавные, длина >= 2)
_ABBR_RE = re.compile(r"^[А-ЯЁA-Z]{2,}$", re.UNICODE)

_morph = None


def _get_morph():
    """Ленивая инициализация MorphAnalyzer (одна загрузка словаря)."""
    global _morph
    if _morph is None:
        try:
            from pymorphy3 import MorphAnalyzer
            _morph = MorphAnalyzer()
        except Exception:  # noqa: BLE001 — pymorphy3 недоступен
            _morph = False
    return _morph if _morph else None


def _restore_case(original: str, inflected: str) -> str:
    """Возвращает исходный регистр первой буквы (pymorphy3 даёт строчные)."""
    if original[:1].isupper():
        return inflected[:1].upper() + inflected[1:]
    return inflected


def inflect_organization_name(text: str, case_type: str) -> str:
    """
    Склоняет родовые слова в начале названия организации.

    case_type: "Genitive" (родительный) или "Dative" (дательный).
    Возвращает название с просклонённой начальной группой слов.
    """
    if not text or not text.strip():
        return text or ""
    morph = _get_morph()
    if morph is None:
        return text  # мягкий откат: pymorphy3 не установлен

    target = _CASE_MAP.get(case_type, "gent")
    parts = _TOKEN_RE.split(text)

    declined_zone_done = False   # найден конец склоняемой зоны
    skip_zone = False            # зона отмены (аббревиатура в начале и т.п.)
    adjectives = []              # (индекс, слово, оригинал) прилагательных до определяемого
    head_noun = None             # (индекс, слово, оригинал) определяемого слова
    noun_gender = None
    noun_number = None

    for idx, tok in enumerate(parts):
        if not re.search(r"[А-ЯЁа-яёA-Za-z]", tok):
            continue  # разделитель
        if declined_zone_done:
            break

        # Аббревиатура -> склонять нечего
        if _ABBR_RE.match(tok):
            skip_zone = True
            break

        parses = morph.parse(tok)
        if not parses:
            continue
        p = parses[0]
        grams = set(p.tag.grammemes)

        # Фамилия/имя в составе названия -> дальше не склоняем
        if grams & {"Surn", "Name", "Patr"}:
            skip_zone = True
            break

        if "ADJF" in grams or "PRTF" in grams or "PRTS" in grams:
            # Прилагательное/причастие до определяемого слова
            if head_noun is None:
                adjectives.append((idx, tok, p))
            continue

        if "NOUN" in grams and head_noun is None:
            head_noun = (idx, tok, p)
            noun_gender = "masc" if "masc" in grams else ("femn" if "femn" in grams else ("neut" if "neut" in grams else None))
            noun_number = "sing" if "sing" in grams else ("plur" if "plur" in grams else None)
            declined_zone_done = True
            continue

        # Предлоги/союзы/частицы/прочее до определяемого слова — пропускаем
        continue

    if skip_zone or head_noun is None:
        return text  # склонять нечего

    def inflect_word(p, word_original):
        extra = []
        if noun_gender:
            extra.append(noun_gender)
        if noun_number:
            extra.append(noun_number)
        inflected = p.inflect({target} | set(extra))
        if inflected is None:
            return word_original
        return _restore_case(word_original, inflected.word)

    new_parts = list(parts)
    for idx, tok, p in adjectives:
        new_parts[idx] = inflect_word(p, tok)
    idx, tok, p = head_noun
    new_parts[idx] = inflect_word(p, tok)

    return "".join(new_parts)