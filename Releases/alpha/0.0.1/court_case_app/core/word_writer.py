# -*- coding: utf-8 -*-
"""
Формирование Word-документа акта по шаблону.

Шаблон — .docx с плейсхолдерами {{...}} (см. Plan.md). В таблице акта одна
строка-образец с плейсхолдерами {{номер}}, {{заголовок}}, {{даты}},
{{номер_описи}}, {{номер_ед_хр}}, {{количество}}, {{срок}}, {{примечание}}.
Программа копирует строку-образец под каждое дело (форматирование
сохраняется 1:1), заполняет значения, удаляет образец и заменяет остальные
плейсхолдеры реквизитами.

Решение: в Word-акт выводятся только заполненные записи (пустые строки
пропущенных номеров в документ не попадают).
"""

from copy import deepcopy

from docx import Document
from docx.oxml.ns import qn

# Ключи записей (из case_processor) -> плейсхолдеры строки таблицы
ROW_FIELD_MAP = [
    ("номер", "sequential"),
    ("заголовок", "title"),
    ("даты", "dates"),
    ("номер_описи", "opis"),
    ("номер_ед_хр", "unit"),
    ("количество", "count"),
    ("срок", "retention"),
    ("примечание", "note"),
]
ROW_PLACEHOLDERS = [ph for ph, _ in ROW_FIELD_MAP]

# Общие реквизиты шаблона
COMMON_PLACEHOLDERS = [
    "судебный_участок", "судья", "дата_утверждения", "дата_акта",
    "номер_акта", "итого", "год_дел", "секретарь", "дата_подписи",
    "протокол_эк_дата", "протокол_эк_номер",
]


# ---------------------------------------------------------------------------
# Числа прописью
# ---------------------------------------------------------------------------

_ONES = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь",
         "восемь", "девять", "десять", "одиннадцать", "двенадцать",
         "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать",
         "семнадцать", "восемнадцать", "девятнадцать"]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
         "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот",
             "шестьсот", "семьсот", "восемьсот", "девятьсот"]
# Единицы для тысяч (женский род)
_ONES_FEM = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь",
             "восемь", "девять", "десять", "одиннадцать", "двенадцать",
             "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать",
             "семнадцать", "восемнадцать", "девятнадцать"]


def _plural_word(n: int, one: str, two: str, five: str) -> str:
    n10 = n % 10
    n100 = n % 100
    if 11 <= n100 <= 14:
        return five
    if n10 == 1:
        return one
    if 2 <= n10 <= 4:
        return two
    return five


def _three_digits(n: int, ones_table) -> list:
    parts = []
    h, r = divmod(n, 100)
    if h:
        parts.append(_HUNDREDS[h])
    if r < 20:
        if r:
            parts.append(ones_table[r])
    else:
        t, u = divmod(r, 10)
        parts.append(_TENS[t])
        if u:
            parts.append(ones_table[u])
    return parts


def number_to_words(num: int) -> str:
    """Число прописью (именительный падеж), до миллиардов."""
    if num == 0:
        return "ноль"
    result = []
    billions, rest = divmod(num, 10 ** 9)
    if billions:
        result += _three_digits(billions, _ONES) + [
            _plural_word(billions, "миллиард", "миллиарда", "миллиардов")]
    millions, rest = divmod(rest, 10 ** 6)
    if millions:
        result += _three_digits(millions, _ONES) + [
            _plural_word(millions, "миллион", "миллиона", "миллионов")]
    thousands, rest = divmod(rest, 10 ** 3)
    if thousands:
        result += _three_digits(thousands, _ONES_FEM) + [
            _plural_word(thousands, "тысяча", "тысячи", "тысяч")]
    if rest:
        result += _three_digits(rest, _ONES)
    return " ".join(result)


# ---------------------------------------------------------------------------
# Работа с XML-структурой документа
# ---------------------------------------------------------------------------

def _p_text(p_element) -> str:
    """Полный текст абзаца (w:p) из всех w:t."""
    return "".join(t.text or "" for t in p_element.iter(qn("w:t")))


def _set_p_text(p_element, text: str) -> None:
    """Запись текста абзаца в первый w:t (форматирование сохраняется)."""
    ts = p_element.findall(".//" + qn("w:t"))
    if ts:
        ts[0].text = text
        for t in ts[1:]:
            t.text = ""
    else:
        r = p_element.makeelement(qn("w:r"), {})
        t = p_element.makeelement(qn("w:t"), {})
        t.text = text
        r.append(t)
        p_element.append(r)


def _replace_in_p(p_element, mapping: dict) -> bool:
    """
    Замена плейсхолдеров {{key}} в абзаце. Возвращает True, если менялось.

    fix_03: None -> "" (плейсхолдер без значения превращается в пустую
    строку, а не в литерал «None»).
    """
    full = _p_text(p_element)
    new = full
    for ph, val in mapping.items():
        text = "" if val is None else str(val)
        new = new.replace("{{" + ph + "}}", text)
    if new != full:
        _set_p_text(p_element, new)
        return True
    return False


def _iter_paragraphs(body_element):
    """Генератор (w:p, is_in_table) по прямым потомкам body и ячеек таблиц."""
    for child in body_element.iterchildren():
        if child.tag == qn("w:p"):
            yield child, False
        elif child.tag == qn("w:tbl"):
            # абзацы ячеек таблиц (кроме образца обрабатываются отдельно)
            for tc in child.iter(qn("w:tc")):
                for p in tc.iter(qn("w:p")):
                    yield p, True


def _find_sample_row(table_element):
    """
    Поиск строки-образца в таблице (по плейсхолдерам {{номер}} и {{заголовок}}).
    Возвращает элемент w:tr или None.
    """
    for tr in table_element.iter(qn("w:tr")):
        text = "".join(t.text or "" for t in tr.iter(qn("w:t")))
        if "{{номер}}" in text and "{{заголовок}}" in text:
            return tr
    return None


def _fill_table_row(tr_element, record: dict) -> None:
    """Заполнение строки таблицы значениями записи по плейсхолдерам."""
    mapping = {}
    for ph, key in ROW_FIELD_MAP:
        value = record.get(key)
        mapping[ph] = value if value is not None else ""
    for p in tr_element.iter(qn("w:p")):
        _replace_in_p(p, mapping)


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def write_word_result(records, template_path: str, filepath: str,
                      common_values: dict) -> str:
    """
    Формирование Word-документа по шаблону.

    Параметры:
        records        — список записей (из case_processor);
        template_path  — путь к шаблону .docx;
        filepath       — путь к создаваемому документу;
        common_values  — словарь реквизитов: ключ -> значение
                         (судебный_участок, судья, дата_утверждения,
                         дата_акта, номер_акта, секретарь, дата_подписи,
                         протокол_эк_дата, протокол_эк_номер и др.).

    Возвращает filepath.
    """
    doc = Document(template_path)
    body = doc.element.body

    common = dict(common_values or {})

    # Пустые строки (пропущенные номера) в Word-акт не попадают
    filled_records = [r for r in records if str(r.get("title") or "").strip()]

    # Итоговая строка
    count = len(filled_records)
    # fix_03: если год пришёл как None (ключ есть, значение None) — ""
    year = common.get("год_дел") or ""
    common["итого"] = (f"Итого {count} ({number_to_words(count)}) "
                       f"гражданских дел за")

    # 1. Замена общих реквизитов в абзацах документа (вне таблиц)
    for p, is_table in _iter_paragraphs(body):
        if not is_table:
            _replace_in_p(p, common)

    # 2. Обработка таблиц
    for tbl in body.findall(qn("w:tbl")):
        sample = _find_sample_row(tbl)
        if sample is None:
            # таблица без образца: заменяем общие реквизиты в ячейках
            for tc in tbl.iter(qn("w:tc")):
                for p in tc.iter(qn("w:p")):
                    _replace_in_p(p, common)
            continue

        # Замена общих реквизитов в остальных строках (заголовки и т.п.)
        for tr in tbl.iter(qn("w:tr")):
            if tr is sample:
                continue
            for p in tr.iter(qn("w:p")):
                _replace_in_p(p, common)

        # Копирование строки-образца под каждое дело
        last = sample
        for record in filled_records:
            new_tr = deepcopy(sample)
            last.addnext(new_tr)
            _fill_table_row(new_tr, record)
            last = new_tr

        # Удаление образца
        sample.getparent().remove(sample)

    doc.save(filepath)
    return filepath