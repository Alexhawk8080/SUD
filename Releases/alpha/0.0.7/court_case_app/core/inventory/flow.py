# -*- coding: utf-8 -*-
"""
Сборка единого потока из нескольких docx-описей (этап 14c, решения 14–18).

Пользователь может загрузить несколько docx. Файлы склеиваются в один поток:
порядок определяется СТЫКОВКОЙ «конец → начало», а не по алфавиту.

Ошибки:
    - разрыв: конец A → начало B не стыкуется;
    - пересечение (дубликаты номеров между файлами);
    - смешение административных и гражданских дел.

Один файл — тривиальный случай.
"""

from .case_number import build_from_rows, resolve_chosen_list
from .exceptions import FlowBreakError, MixedTypesError
from .normalizer import CASE_ADMIN, CASE_CIVIL, detect_case_type


def doc_numbers(doc) -> list:
    """Выбранные номера одного документа (по порядку)."""
    resolved = resolve_chosen_list(doc.get("rows", []))
    return [r["chosen"] for r in resolved if r["chosen"]]


def doc_range(doc):
    """(первый номер, последний номер) документа; числа или (None, None)."""
    nums = doc_numbers(doc)
    if not nums:
        return None, None
    return nums[0]["number"], nums[-1]["number"]


def doc_case_type(doc) -> str:
    """
    Тип дел документа (CASE_CIVIL / CASE_ADMIN / "").

    Определяется голосованием по «Наименованию» строк (решение 17).
    При явном смешении типов в одном файле — MixedTypesError.
    """
    civil = admin = 0
    for row in doc.get("rows", []):
        t = detect_case_type(row.get("name"))
        if t == CASE_CIVIL:
            civil += 1
        elif t == CASE_ADMIN:
            admin += 1
    total = civil + admin
    if total == 0:
        return ""
    if civil and admin and min(civil, admin) / total >= 0.10:
        raise MixedTypesError(
            f"В файле «{doc.get('file', '?')}» смешаны административные "
            f"({admin}) и гражданские ({civil}) дела.")
    return CASE_ADMIN if admin > civil else CASE_CIVIL


def stitch_docs(docs) -> list:
    """
    Упорядочивает документы по стыковке «конец → начало» (решение 15).

    Бросает FlowBreakError при разрыве или пересечении с диагностикой.
    Один файл возвращается как есть.
    """
    if not docs:
        return []
    if len(docs) == 1:
        return list(docs)

    infos = []
    for doc in docs:
        start, end = doc_range(doc)
        infos.append({"doc": doc, "start": start, "end": end})

    with_nums = [i for i in infos if i["start"] is not None]
    without = [i for i in infos if i["start"] is None]
    with_nums.sort(key=lambda i: i["start"])

    ordered = []
    for idx in range(1, len(with_nums)):
        prev, cur = with_nums[idx - 1], with_nums[idx]
        if cur["start"] < prev["end"]:
            raise FlowBreakError(
                f"Пересечение: «{cur['doc'].get('file')}» начинается с "
                f"№{cur['start']}, а «{prev['doc'].get('file')}» уже "
                f"заканчивается №{prev['end']}.")
        if cur["start"] > prev["end"] + 1:
            raise FlowBreakError(
                f"Разрыв потока: «{prev['doc'].get('file')}» заканчивается "
                f"№{prev['end']}, а «{cur['doc'].get('file')}» начинается "
                f"с №{cur['start']}.")

    ordered.extend(i["doc"] for i in with_nums)
    ordered.extend(i["doc"] for i in without)
    return ordered


def combine_type(docs) -> str:
    """Единый тип потока; MixedTypesError при смешении файлов (решение 15)."""
    types = {doc_case_type(d) for d in docs}
    types.discard("")
    if CASE_CIVIL in types and CASE_ADMIN in types:
        raise MixedTypesError(
            "В одном потоке смешаны административные и гражданские дела.")
    if CASE_ADMIN in types:
        return CASE_ADMIN
    if CASE_CIVIL in types:
        return CASE_CIVIL
    return ""


def build_flow(docs, flow_year=None) -> dict:
    """
    Собирает единый поток из нескольких docx-описей (решения 14–18).

    docs — список результатов read_inventory_docx (ключи file, rows, ...).

    Возвращает:
        {"files":     [имена файлов в порядке потока],
         "type":      CASE_CIVIL / CASE_ADMIN / "",
         "rows":      склеенные строки в порядке потока,
         "stream":    результат build_from_rows,
         "f4":        база F4,
         "year":      год потока,
         "attention": суммарный attention}
    """
    ordered = stitch_docs(docs)
    flow_type = combine_type(ordered)

    rows = []
    attention = []
    for doc in ordered:
        rows.extend(doc.get("rows", []))
        attention.extend(doc.get("attention", []))

    stream = build_from_rows(rows, flow_year=flow_year)
    return {
        "files": [d.get("file", "?") for d in ordered],
        "type": flow_type,
        "rows": rows,
        "stream": stream,
        "f4": stream.get("f4"),
        "year": stream.get("year"),
        "attention": attention,
    }
