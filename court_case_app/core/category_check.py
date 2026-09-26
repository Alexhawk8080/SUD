# -*- coding: utf-8 -*-
"""
Проверка и исправление категорий дел (Доработка 6).

Логика:
    1. Проблемное дело — категория пустая ИЛИ в ней нет формулировки
       «о ...» / «об ...» (нет типовой части «о взыскании...»,
       «О защите прав потребителей» и т.п.).
    2. Истец сопоставляется комбинированно:
         - организация — по первому слову (справочник БД + аббревиатуры
           ООО/АО/ПАО/ЗАО/ИП/МУП/ГУП...);
         - физическое лицо — по нормализованному полному тексту
           (регистр/пробелы/пунктуация не учитываются).
    3. Для проблемного дела ищутся аналоги — дела того же истца с
       корректной категорией; предлагается самая частая категория (мода)
       и выводится список всех вариантов.
    4. Дела без аналогов группируются по истцу (секция «Без аналогов»)
       для ручного заполнения категории.
    5. Словарь БД (case_categories) — дополнительный источник:
       аналоги из текущего файла приоритетнее словаря.
"""

import re

# Аббревиатуры, по которым название распознаётся как организация
# даже если его нет в справочнике БД (Доработка 6).
ORGANIZATION_PREFIXES = (
    "ооо", "ао", "пао", "зао", "нао", "оао", "ип", "гк", "гск",
    "тсж", "уо", "упф", "ифнс", "пко", "мфк", "мфо", "кпк",
    "муп", "гуп",
)

# Убираемая пунктуация при нормализации текста
_PUNCT_RE = re.compile(r"[\s.,;:«»\"'()\-–—/\\!?]+")
# Фраза «о ...» / «об ...»: «о» или «об» в начале строки или после пробела,
# после которого следует пробел (не часть слова: «оборот», «ооо»).
_CATEGORY_PHRASE_RE = re.compile(r"(?:^|\s)(о|об)\s")


def normalize_text(text) -> str:
    """
    Нормализация текста для сравнения: нижний регистр, ё -> е,
    сжатие пробелов, удаление пунктуации.
    """
    if text is None:
        return ""
    t = str(text).lower().replace("ё", "е")
    t = _PUNCT_RE.sub(" ", t)
    return " ".join(t.split())


def has_category_phrase(text) -> bool:
    """
    Есть ли в тексте типовая формулировка «о ...» / «об ...».

    Проверка шире, чем extract_case_type (VBA): ловит и «О ...»
    в начале строки (без пробела перед «О»).
    """
    if not text:
        return False
    return bool(_CATEGORY_PHRASE_RE.search(str(text).lower()))


def is_problematic(category) -> bool:
    """
    Дело проблемное: категория пустая ИЛИ в ней нет «о/об»
    (вариант В по договорённости с пользователем).
    """
    if category is None:
        return True
    if not str(category).strip():
        return True
    return not has_category_phrase(category)


def extract_phrase(text) -> str:
    """
    Извлечение фразы «о ...» из текста категории.

    В отличие от extract_case_type (case_processor) поддерживает и
    «О ...» в начале строки. Возвращает подстроку с оригинальным
    регистром, например «О расторжении брака» или «о взыскании ...».
    """
    if not text:
        return ""
    t = " ".join(str(text).split())
    m = _CATEGORY_PHRASE_RE.search(t.lower())
    if not m:
        return ""
    return t[m.start(1):].strip()


def build_organization_lookup(org_names) -> set:
    """Множество нормализованных названий организаций из справочника БД."""
    return {normalize_text(n) for n in (org_names or []) if n and str(n).strip()}


def get_plaintiff_key(applicants_text, org_lookup: set):
    """
    Ключ истца для сопоставления (комбинированный критерий).

    Возвращает кортеж (key, label, is_organization):
        key  — нормализованный ключ: первое слово для организаций,
               полный текст для физических лиц;
        label — исходное имя истца (для отображения);
        is_organization — True, если истец — организация.
    """
    names = [n.strip() for n in re.split(r"[;,]", str(applicants_text or ""))
             if n and str(n).strip()]
    if not names:
        return "", "", False

    prefixes = {normalize_text(p) for p in ORGANIZATION_PREFIXES}
    for name in names:
        words = name.split()
        first_word = normalize_text(words[0]) if words else ""
        if first_word in org_lookup or first_word in prefixes:
            return first_word, name, True

    # Физическое лицо: ключ — нормализованный полный текст,
    # label — исходный текст заявителей (с сохранением разделителей)
    return (normalize_text(" ".join(names)),
            str(applicants_text).strip(), False)


def most_frequent(values) -> str:
    """
    Самая частая строка из списка (мода). Равные формулировки
    сравниваются по normalize_text; возвращается первый вариант
    с максимальной частотой в оригинальном виде.
    """
    if not values:
        return ""
    counts = {}
    order = []
    for v in values:
        key = normalize_text(v)
        if key not in counts:
            counts[key] = 0
            order.append(key)
        counts[key] += 1
    best_key = max(order, key=lambda k: counts[k])
    for v in values:
        if normalize_text(v) == best_key:
            return v
    return values[0]


def unique_preserve_order(values) -> list:
    """Уникальные строки с сохранением порядка (без учёта регистра/пунктуации)."""
    seen = set()
    result = []
    for v in values:
        key = normalize_text(v)
        if key and key not in seen:
            seen.add(key)
            result.append(v)
    return result


def analyze(rows, org_names, categories_map=None) -> dict:
    """
    Полный анализ списка дел на предмет отсутствия категории.

    Параметры:
        rows            — список строк с методом .get (SourceRow / dict):
                          'case_number', 'applicants', 'category';
        org_names       — список названий организаций из справочника БД;
        categories_map  — словарь из case_categories: ключ истца ->
                          список категорий (для подсказок/автоисправления).

    Возвращает словарь:
        {
          "problematic": [ {
              row_index, case_number, applicants, current_category,
              plaintiff_key, plaintiff_label, is_organization,
              suggested, options, source ("analog"/"dictionary"/None),
              analogs: [ {case_number, category} ]
          } ],
          "groups": [ {   # только дела БЕЗ аналогов в текущем файле
              key, label, is_organization,
              cases: [ {row_index, case_number} ],
              dictionary_options: [...]
          } ],
          "stats": { total, with_analogs, from_dictionary, no_analog, groups }
        }
    """
    categories_map = categories_map or {}
    org_lookup = build_organization_lookup(org_names)

    # Индекс аналогов: ключ истца -> дела с корректной категорией
    analog_index = {}
    for idx, row in enumerate(rows):
        if is_problematic(row.get("category")):
            continue
        key, _label, _org = get_plaintiff_key(row.get("applicants"), org_lookup)
        if not key:
            continue
        phrase = extract_phrase(row.get("category"))
        if not phrase:
            continue
        analog_index.setdefault(key, []).append({
            "row_index": idx,
            "case_number": row.get("case_number"),
            "category": row.get("category"),
            "phrase": phrase,
        })

    problematic = []
    for idx, row in enumerate(rows):
        if not is_problematic(row.get("category")):
            continue
        key, label, is_org = get_plaintiff_key(row.get("applicants"), org_lookup)

        analogs = analog_index.get(key, [])
        analog_phrases = [a["phrase"] for a in analogs]
        dict_cats = categories_map.get(key, [])

        suggested = ""
        source = None
        if analog_phrases:
            suggested = most_frequent(analog_phrases)
            source = "analog"
        elif dict_cats:
            suggested = most_frequent(dict_cats)
            source = "dictionary"

        options = unique_preserve_order(analog_phrases + dict_cats)

        problematic.append({
            "row_index": idx,
            "case_number": row.get("case_number"),
            "applicants": row.get("applicants") or "",
            "current_category": row.get("category") or "",
            "plaintiff_key": key,
            "plaintiff_label": label or (row.get("applicants") or ""),
            "is_organization": is_org,
            "suggested": suggested,
            "options": options,
            "source": source,
            "analogs": analogs[:10],
        })

    # Группы «Без аналогов» (нет ни одного аналога в текущем файле)
    no_analog_items = [p for p in problematic if not analog_index.get(p["plaintiff_key"])]
    groups = {}
    for p in no_analog_items:
        g = groups.setdefault(p["plaintiff_key"], {
            "key": p["plaintiff_key"],
            "label": p["plaintiff_label"],
            "is_organization": p["is_organization"],
            "cases": [],
            "dictionary_options": categories_map.get(p["plaintiff_key"], []),
        })
        g["cases"].append({"row_index": p["row_index"],
                           "case_number": p["case_number"]})
    group_list = list(groups.values())

    stats = {
        "total": len(problematic),
        "with_analogs": sum(1 for p in problematic if p["source"] == "analog"),
        "from_dictionary": sum(1 for p in problematic if p["source"] == "dictionary"),
        "no_analog": len(no_analog_items),
        "groups": len(group_list),
    }
    return {"problematic": problematic, "groups": group_list, "stats": stats}