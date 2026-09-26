# -*- coding: utf-8 -*-
"""
Парсер Word-акта (АКТ уничтожения гражданских дел).

Использование:
    result = read_act_docx(path)
    # result = {
    #     "records":    [ {sequential, title, dates, opis, unit, count,
    #                       retention, note}, ... ],
    #     "attention":  [ {row, reason}, ... ],
    #     "refs":       {"номер": "9", "судья": "...", ...},
    #     "marker":     {"found": True, "version": "V1"},
    #     "table_index": 0,
    # }

Логика (согласована в обсуждении):
    * Таблица дел — с наибольшим числом «Гражданское дело №...» (решение 54).
    * 8 колонок: по позиции + эвристика по содержимому (решение 55).
    * Умная нумерация (решение 10): если № п/п = 1,2,3,... без пропусков —
      сохраняем; иначе переиндексируем и в attention добавляем замечание.
    * Даты (решение 50): если 1-2 даты dd.mm.yyyy — нормализуем в \\n;
      иначе оставляем как есть и добавляем в attention.
    * Строка без номера в заголовке — attention (решение 51).
    * Реквизиты из шапки — только для информации (решение 11).
"""

import re

from .exceptions import NoCasesFound
from .markers import read_word_marker
from .sheets import verify_docx_content

# --- Регулярки ---------------------------------------------------------------

_CASE_TITLE_RE = re.compile(r"Гражданское дело\s+№", re.IGNORECASE)
_CASE_NUM_IN_TITLE_RE = re.compile(r"№\s*(\d+-\d+/\d{4})")
_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_RETENTION_RE = re.compile(r"\b\d+\s*(?:год|года|лет)\b", re.IGNORECASE)

# 8 колонок: role -> подсказки для эвристики по шапке
_COLUMNS = ["sequential", "title", "dates", "opis", "unit",
            "count", "retention", "note"]
_HEADER_HINTS = {
    "sequential": ("№ п/п", "п/п", "№"),
    "title": ("заголовок", "наименование"),
    "dates": ("даты", "дата"),
    "opis": ("№ описи", "описи", "опись"),
    "unit": ("№ ед.хр", "№ ед. хр", "ед.хр", "ед. хр", "единиц"),
    "count": ("кол-во", "количество"),
    "retention": ("срок хранения", "срок"),
    "note": ("примечание",),
}


def _norm(v) -> str:
    if v is None:
        return ""
    return " ".join(str(v).strip().lower().split())


def normalize_cell_text(text: str) -> str:
    """
    Нормализует артефакты Word в тексте ячейки (fix_10_v2).

    Использует общий sanitize_text — единая логика для всех границ.
    """
    from ..text_utils import sanitize_text
    return sanitize_text(text)


def _cell_text(cell) -> str:
    """
    Текст ячейки с сохранением переносов строк.

    fix_10: нормализуем _x000D_/\r/\v — иначе дата в старой акте
    читается как «08.12.2017_x000D_08.01.2018».
    """
    if cell is None:
        return ""
    try:
        raw = cell.text or ""
    except Exception:  # noqa: BLE001
        return ""
    return normalize_cell_text(raw)


# ---------------------------------------------------------------------------
# Определение таблицы дел
# ---------------------------------------------------------------------------

def _count_cases_in_table(table) -> int:
    """Сколько ячеек таблицы содержат «Гражданское дело №...»."""
    count = 0
    for row in table.rows:
        for cell in row.cells:
            if _CASE_TITLE_RE.search(_cell_text(cell)):
                count += 1
    return count


def find_cases_table(doc):
    """
    Возвращает (table, index) — таблицу с максимальным числом дел.
    Бросает NoCasesFound, если ни в одной таблице нет «Гражданское дело №...».
    """
    best = None
    best_idx = -1
    best_count = 0
    for idx, t in enumerate(doc.tables):
        c = _count_cases_in_table(t)
        if c > best_count:
            best, best_idx, best_count = t, idx, c
    if best is None or best_count == 0:
        raise NoCasesFound(
            "В документе не найдено ни одной строки «Гражданское дело №...».")
    return best, best_idx


# ---------------------------------------------------------------------------
# Определение колонок
# ---------------------------------------------------------------------------

def _detect_columns(table) -> dict:
    """
    Определяет role -> индекс столбца (0-based) по шапке таблицы + эвристике
    по содержимому.

    Эвристика: для каждого столбца из первых 20 строк собираем содержимое,
    ищем «Гражданское дело №» (title), «N год ... Ст.» (retention).

    Возвращает dict role -> col_index; обязательные — sequential и title.
    """
    if not table.rows:
        return {}

    header_cells = table.rows[0].cells
    header = [_norm(_cell_text(c)) for c in header_cells]
    mapping = {}

    # Шаг 1: по шапке
    for idx, h in enumerate(header):
        if not h:
            continue
        for role, hints in _HEADER_HINTS.items():
            if role in mapping:
                continue
            for hint in hints:
                nh = _norm(hint)
                if h == nh or h.startswith(nh):
                    mapping[role] = idx
                    break
            if role in mapping:
                break

    # Шаг 2: по содержимому (title, retention), если не нашли
    if "title" not in mapping or "retention" not in mapping:
        ncols = max((len(r.cells) for r in table.rows), default=0)
        for col_idx in range(ncols):
            joined_parts = []
            for r in table.rows[:20]:
                if col_idx < len(r.cells):
                    joined_parts.append(_cell_text(r.cells[col_idx]))
            joined = " ".join(joined_parts)
            if "title" not in mapping and _CASE_TITLE_RE.search(joined):
                mapping["title"] = col_idx
            if "retention" not in mapping and _RETENTION_RE.search(joined):
                mapping["retention"] = col_idx

    # Разумные дефолты по позиции
    if "sequential" not in mapping:
        mapping["sequential"] = 0
    if "title" not in mapping:
        # Может, это таблица без номера? Никакого title — не имеет смысла
        return mapping  # отсутствие title = error выше
    return mapping


# ---------------------------------------------------------------------------
# Умная нумерация и даты
# ---------------------------------------------------------------------------

def _looks_like_valid_sequence(values) -> bool:
    """True, если последовательность — 1, 2, 3, ..., N без пропусков."""
    nums = []
    for v in values:
        s = str(v or "").strip()
        if not s:
            continue
        if not s.isdigit():
            return False
        nums.append(int(s))
    if not nums:
        return False
    return nums == list(range(1, len(nums) + 1))


def _normalize_dates(text: str) -> tuple:
    """
    Возвращает (нормализованный_текст, was_valid, comment_or_empty).

    Если в тексте 1-2 даты dd.mm.yyyy — нормализуем в \\n-разделённые.
    Иначе — возвращаем как есть и добавляем комментарий в attention.
    """
    if not text:
        return "", True, ""
    found = _DATE_RE.findall(text)
    if not (1 <= len(found) <= 2):
        return text, False, "не удалось распознать даты"
    parts = [f"{d.zfill(2)}.{m.zfill(2)}.{y}" for d, m, y in found]
    if len(parts) == 2 and parts[0] == parts[1]:
        parts = parts[:1]
    return "\n".join(parts), True, ""


# ---------------------------------------------------------------------------
# Извлечение записей из таблицы
# ---------------------------------------------------------------------------

def extract_table_records(table) -> dict:
    """
    Извлекает записи из таблицы дел.

    Возвращает:
        {
          "records":    [ {sequential, title, dates, opis, unit, count,
                           retention, note}, ... ],
          "attention":  [ {row: int, reason: str}, ... ],
          "mapping":    {role: col_index},
        }

    Бросает NoCasesFound, если в таблице нет ни одной строки с делом.
    """
    mapping = _detect_columns(table)
    if "title" not in mapping:
        raise NoCasesFound(
            "Не удалось определить столбец «Заголовок дела» — ни по шапке, "
            "ни по содержимому.")

    # Собираем «сырые» строки: с 1-й по последнюю, если в ней есть дело
    raw_rows = []
    for r_idx, row in enumerate(table.rows):
        if r_idx == 0 and any(_norm(_cell_text(c)) == _norm(hint)
                              for c in row.cells
                              for hint in ("№ п/п", "заголовок дела")):
            continue
        cells = [_cell_text(c) for c in row.cells]
        joined = " ".join(cells)
        if _CASE_TITLE_RE.search(joined):
            raw_rows.append((r_idx, cells))

    if not raw_rows:
        raise NoCasesFound(
            "В таблице нет ни одной строки с «Гражданское дело №...».")

    # Проверяем последовательность № п/п
    seq_idx = mapping.get("sequential", 0)
    seq_values = [cells[seq_idx] if seq_idx < len(cells) else ""
                  for _, cells in raw_rows]
    seq_ok = _looks_like_valid_sequence(seq_values)

    attention = []
    records = []
    for n, (r_idx, cells) in enumerate(raw_rows, start=1):
        def get(role):
            idx = mapping.get(role)
            if idx is None or idx >= len(cells):
                return ""
            return (cells[idx] or "").strip()

        title = get("title")

        # Номер дела
        m = _CASE_NUM_IN_TITLE_RE.search(title)
        case_num = m.group(1) if m else ""

        # Последовательный
        if seq_ok:
            seq_val = get("sequential") or str(n)
        else:
            seq_val = str(n)

        # Даты
        raw_dates = get("dates")
        norm_dates, dates_ok, dates_note = _normalize_dates(raw_dates)
        if not dates_ok:
            attention.append({
                "row": n, "case_number": case_num or "—",
                "reason": dates_note or "проблема с датами",
            })

        # Проверка номера
        if not case_num:
            attention.append({
                "row": n,
                "case_number": "—",
                "reason": "не найден номер вида «N-N/ГГГГ» в заголовке",
            })

        records.append({
            "sequential": seq_val,
            "title": title,
            "dates": norm_dates,
            "opis": get("opis"),
            "unit": get("unit"),
            "count": get("count"),
            "retention": get("retention"),
            "note": get("note"),
        })

    # Если переиндексировали — одно общее замечание
    if not seq_ok:
        attention.insert(0, {
            "row": 0, "case_number": "—",
            "reason": "нумерация в акте непоследовательная — переиндексировано",
        })

    return {"records": records, "attention": attention, "mapping": mapping}


# ---------------------------------------------------------------------------
# Реквизиты из шапки (только для информации)
# ---------------------------------------------------------------------------

_REFS_PATTERNS = [
    ("номер",         r"Судебный\s+участок\s*№\s*([0-9А-Яа-я\-]+)"),
    ("судья",         r"Мировой\s+судья[:\s]+([^\n,;]+)"),
    ("секретарь",     r"Секретарь[:\s]+([^\n,;]+)"),
    ("номер_акта",    r"№\s*акта[:\s]+([^\n,;]+)"),
    ("протокол_эк_дата", r"Протокол[^\n]*?ЭК[^\n]*?от\s+([^\n,;]+)"),
    ("протокол_эк_номер", r"Протокол[^\n]*?ЭК[^\n]*?№\s*([^\n,;]+)"),
]


def extract_refs_from_doc(doc) -> dict:
    """
    Извлекает реквизиты из шапки документа — только для информации.
    Возвращает dict field -> value (пустой, если не найдено).
    """
    text_parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                text_parts.append(cell.text)
    text = "\n".join(text_parts)

    refs = {}
    for field, pattern in _REFS_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = " ".join(m.group(1).split()).strip(".,; ")
            if val:
                refs[field] = val
    return refs


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------

def read_act_docx(filepath) -> dict:
    """
    Читает Word-акт и извлекает дела, attention, реквизиты, метку.

    Возвращает:
        {
          "records":     [...],
          "attention":   [...],
          "refs":        {...},
          "marker":      {"found": bool, "version": str},
          "table_index": int,
        }

    Бросает BadFileError (битый файл) или NoCasesFound.
    """
    verify_docx_content(filepath)
    from docx import Document
    doc = Document(filepath)

    marker = read_word_marker(filepath)
    table, idx = find_cases_table(doc)
    parsed = extract_table_records(table)
    refs = extract_refs_from_doc(doc)

    return {
        "records": parsed["records"],
        "attention": parsed["attention"],
        "refs": refs,
        "marker": marker,
        "table_index": idx,
    }


# ---------------------------------------------------------------------------
# C2: полный цикл Word -> Excel
# ---------------------------------------------------------------------------

def _restore_gaps(records: list) -> list:
    """
    Восстанавливает пустые строки для пропущенных номеров дел.

    Анализирует номера в заголовках (N-N/YYYY) и вставляет пустые
    записи для пропущенных N внутри диапазона min..max.
    """
    import re as _re
    _case_re = _re.compile(r"№\s*(\d+)-(\d+)/(\d{4})")

    nums = []
    for rec in records:
        m = _case_re.search(str(rec.get("title") or ""))
        if m:
            nums.append(int(m.group(2)))
    if not nums:
        return records

    mn, mx = min(nums), max(nums)
    by_num = {}
    for rec in records:
        m = _case_re.search(str(rec.get("title") or ""))
        if m:
            by_num[int(m.group(2))] = rec

    result = []
    seq = 1
    for n in range(mn, mx + 1):
        if n in by_num:
            r = dict(by_num[n])
            r["sequential"] = seq
            result.append(r)
        else:
            result.append({
                "sequential": seq, "title": "", "dates": "",
                "opis": "", "unit": "", "count": "", "retention": "",
                "note": "",
            })
        seq += 1
    return result


def convert_word_to_xlsx(filepath, output_path,
                         restore_gaps: bool = False,
                         columns=None):
    """
    Полный цикл: Word-акт -> Excel-результат.

    Параметры:
        filepath      — путь к .docx;
        output_path   — путь к создаваемому .xlsx;
        restore_gaps  — восстанавливать пустые строки для пропущенных
                        номеров дел (решение 8, переключатель на UI);
        columns       — список ключей столбцов (None = все 8).

    Возвращает:
        {
          "path":       output_path,
          "records":    [...],
          "attention":  [...],
          "refs":       {...},
          "marker":     {"found": bool, "version": str},
          "count":      <число строк с заголовком>,
        }
    """
    import os as _os

    parsed = read_act_docx(filepath)
    records = parsed["records"]

    if restore_gaps:
        records = _restore_gaps(records)

    from core.excel_writer import write_excel_result, DEFAULT_KEYS
    cols = columns if columns else DEFAULT_KEYS

    out_dir = _os.path.dirname(_os.path.abspath(output_path)) or "."
    _os.makedirs(out_dir, exist_ok=True)
    write_excel_result(records, output_path, columns=cols)

    count = sum(1 for r in records if str(r.get("title") or "").strip())
    return {
        "path": output_path,
        "records": records,
        "attention": parsed["attention"],
        "refs": parsed["refs"],
        "marker": parsed["marker"],
        "count": count,
    }
