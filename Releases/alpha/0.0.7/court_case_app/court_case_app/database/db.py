# -*- coding: utf-8 -*-
"""
База данных приложения (SQLite), схема v2.

Иерархия (сначала участки и годы; дела и файлы — в следующих под-этапах):

    court_areas (судебные участки: номер + name/address/note)
      └─ court_years (реквизиты года: судья, секретарь, даты акта, ...)

Справочники (не пересекаются с базой дел):
    organizations       — организации (первое слово + тип подачи);
    retention_rules     — правила сроков хранения;
    case_categories     — «истец → категория» (глобальные записи).

Служебные:
    settings            — ключ-значение: auto_fix_categories,
                          category_snapshot_limit, schema_version.
"""

import sqlite3

from core.retention import (
    DEFAULT_KEYWORDS,
    DEFAULT_RETENTION_TEXT,
)

SCHEMA_VERSION = "v2"

# Начальный список организаций (первое слово -> тип подачи)
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

# Служебные настройки (после v2; реквизитные ключи удалены)
DEFAULT_SETTINGS = {
    "auto_fix_categories": "1",
    "category_snapshot_limit": "5",
    # schema_version устанавливается _init_schema_version
}

# Реквизитные поля года (9 штук, как было у court_areas в v1)
_COURT_YEAR_FIELDS = (
    "судья", "секретарь", "дата_утверждения", "дата_акта", "номер_акта",
    "дата_подписи", "протокол_эк_дата", "протокол_эк_номер",
)


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

-- stage16a: судебные участки (v2: номер + атрибуты).
CREATE TABLE IF NOT EXISTS court_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    номер TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- stage16a: реквизиты года (судья, секретарь, даты акта, ...).
CREATE TABLE IF NOT EXISTS court_years (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    court_area_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    судья TEXT NOT NULL DEFAULT '',
    секретарь TEXT NOT NULL DEFAULT '',
    дата_утверждения TEXT NOT NULL DEFAULT '',
    дата_акта TEXT NOT NULL DEFAULT '',
    номер_акта TEXT NOT NULL DEFAULT '',
    дата_подписи TEXT NOT NULL DEFAULT '',
    протокол_эк_дата TEXT NOT NULL DEFAULT '',
    протокол_эк_номер TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    is_incomplete INTEGER NOT NULL DEFAULT 0,
    is_closed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(court_area_id, year),
    FOREIGN KEY (court_area_id) REFERENCES court_areas(id) ON DELETE CASCADE
);
"""


# ---------------------------------------------------------------------------
# Соединение и инициализация
# ---------------------------------------------------------------------------

def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _detect_schema_version(conn) -> str:
    """
    Определяет версию схемы: 'empty', 'v1', 'v2'.
    """
    has_settings = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
    ).fetchone()
    if not has_settings:
        return "empty"
    row = conn.execute(
        "SELECT value FROM settings WHERE key='schema_version'"
    ).fetchone()
    if row and row[0]:
        return str(row[0])
    # Версия не записана: смотрим, есть ли court_years
    has_years = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='court_years'"
    ).fetchone()
    return "v2" if has_years else "v1"


def get_schema_version(conn) -> str:
    return _detect_schema_version(conn)


def _init_schema_version(conn) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,))
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
    """
    Создание схемы, начальное наполнение; возвращает соединение.

    Для схемы v1 (старой) — выбрасывает RuntimeError: нужна миграция.
    Для пустой БД — создаёт v2 и сразу ставит schema_version='v2'.
    Для v2 — просто открывает.
    """
    conn = connect(db_path)
    version = _detect_schema_version(conn)

    if version == "v1":
        conn.close()
        raise RuntimeError(
            "Схема БД устарела (v1). Требуется миграция. "
            "Запустите: .venv\\Scripts\\python.exe migrate_db_v2.py"
        )

    conn.executescript(_SCHEMA)
    _seed(conn)

    if version == "empty":
        _init_schema_version(conn)

    return conn


# ---------------------------------------------------------------------------
# Организации
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
    return {name: claim_type for _, name, claim_type in
            conn.execute("SELECT id, name, claim_type FROM organizations")}


def organization_names(conn) -> list:
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


def add_retention_rule(conn, keyword: str, code: str, result_text=None) -> int:
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
# case_categories (без изменений; court_area_id добавится в D1a2/D1b)
# ---------------------------------------------------------------------------

def list_case_categories(conn) -> list:
    cur = conn.execute(
        "SELECT id, plaintiff_key, plaintiff_label, category, is_organization "
        "FROM case_categories ORDER BY plaintiff_key, category")
    return [{"id": r[0], "plaintiff_key": r[1], "plaintiff_label": r[2],
             "category": r[3], "is_organization": r[4]} for r in cur.fetchall()]


def add_case_category(conn, plaintiff_key: str, plaintiff_label: str,
                      category: str, is_organization: bool = False) -> int:
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
    result = {}
    for r in conn.execute(
            "SELECT plaintiff_key, category FROM case_categories"):
        result.setdefault(r[0], []).append(r[1])
    return result


def case_categories_labels(conn) -> dict:
    result = {}
    for key, label in conn.execute(
            "SELECT plaintiff_key, plaintiff_label FROM case_categories"):
        if key not in result:
            result[key] = label
    return result


# ---------------------------------------------------------------------------
# Судебные участки (v2)
# ---------------------------------------------------------------------------

def list_court_areas(conn) -> list:
    cur = conn.execute(
        "SELECT id, номер, name, address, note, created_at "
        "FROM court_areas ORDER BY CAST(номер AS INTEGER), номер")
    return [{"id": r[0], "номер": r[1], "name": r[2],
             "address": r[3], "note": r[4], "created_at": r[5]}
            for r in cur.fetchall()]


def get_court_area(conn, area_id: int):
    for rec in list_court_areas(conn):
        if rec["id"] == area_id:
            return rec
    return None


def court_area_for_number(conn, номер: str):
    if not номер:
        return None
    s = str(номер).strip()
    for rec in list_court_areas(conn):
        if rec["номер"] == s:
            return rec
    return None


def add_court_area(conn, data: dict) -> int:
    """data: {номер, name, address, note}."""
    номер = (data.get("номер") or "").strip()
    if not номер:
        raise ValueError("Номер участка не может быть пустым")
    conn.execute(
        "INSERT INTO court_areas (номер, name, address, note) "
        "VALUES (?, ?, ?, ?)",
        (номер,
         (data.get("name") or "").strip(),
         (data.get("address") or "").strip(),
         (data.get("note") or "").strip()))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_court_area(conn, area_id: int, data: dict) -> None:
    номер = (data.get("номер") or "").strip()
    if not номер:
        raise ValueError("Номер участка не может быть пустым")
    conn.execute(
        "UPDATE court_areas SET номер = ?, name = ?, address = ?, note = ? "
        "WHERE id = ?",
        (номер,
         (data.get("name") or "").strip(),
         (data.get("address") or "").strip(),
         (data.get("note") or "").strip(),
         area_id))
    conn.commit()


def delete_court_area(conn, area_id: int) -> None:
    conn.execute("DELETE FROM court_areas WHERE id = ?", (area_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Годы участка
# ---------------------------------------------------------------------------

def _is_incomplete(data: dict) -> int:
    for field in _COURT_YEAR_FIELDS:
        val = data.get(field)
        if val is None or not str(val).strip():
            return 1
    return 0


def _year_row_to_dict(r) -> dict:
    return {
        "id": r[0], "court_area_id": r[1], "year": r[2],
        "судья": r[3], "секретарь": r[4],
        "дата_утверждения": r[5], "дата_акта": r[6], "номер_акта": r[7],
        "дата_подписи": r[8],
        "протокол_эк_дата": r[9], "протокол_эк_номер": r[10],
        "note": r[11], "is_incomplete": bool(r[12]), "is_closed": bool(r[13]),
        "created_at": r[14], "updated_at": r[15],
    }


_YEAR_COLS = (
    "id, court_area_id, year, судья, секретарь, "
    "дата_утверждения, дата_акта, номер_акта, дата_подписи, "
    "протокол_эк_дата, протокол_эк_номер, note, is_incomplete, is_closed, "
    "created_at, updated_at"
)


def list_court_years(conn, court_area_id: int = None) -> list:
    if court_area_id is None:
        cur = conn.execute(
            f"SELECT {_YEAR_COLS} FROM court_years ORDER BY court_area_id, year")
    else:
        cur = conn.execute(
            f"SELECT {_YEAR_COLS} FROM court_years WHERE court_area_id = ? "
            "ORDER BY year",
            (court_area_id,))
    return [_year_row_to_dict(r) for r in cur.fetchall()]


def get_court_year(conn, year_id: int):
    r = conn.execute(
        f"SELECT {_YEAR_COLS} FROM court_years WHERE id = ?",
        (year_id,)).fetchone()
    return _year_row_to_dict(r) if r else None


def court_year_for(conn, court_area_id: int, year: int):
    r = conn.execute(
        f"SELECT {_YEAR_COLS} FROM court_years "
        "WHERE court_area_id = ? AND year = ?",
        (court_area_id, year)).fetchone()
    return _year_row_to_dict(r) if r else None


def add_court_year(conn, court_area_id: int, year: int, data: dict) -> int:
    values = [(data.get(f) or "").strip() for f in _COURT_YEAR_FIELDS]
    conn.execute(
        "INSERT INTO court_years (court_area_id, year, "
        "судья, секретарь, дата_утверждения, дата_акта, номер_акта, "
        "дата_подписи, протокол_эк_дата, протокол_эк_номер, "
        "note, is_incomplete, is_closed) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (court_area_id, int(year), *values,
         (data.get("note") or "").strip(),
         _is_incomplete(dict(zip(_COURT_YEAR_FIELDS, values))),
         1 if data.get("is_closed") else 0))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def update_court_year(conn, year_id: int, data: dict) -> None:
    values = [(data.get(f) or "").strip() for f in _COURT_YEAR_FIELDS]
    conn.execute(
        "UPDATE court_years SET "
        "судья = ?, секретарь = ?, дата_утверждения = ?, дата_акта = ?, "
        "номер_акта = ?, дата_подписи = ?, "
        "протокол_эк_дата = ?, протокол_эк_номер = ?, "
        "note = ?, is_incomplete = ?, is_closed = ?, "
        "updated_at = datetime('now') "
        "WHERE id = ?",
        (*values,
         (data.get("note") or "").strip(),
         _is_incomplete(dict(zip(_COURT_YEAR_FIELDS, values))),
         1 if data.get("is_closed") else 0,
         year_id))
    conn.commit()


def delete_court_year(conn, year_id: int) -> None:
    conn.execute("DELETE FROM court_years WHERE id = ?", (year_id,))
    conn.commit()


def court_area_settings_dict(conn, area_id: int, year=None) -> dict:
    """
    Словарь реквизитов для word_writer: плейсхолдер -> значение.

    Если year не указан — берётся последний (по убыванию year) год участка.
    Возвращает {} если участка или года нет.
    """
    area = get_court_area(conn, area_id)
    if not area:
        return {}

    if year is None:
        row = conn.execute(
            "SELECT id FROM court_years WHERE court_area_id = ? "
            "ORDER BY year DESC LIMIT 1",
            (area_id,)).fetchone()
        if not row:
            return {}
        rec = get_court_year(conn, row[0])
    else:
        rec = court_year_for(conn, area_id, int(year))

    if not rec:
        return {}

    return {
        "судебный_участок": area["номер"],
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
# Импорт/экспорт БД в Excel (без изменений)
# ---------------------------------------------------------------------------

def import_database_from_excel(conn, filepath: str) -> int:
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
    from openpyxl import Workbook
    wb = Workbook()

    ws = wb.active
    ws.title = "База данных"
    for name, claim_type in sorted(organizations_dict(conn).items()):
        ws.append([name, claim_type])

    ws2 = wb.create_sheet("Правила сроков")
    ws2.append(["Корень", "Код", "Результат"])
    for rule in list_retention_rules(conn):
        ws2.append([rule["keyword"], rule["code"], rule["result_text"] or ""])

    ws3 = wb.create_sheet("Настройки")
    ws3.append(["Ключ", "Значение"])
    for key, value in get_settings(conn).items():
        ws3.append([key, value])

    ws4 = wb.create_sheet("Категории дел")
    ws4.append(["Истец", "Ключ", "Категория", "Организация"])
    for rec in list_case_categories(conn):
        ws4.append([rec["plaintiff_label"], rec["plaintiff_key"],
                    rec["category"], "да" if rec["is_organization"] else "нет"])

    ws5 = wb.create_sheet("Судебные участки")
    ws5.append(["Номер", "Name", "Address", "Note"])
    for area in list_court_areas(conn):
        ws5.append([area["номер"], area["name"], area["address"], area["note"]])

    ws6 = wb.create_sheet("Годы участков")
    ws6.append(["Номер участка", "Год", "Судья", "Секретарь", "№ акта",
                "Дата акта", "Дата утверждения", "Дата подписи",
                "Протокол ЭК дата", "Протокол ЭК номер", "Note",
                "IsClosed"])
    for y in list_court_years(conn):
        area = get_court_area(conn, y["court_area_id"])
        ws6.append([
            area["номер"] if area else "?",
            y["year"], y["судья"], y["секретарь"], y["номер_акта"],
            y["дата_акта"], y["дата_утверждения"], y["дата_подписи"],
            y["протокол_эк_дата"], y["протокол_эк_номер"], y["note"],
            "да" if y["is_closed"] else "нет",
        ])

    wb.save(filepath)
    return filepath
