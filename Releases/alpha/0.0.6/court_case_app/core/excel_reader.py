# -*- coding: utf-8 -*-
"""
Чтение исходной таблицы гражданских дел из Excel (.xlsx).

Автоопределение ролей столбцов по заголовкам первой строки.
При несовпадении — ручной маппинг: роль -> индекс столбца (1-based),
который пользователь задаёт через интерфейс.

Соответствие ролей колонкам VBA-макроса (индексы 1-based):
    date (B), case_number (C), applicants (D), respondents (E),
    category (F), opis_number (G), unit_number (H), note (J),
    end_date (N = B+11).
"""

from openpyxl import load_workbook

# Роли столбцов исходной таблицы
ROLES = [
    "date",            # дата начала
    "case_number",     # номер дела
    "applicants",      # заявители
    "respondents",     # ответчики
    "category",        # категория дела
    "opis_number",     # номер описи
    "unit_number",     # номер ед.хр.
    "note",            # примечание
    "end_date",        # дата окончания (B+11 в VBA)
]

ROLE_TITLES = {
    "date": "Дата",
    "case_number": "№ дела",
    "applicants": "Заявители",
    "respondents": "Ответчики",
    "category": "Категория дела",
    "opis_number": "№ описи",
    "unit_number": "№ ед.хр.",
    "note": "Примечание",
    "end_date": "Дата окончания",
}

# Варианты заголовков для автоопределения (нижний регистр, без пробелов по краям)
HEADER_ALIASES = {
    "date": ["дата", "дата начала", "дата поступления", "дата подачи"],
    "case_number": ["номер дела", "№ дела", "номер", "№", "номер дела (префикс-nnn/гггг)"],
    "applicants": ["заявители", "заявитель", "истцы", "истец", "фамилия истца"],
    "respondents": ["ответчики", "ответчик", "фамилия ответчика"],
    "category": ["категория", "категория дела", "суть спора", "предмет спора"],
    "opis_number": ["номер описи", "№ описи", "описи", "номер описи дела"],
    "unit_number": ["номер ед.хр.", "№ ед.хр.", "номер единицы хранения", "ед.хр."],
    "note": ["примечание", "примечания", "комментарий"],
    "end_date": ["дата окончания", "дата окончания дела", "дата окончания производства",
                 "окончание производства", "окончание"],
}


class MappingError(Exception):
    """Ошибка маппинга столбцов: роль не найдена."""


class SourceRow:
    """Строка исходной таблицы: значения доступны по ролям (None для пустых)."""

    def __init__(self, data: dict):
        self._data = data

    def get(self, role: str):
        return self._data.get(role)

    @property
    def data(self) -> dict:
        return dict(self._data)


def _normalize_header(value) -> str:
    """
    Нормализация заголовка: строка, нижний регистр, схлопнутые пробелы,
    удаление дефисов (Word переносит длинные слова через «-»).
    """
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    return text.lower().replace("-", "")


def detect_header_row(rows) -> int:
    """
    Автоопределение номера строки с заголовками (1-based).

    Перебирает первые строки листа и возвращает индекс строки, где
    распознано максимальное число ролей столбцов. Если ни одна строка
    не дала совпадений — возвращает 1.
    """
    best_row = 1
    best_score = 0
    for idx, row in enumerate(rows[:20], start=1):
        mapping = auto_detect_roles(row)
        score = len(mapping)
        if score > best_score:
            best_score = score
            best_row = idx
    return best_row


def auto_detect_roles(headers) -> dict:
    """
    Автоопределение ролей по заголовкам первой строки.

    Возвращает словарь role -> индекс столбца (1-based).
    Роль, для которой не найден столбец, отсутствует в результате.

    Алгоритм двухпроходный (fix_01):
      1) точные совпадения заголовка с алиасом (h == alias);
      2) совпадение по началу строки (h.startswith(alias)) — только для
         ещё не назначенных ролей и не занятых столбцов.
    Внутри каждого прохода кандидаты сортируются по убыванию длины
    совпавшего алиаса, чтобы «Номер описи» не определялся как
    case_number (алиас «номер»), а «Дата окончания» — как date
    (алиас «дата»). Один столбец назначается не более одной роли.
    """
    mapping = {}
    used_cols = set()

    def _assign(candidates):
        # candidates: список (alias_len, role, col_idx)
        # Сортировка: длина алиаса — по убыванию, индекс — по возрастанию
        candidates.sort(key=lambda c: (-c[0], c[2]))
        for _ln, role, idx in candidates:
            if role in mapping or idx in used_cols:
                continue
            mapping[role] = idx
            used_cols.add(idx)

    # 1-й проход: точные совпадения
    exact = []
    for idx, header in enumerate(headers, start=1):
        h = _normalize_header(header)
        if not h:
            continue
        for role, aliases in HEADER_ALIASES.items():
            for alias in aliases:
                if h == alias:
                    exact.append((len(alias), role, idx))
    _assign(exact)

    # 2-й проход: по началу строки (для оставшихся ролей и столбцов)
    prefix = []
    for idx, header in enumerate(headers, start=1):
        if idx in used_cols:
            continue
        h = _normalize_header(header)
        if not h:
            continue
        for role, aliases in HEADER_ALIASES.items():
            if role in mapping:
                continue
            for alias in aliases:
                if h.startswith(alias):
                    prefix.append((len(alias), role, idx))
    _assign(prefix)

    return mapping


def read_source_table(filepath: str, mapping=None, sheet_name: str = None,
                      header_row: int = 1):
    """
    Чтение исходной таблицы.

    Параметры:
        filepath    — путь к .xlsx файлу;
        mapping     — ручной маппинг role -> индекс столбца (1-based).
                      Если None — используется автоопределение по заголовкам;
        sheet_name  — имя листа (по умолчанию первый активный);
        header_row  — номер строки с заголовками (1-based, по умолчанию 1).
                      0 = заголовков нет, данные читаются с первой строки.

    Возвращает кортеж (headers, rows, used_mapping):
        headers      — список заголовков строки header_row ([] при 0);
        rows         — список SourceRow (данные со следующей строки);
        used_mapping — словарь role -> индекс столбца.
    """
    wb = load_workbook(filepath, data_only=True, read_only=True)
    try:
        ws = wb[sheet_name] if sheet_name else wb.active
        all_rows = list(ws.iter_rows(values_only=True))

        if header_row is None:
            header_row = detect_header_row(all_rows)

        headers = []
        if header_row > 0 and header_row <= len(all_rows):
            headers = list(all_rows[header_row - 1])

        if mapping is None:
            mapping = auto_detect_roles(headers)

        rows = []
        start = header_row if header_row > 0 else 0
        for values in all_rows[start:]:
            data = {}
            for role, col_idx in mapping.items():
                if 1 <= col_idx <= len(values):
                    data[role] = values[col_idx - 1]
                else:
                    data[role] = None
            rows.append(SourceRow(data))
        return headers, rows, mapping
    finally:
        wb.close()


def get_column_index(headers, role: str) -> int:
    """Возвращает индекс столбца (1-based) для роли по заголовкам (0, если нет)."""
    mapping = auto_detect_roles(headers)
    return mapping.get(role, 0)