# -*- coding: utf-8 -*-
"""
База данных приложения (SQLite).

Таблицы:
    organizations   — организация (первое слово) -> тип подачи
                      («по иску»/«по заявлению»). Наличие записи означает,
                      что название НЕ склоняется (объединено со старым
                      списком слов-исключений);
    retention_rules — правила сроков хранения: корень слова -> код типа,
                      код -> текст результата (порядок важен, как в VBA);
    settings        — ключ -> значение (реквизиты акта и пр.);
    case_categories — словарь «истец -> категория дела» для проверки
                      и автоисправления категорий (Доработка 6):
                      plaintiff_key — нормализованный ключ истца
                      (первое слово для организаций, полное ФИО для
                      физлиц), category — формулировка «о ...»; на одного
                      истца может быть несколько категорий.

Поддержка импорта/экспорта базы в Excel-файл формата
«АКТ уничтожения гражданских дел N.xlsm» (лист «База данных»:
колонка A — первое слово организации, колонка B — тип подачи).
"""

import os
import sqlite3

from core.retention import (
    DEFAULT_KEYWORDS,
    DEFAULT_RETENTION_TEXT,
)

# Начальный список организаций: первое слово -> тип подачи
INITIAL_ORGANIZATIONS = [
    ("ООО", "по иску"),
    ("АО", "по иску"),
    ("ЗАО", "по иску"),
    ("ОАО", "по иску"),
    ("ПАО", "по иску"),
    ("НАО", "по иску"),
    ("ИП", "по иску"),
    ("ГК", "по иску"),
    ("ГСК", "по иску"),
    ("ТСЖ", "по иску"),
    ("УО", "по иску"),
    ("УПФ", "по иску"),
    ("ИФНС", "по иску"),
    ("ПКО", "по иску"),
    ("МФК", "по иску"),
    ("МФО", "по иску"),
    ("КПК", "по иску"),
]

DEFAULT_SETTINGS = {
    "судебный_участок": "3",
    "судья": "О. А. Левошина",
    "дата_утверждения": "«___» ______________ 20__ года",
    "дата_акта": "«__» ____________ 20__ г.",
    "номер_акта": "1",
    "секретарь": "А.М. Намаюшка",
    "дата_подписи": "«__» ____________ 20__ г.",
    "протокол_эк_дата": "«__» ____________ 20__ г.",
    "протокол_эк_номер": "1",
    # Доработка 6: автоисправление категорий из словаря case_categories
    # (включается при обработке; таблица проблемных дел показывается всегда)
    "auto_fix_categories": "1",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    claim_type TEXT NOT NULL DEFAULT 'по иску'
);
CREATE TABLE IF NOT EXISTS retention_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    code TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    result_text TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS case_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plaintiff_key TEXT NOT NULL,
    plaintiff_label TEXT NOT NULL,
    category TEXT NOT NULL,
    is_organization INTEGER NOT NULL DEFAULT 0,
    UNIQUE(plaintiff_key, category)
);
-- stage11a: справочник судебных участков (реквизиты акта на каждый участок).
-- Все 9 полей обязательны при работе через UI; is_incomplete=1 сигнализирует,
-- что запись перенесена из settings с пустыми полями (требует заполнения).
CREATE TABLE IF NOT EXISTS court_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    номер TEXT NOT NULL UNIQUE,
    судья TEXT NOT NULL DEFAULT '',
    дата_утверждения TEXT NOT NULL DEFAULT '',
    дата_акта TEXT NOT NULL DEFAULT '',
    номер_акта TEXT NOT NULL DEFAULT '',
    секретарь TEXT NOT NULL DEFAULT '',
    дата_подписи TEXT NOT NULL DEFAULT '',
    протокол_эк_дата TEXT NOT NULL DEFAULT '',
    протокол_эк_номер TEXT NOT NULL DEFAULT '',
    is_incomplete INTEGER NOT NULL DEFAULT 0
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """Открывает соединение с БД."""
    return sqlite3.connect(db_path)


def _migrate_old_exclusions(conn: sqlite3.Connection) -> None:
    """
    Миграция старой схемы: перенос таблицы exclusions в organizations.
    (Доработка: слова-исключения объединены с организациями.)
    """
    cur = conn.cursor()
    exists = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='exclusions'"
    ).fetchone()
    if not exists:
        return
    rows = cur.execute("SELECT word FROM exclusions").fetchall()
    for (word,) in rows:
        if word and word.strip():
            cur.execute(
                "INSERT OR IGNORE INTO organizations (name, claim_type)"
                " VALUES (?, 'по иску')", (word.strip(),))
    cur.execute("DROP TABLE exclusions")
    conn.commit()


def _seed(conn: sqlite3.Connection) -> None:
    """Начальное наполнение (только для пустых таблиц)."""
    cur = conn.cursor()

    if cur.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 0:
        cur.executemany(
            "INSERT OR IGNORE INTO organizations (name, claim_type) VALUES (?, ?)",
            INITIAL_ORGANIZATIONS)

    if cur.execute("SELECT COUNT(*) FROM retention_rules").fetchone()[0] == 0:
        rows = []
        for idx, (keyword, code) in enumerate(DEFAULT_KEYWORDS):
            rows.append((keyword, code, idx))
        for keyword, code, order in rows:
            result_text = DEFAULT_RETENTION_TEXT.get(code)
            cur.execute(
                "INSERT INTO retention_rules (keyword, code, sort_order, result_text)"
                " VALUES (?, ?, ?, ?)",
                (keyword, code, order, result_text))

    for key, value in DEFAULT_SETTINGS.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value))

    conn.commit()


def init_db(db_path: str) -> sqlite3.Connection:
    """Создание схемы, миграция, начальное наполнение; возвращает соединение."""
    conn = connect(db_path)
    conn.executescript(_SCHEMA)
    _migrate_old_exclusions(conn)
    _seed(conn)
    # stage11a: миграция реквизитов из settings в court_areas (однократно)
    _migrate_settings_to_court_areas(conn)
    return conn


# ---------------------------------------------------------------------------
# stage11a: справочник судебных участков
# ---------------------------------------------------------------------------

# Соответствие field court_areas -> key в settings (для миграции)
_COURT_AREA_FIELDS = (
    "номер", "судья", "дата_утверждения", "дата_акта", "номер_акта",
    "секретарь", "дата_подписи", "протокол_эк_дата", "протокол_эк_номер",
)
# Как поля court_areas называются в settings
_SETTINGS_KEY_FOR_FIELD = {
    "номер": "судебный_участок",
    "судья": "судья",
    "дата_утверждения": "дата_утверждения",
    "дата_акта": "дата_акта",
    "номер_акта": "номер_акта",
    "секретарь": "секретарь",
    "дата_подписи": "дата_подписи",
    "протокол_эк_дата": "протокол_эк_дата",
    "протокол_эк_номер": "протокол_эк_номер",
}


def _is_incomplete(data: dict) -> int:
    """1, если хотя бы одно из 9 полей пустое/None; иначе 0."""
    for field in _COURT_AREA_FIELDS:
        val = data.get(field)
        if val is None or not str(val).strip():
            return 1
    return 0


def _migrate_settings_to_court_areas(conn: sqlite3.Connection) -> None:
    """
    Перенос реквизитов из settings в первую запись court_areas.

    Выполняется однократно: если court_areas непустая — пропускаем.
    Settings НЕ удаляются (двойное чтение, решение 18б).
    Если в settings чего-то не хватает — запись создаётся с is_incomplete=1.
    """
    if conn.execute("SELECT COUNT(*) FROM court_areas").fetchone()[0] > 0:
        return

    settings = {k: v for k, v in conn.execute("SELECT key, value FROM settings")}
    if not settings:
        return  # нет даже дефолтных настроек — миграция не нужна

    data = {}
    for field in _COURT_AREA_FIELDS:
        key = _SETTINGS_KEY_FOR_FIELD[field]
        data[field] = (settings.get(key) or "").strip()

    # Если номер участка пуст — миграция бессмысленна: без номера запись
    # не даст ничего полезного, пусть пользователь заводит вручную.
    if not data["номер"]:
        return

    conn.execute(
        "INSERT INTO court_areas ("
        "номер, судья, дата_утверждения, дата_акта, номер_акта, "
        "секретарь, дата_подписи, протокол_эк_дата, протокол_эк_номер, "
        "is_incomplete) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data["номер"], data["судья"], data["дата_утверждения"],
         data["дата_акта"], data["номер_акта"], data["секретарь"],
         data["дата_подписи"], data["протокол_эк_дата"],
         data["протокол_эк_номер"], _is_incomplete(data)))
    conn.commit()


def list_court_areas(conn) -> list:
    """Все записи справочника, отсортированные по номеру."""
    cur = conn.execute(
        "SELECT id, номер, судья, дата_утверждения, дата_акта, номер_акта, "
        "секретарь, дата_подписи, протокол_эк_дата, протокол_эк_номер, "
        "is_incomplete FROM court_areas ORDER BY CAST(номер AS INTEGER), номер")
    return [{
        "id": r[0], "номер": r[1], "судья": r[2],
        "дата_утверждения": r[3], "дата_акта": r[4], "номер_акта": r[5],
        "секретарь": r[6], "дата_подписи": r[7],
        "протокол_эк_дата": r[8], "протокол_эк_номер": r[9],
        "is_incomplete": bool(r[10]),
    } for r in cur.fetchall()]


def get_court_area(conn, area_id: int):
    """Запись по id, или None."""
    for rec in list_court_areas(conn):
        if rec["id"] == area_id:
            return rec
    return None


def court_area_for_number(conn, номер: str):
    """Запись по номеру участка, или None."""
    if not номер:
        return None
    s = str(номер).strip()
    for rec in list_court_areas(conn):
        if rec["номер"] == s:
            return rec
    return None


def add_court_area(conn, data: dict) -> int:
    """
    Добавление участка. data — dict с 9 полями (номер, судья, ...).
    is_incomplete вычисляется автоматически.
    """
    values = [(data.get(f) or "").strip() for f in _COURT_AREA_FIELDS]
    номер = values[0]
    if not номер:
        raise ValueError("Номер участка не может быть пустым")
    conn.execute(
        "INSERT INTO court_areas ("
        "номер, судья, дата_утверждения, дата_акта, номер_акта, "
        "секретарь, дата_подписи, протокол_эк_дата, протокол_эк_номер, "
        "is_incomplete) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (*values, _is_incomplete(dict(zip(_COURT_AREA_FIELDS, values)))))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_court_area(conn, area_id: int, data: dict) -> None:
    """Обновление участка. Все 9 полей перезаписываются."""
    values = [(data.get(f) or "").strip() for f in _COURT_AREA_FIELDS]
    if not values[0]:
        raise ValueError("Номер участка не может быть пустым")
    conn.execute(
        "UPDATE court_areas SET "
        "номер = ?, судья = ?, дата_утверждения = ?, дата_акта = ?, "
        "номер_акта = ?, секретарь = ?, дата_подписи = ?, "
        "протокол_эк_дата = ?, протокол_эк_номер = ?, is_incomplete = ? "
        "WHERE id = ?",
        (*values,
         _is_incomplete(dict(zip(_COURT_AREA_FIELDS, values))),
         area_id))
    conn.commit()


def delete_court_area(conn, area_id: int) -> None:
    conn.execute("DELETE FROM court_areas WHERE id = ?", (area_id,))
    conn.commit()


def court_area_settings_dict(conn, area_id: int) -> dict:
    """
    Значения для word_writer: плейсхолдер -> значение.

    Соответствует COMMON_PLACEHOLDERS (без итого/год_дел — их добавит pipeline).
    Возвращает пустой dict, если записи нет.
    """
    rec = get_court_area(conn, area_id)
    if not rec:
        return {}
    return {
        "судебный_участок": rec["номер"],
        "судья": rec["судья"],
        "дата_утверждения": rec["дата_утверждения"],
        "дата_акта": rec["дата_акта"],
        "номер_акта": rec["номер_акта"],
        "секретарь": rec["секретарь"],
        "дата_подписи": rec["дата_подписи"],
        "протокол_эк_дата": rec["протокол_эк_дата"],
        "протокол_эк_номер": rec["протокол_эк_номер"],
    }


# ---------------------------------------------------------------------------
# Организации (включая бывшие слова-исключения)
# ---------------------------------------------------------------------------

def list_organizations(conn) -> list:
    cur = conn.execute(
        "SELECT id, name, claim_type FROM organizations ORDER BY name")
    return [{"id": r[0], "name": r[1], "claim_type": r[2]} for r in cur.fetchall()]


def add_organization(conn, name: str, claim_type: str) -> int:
    cur = conn.execute(
        "INSERT INTO organizations (name, claim_type) VALUES (?, ?)",
        (name.strip(), claim_type.strip()))
    conn.commit()
    return cur.lastrowid


def update_organization(conn, org_id: int, name: str, claim_type: str) -> None:
    conn.execute(
        "UPDATE organizations SET name = ?, claim_type = ? WHERE id = ?",
        (name.strip(), claim_type.strip(), org_id))
    conn.commit()


def delete_organization(conn, org_id: int) -> None:
    conn.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
    conn.commit()


def organizations_dict(conn) -> dict:
    """Словарь организация -> тип подачи (для case_processor)."""
    return {name: claim_type for _, name, claim_type in
            conn.execute("SELECT id, name, claim_type FROM organizations")}


def organization_names(conn) -> list:
    """Список названий организаций (первые слова, не склоняются)."""
    return [r[0] for r in conn.execute("SELECT name FROM organizations")]


# ---------------------------------------------------------------------------
# Правила сроков хранения
# ---------------------------------------------------------------------------

def list_retention_rules(conn) -> list:
    cur = conn.execute(
        "SELECT id, keyword, code, sort_order, result_text "
        "FROM retention_rules ORDER BY sort_order, id")
    return [{"id": r[0], "keyword": r[1], "code": r[2],
             "sort_order": r[3], "result_text": r[4]} for r in cur.fetchall()]


def add_retention_rule(conn, keyword: str, code: str,
                       result_text=None) -> int:
    max_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) FROM retention_rules").fetchone()[0]
    cur = conn.execute(
        "INSERT INTO retention_rules (keyword, code, sort_order, result_text)"
        " VALUES (?, ?, ?, ?)",
        (keyword.strip(), code.strip(), max_order + 1,
         result_text.strip() if result_text else None))
    conn.commit()
    return cur.lastrowid


def update_retention_rule(conn, rule_id: int, keyword: str, code: str,
                          result_text=None) -> None:
    conn.execute(
        "UPDATE retention_rules SET keyword = ?, code = ?, result_text = ? "
        "WHERE id = ?",
        (keyword.strip(), code.strip(),
         result_text.strip() if result_text else None, rule_id))
    conn.commit()


def delete_retention_rule(conn, rule_id: int) -> None:
    conn.execute("DELETE FROM retention_rules WHERE id = ?", (rule_id,))
    conn.commit()


def load_retention_rules(conn):
    """
    Загрузка правил для retention.get_retention_info.

    Возвращает (keywords, texts):
        keywords — список кортежей (root, code) в порядке sort_order;
        texts    — словарь code -> текст результата.
    """
    cur = conn.execute(
        "SELECT keyword, code, result_text FROM retention_rules "
        "ORDER BY sort_order, id")
    rows = cur.fetchall()
    keywords = [(r[0], r[1]) for r in rows]
    texts = {}
    for _, code, text in rows:
        if text and code not in texts:
            texts[code] = text
    return keywords, texts


# ---------------------------------------------------------------------------
# Настройки
# ---------------------------------------------------------------------------

def get_settings(conn) -> dict:
    cur = conn.execute("SELECT key, value FROM settings")
    return {k: v for k, v in cur.fetchall()}


def get_setting(conn, key: str, default=None):
    """Значение одной настройки (или default, если ключа нет)."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value))
    conn.commit()


# ---------------------------------------------------------------------------
# Словарь «истец -> категория дела» (Доработка 6)
# ---------------------------------------------------------------------------

def list_case_categories(conn) -> list:
    """Все записи словаря: id, ключ, имя истца, категория, признак организации."""
    cur = conn.execute(
        "SELECT id, plaintiff_key, plaintiff_label, category, is_organization "
        "FROM case_categories ORDER BY plaintiff_key, category")
    return [{"id": r[0], "plaintiff_key": r[1], "plaintiff_label": r[2],
             "category": r[3], "is_organization": r[4]} for r in cur.fetchall()]


def add_case_category(conn, plaintiff_key: str, plaintiff_label: str,
                      category: str, is_organization: bool = False) -> int:
    """
    Добавление пары «истец -> категория». Дубликаты пары (ключ, категория)
    игнорируются. Возвращает id записи (существующей или новой).
    """
    cur = conn.execute(
        "INSERT OR IGNORE INTO case_categories "
        "(plaintiff_key, plaintiff_label, category, is_organization)"
        " VALUES (?, ?, ?, ?)",
        (plaintiff_key.strip(), plaintiff_label.strip(),
         category.strip(), 1 if is_organization else 0))
    if cur.rowcount > 0:
        conn.commit()
        return cur.lastrowid
    row = conn.execute(
        "SELECT id FROM case_categories WHERE plaintiff_key = ? AND category = ?",
        (plaintiff_key.strip(), category.strip())).fetchone()
    return row[0] if row else cur.lastrowid


def update_case_category(conn, cat_id: int, category: str) -> None:
    conn.execute(
        "UPDATE case_categories SET category = ? WHERE id = ?",
        (category.strip(), cat_id))
    conn.commit()


def delete_case_category(conn, cat_id: int) -> None:
    conn.execute("DELETE FROM case_categories WHERE id = ?", (cat_id,))
    conn.commit()


def case_categories_map(conn) -> dict:
    """
    Словарь для автоподстановки: нормализованный ключ истца ->
    список категорий (для определения самой частой / выбора).
    """
    result = {}
    for r in conn.execute(
            "SELECT plaintiff_key, category FROM case_categories"):
        result.setdefault(r[0], []).append(r[1])
    return result


def case_categories_labels(conn) -> dict:
    """Ключ истца -> человекочитаемое имя (для показа в интерфейсе)."""
    result = {}
    for key, label in conn.execute(
            "SELECT plaintiff_key, plaintiff_label FROM case_categories"):
        if key not in result:
            result[key] = label
    return result


# ---------------------------------------------------------------------------
# Импорт/экспорт базы данных в Excel (.xlsx / .xlsm)
# ---------------------------------------------------------------------------

def import_database_from_excel(conn, filepath: str) -> int:
    """
    Импорт организаций из Excel-файла (лист «База данных»).

    Формат (как в файле «АКТ уничтожения гражданских дел 9СУ 2020.xlsm»):
    колонка A — первое слово организации, колонка B — тип подачи.
    Пустые строки пропускаются; существующие записи не перезаписываются.

    Возвращает количество добавленных записей.
    """
    from openpyxl import load_workbook

    wb = load_workbook(filepath, data_only=True, read_only=True)
    try:
        ws = wb["База данных"] if "База данных" in wb.sheetnames else wb.active
        added = 0
        cur = conn.cursor()
        for row in ws.iter_rows(min_col=1, max_col=2, values_only=True):
            name = str(row[0]).strip() if row[0] is not None else ""
            if not name:
                continue
            claim_type = str(row[1]).strip() if len(row) > 1 and row[1] else "по иску"
            cur.execute(
                "INSERT OR IGNORE INTO organizations (name, claim_type)"
                " VALUES (?, ?)", (name, claim_type))
            if cur.rowcount > 0:
                added += 1
        conn.commit()
        return added
    finally:
        wb.close()


def export_database_to_excel(conn, filepath: str) -> str:
    """
    Экспорт базы данных в Excel-файл (.xlsx).

    Листы: «База данных» (организации: A — слово, B — тип),
    «Правила сроков» (корень, код, результат), «Настройки».

    Возвращает filepath.
    """
    from openpyxl import Workbook

    wb = Workbook()

    ws = wb.active
    ws.title = "База данных"
    for name, claim_type in sorted(organizations_dict(conn).items()):
        ws.append([name, claim_type])

    ws2 = wb.create_sheet("Правила сроков")
    ws2.append(["Корень", "Код", "Результат"])
    for rule in list_retention_rules(conn):
        ws2.append([rule["keyword"], rule["code"],
                    rule["result_text"] or ""])

    ws3 = wb.create_sheet("Настройки")
    ws3.append(["Ключ", "Значение"])
    for key, value in get_settings(conn).items():
        ws3.append([key, value])

    ws4 = wb.create_sheet("Категории дел")
    ws4.append(["Истец", "Ключ", "Категория", "Организация"])
    for rec in list_case_categories(conn):
        ws4.append([rec["plaintiff_label"], rec["plaintiff_key"],
                    rec["category"], "да" if rec["is_organization"] else "нет"])

    wb.save(filepath)
    return filepath