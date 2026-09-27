# -*- coding: utf-8 -*-
"""
Веб-приложение «Акт уничтожения гражданских дел».

Flask-сервер: главная страница (обработка файлов), страница базы данных,
API для управления БД, скачивание результата, предпросмотр исходного файла.
Автозапуск браузера; остановка сервера при закрытии вкладки интерфейса
(heartbeat + сигнал при закрытии).
"""

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
import os
import re
import threading
import time
import webbrowser

from flask import Flask, abort, jsonify, render_template, request, send_file

from core.pipeline import process_rows, process_upload
from core.excel_reader import (
    ROLES,
    ROLE_TITLES,
    auto_detect_roles,
    detect_header_row,
    read_source_table,
)
from core.excel_writer import DEFAULT_COLUMNS
from core.category_check import analyze
from core.legacy_reader import parse_legacy_file
from core.case_processor import contains_alimony, is_valid_case_number
from core.converter import (
    ConverterError,
    detect_year_from_numbers,
    inspect_sheets,
    make_warning_message,
    read_act_docx,
    read_result_xlsx,
)
from core.converter.xlsx_to_word import convert_xlsx_to_word
from core.inventory.api import register_routes as register_inventory_routes
from database import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# fix_27: логирование в файлы
# ---------------------------------------------------------------------------
_SERVER_LOG = os.path.join(BASE_DIR, "server_errors.log")

_logger = logging.getLogger("court_case_app")
_logger.setLevel(logging.DEBUG)
if not _logger.handlers:
    _handler = RotatingFileHandler(
        _SERVER_LOG, maxBytes=2 * 1024 * 1024, backupCount=3,
        encoding="utf-8")
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False


def _log_uncaught(exc_type, exc_value, exc_tb):
    """sys.excepthook: пишем необработанные исключения в лог."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _logger.critical("Uncaught exception",
                     exc_info=(exc_type, exc_value, exc_tb))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _log_thread_exception(args):
    """threading.excepthook: пишем исключения фоновых потоков."""
    _logger.critical(
        "Uncaught exception in thread %s",
        getattr(args, "thread", "?").name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


sys.excepthook = _log_uncaught
if hasattr(threading, "excepthook"):
    threading.excepthook = _log_thread_exception

# Зеркалируем stdout/stderr в файл — чтобы HTTP-строки werkzeug и print()
# из приложения тоже сохранялись.
try:
    _CONSOLE_LOG = os.path.join(BASE_DIR, "server_console.log")
    _stream = open(_CONSOLE_LOG, "a", encoding="utf-8", buffering=1)

    class _Tee:
        def __init__(self, original, fileobj):
            self._original = original
            self._fileobj = fileobj

        def write(self, data):
            try:
                self._original.write(data)
            except Exception:
                pass
            try:
                self._fileobj.write(data)
                self._fileobj.flush()
            except Exception:
                pass
            return len(data) if isinstance(data, str) else 0

        def flush(self):
            for obj in (self._original, self._fileobj):
                try:
                    obj.flush()
                except Exception:
                    pass

        def fileno(self):
            return self._original.fileno()

        def isatty(self):
            return False

    sys.stdout = _Tee(sys.stdout, _stream)
    sys.stderr = _Tee(sys.stderr, _stream)
except Exception:
    pass
DB_PATH = os.path.join(BASE_DIR, "database", "app.db")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
TEMPLATE_DOCX = os.path.join(
    BASE_DIR, "docs", "АКТ уничтожения гражданских дел.docx")
# D8d: отдельный шаблон для административных дел
TEMPLATE_DOCX_ADMIN = os.path.join(
    BASE_DIR, "docs", "АКТ уничтожения административных дел.docx")

# Heartbeat: если вкладка интерфейса закрыта и heartbeat пропал — остановить сервер.
# Web Worker шлёт heartbeat каждые 4 с; таймаут 120 с — с запасом на:
#   * переходы между страницами интерфейса;
#   * открытый нативный диалог выбора файла (браузер приостанавливает
#     таймеры вкладки, включая Web Worker, пока диалог открыт);
#   * долгую обработку большого файла на сервере.
# При закрытии вкладки сервер живёт ещё до 2 минут — приемлемо для
# однопользовательского режима.
HEARTBEAT_TIMEOUT = 120.0  # секунд без heartbeat до остановки

# fix_32: launcher передаёт env-переменные дочернему процессу:
#   COURT_CASE_NO_WATCHDOG=1  — не следить за heartbeat (нет вкладки),
#                               вместо этого следить за родителем;
#   COURT_CASE_PARENT_PID=<pid>  — PID процесса-launcher.
_NO_WATCHDOG = os.environ.get("COURT_CASE_NO_WATCHDOG") == "1"
_PARENT_PID_RAW = os.environ.get("COURT_CASE_PARENT_PID", "")
try:
    _PARENT_PID = int(_PARENT_PID_RAW) if _PARENT_PID_RAW else None
except ValueError:
    _PARENT_PID = None


def _pid_alive(pid: int) -> bool:
    """Кросс-платформенная проверка, жив ли процесс с данным PID."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            h = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not h:
                return False
            kernel32.CloseHandle(h)
            return True
        except Exception:
            return False
    else:
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False


def _parent_watchdog():
    """
    Фоновый поток: если родительский процесс (launcher) умер —
    завершаем работу сервера. Заменяет heartbeat-watchdog, когда сервер
    запущен из launcher.
    """
    if _PARENT_PID is None:
        return
    while True:
        time.sleep(2.0)
        if not _pid_alive(_PARENT_PID):
            _logger.warning(
                "Родительский процесс (PID=%d) не найден — останавливаю "
                "сервер", _PARENT_PID)
            os._exit(0)
_last_beat = time.time()


def _beat_watchdog():
    """Фоновый поток: останавливает сервер, если heartbeat пропал."""
    while True:
        time.sleep(2.0)
        if time.time() - _last_beat > HEARTBEAT_TIMEOUT:
            _logger.warning(
                "Watchdog: heartbeat отсутствует %.1f c (порог %.1f) — "
                "останавливаю сервер через os._exit(0)",
                time.time() - _last_beat, HEARTBEAT_TIMEOUT)
            os._exit(0)


def start_beat_watchdog():
    """
    fix_32: если сервер запущен из launcher (NO_WATCHDOG=1) — вместо
    heartbeat-watchdog запускаем parent-watchdog (следим за launcher).
    Иначе — обычный heartbeat-watchdog (как раньше, для запуска app.py
    напрямую в браузере).
    """
    if _NO_WATCHDOG:
        _logger.info(
            "fix_32: watchdog переключён на parent-watch "
            "(launcher PID=%s)", _PARENT_PID)
        threading.Thread(target=_parent_watchdog, daemon=True).start()
        return
    threading.Thread(target=_beat_watchdog, daemon=True).start()


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 МБ

# Модуль «Внутренняя опись» (Word -> лист «Таблица»), этап 14e.
register_inventory_routes(app, lambda: (OUTPUT_DIR, UPLOAD_DIR))


def get_db():
    """Соединение с БД (создание/наполнение при первом обращении)."""
    return db.init_db(DB_PATH)


def _json_error(message, code=400):
    return jsonify({"error": message}), code


# ---------------------------------------------------------------------------
# Страницы
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        roles=ROLES,
        role_titles=ROLE_TITLES,
        columns=DEFAULT_COLUMNS,
    )


@app.route("/db_page")
def db_page():
    return render_template("db.html")


@app.route("/check_page")
def check_page():
    """Страница «Проверка категорий» (Доработка 6)."""
    return render_template("check.html")


@app.route("/heartbeat", methods=["GET"])
def heartbeat():
    """Сигнал «вкладка жива» от клиента."""
    global _last_beat
    _last_beat = time.time()
    return jsonify({"ok": True})


@app.route("/api/ping", methods=["GET", "POST"])
def api_ping():
    """
    Явный «пинг живучести» для клиента.

    Эквивалентен /heartbeat, но по нейтральному пути — используется,
    например, в JS перед открытием нативного файлового диалога, чтобы
    сервер не успел остановиться, пока таймеры вкладки заморожены.
    """
    global _last_beat
    _last_beat = time.time()
    return jsonify({"ok": True})


@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Остановка сервера по сигналу клиента (закрытие вкладки)."""
    os._exit(0)


@app.route("/preview", methods=["POST"])
def preview():
    """
    Предпросмотр загруженного исходного файла.

    Возвращает первые строки листа, автоопределённые номер строки
    заголовков и маппинг ролей.
    """
    if "file" not in request.files:
        return _json_error("Файл не загружен")
    uploaded = request.files["file"]
    if not uploaded.filename:
        return _json_error("Файл не выбран")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, os.path.basename(uploaded.filename))
    uploaded.save(path)

    try:
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True, read_only=True)
        ws = wb.active
        rows = []
        for values in ws.iter_rows(values_only=True):
            cells = []
            for v in values[:14]:
                if v is None:
                    cells.append("")
                else:
                    s = str(v)
                    cells.append(s[:80] + ("…" if len(s) > 80 else ""))
            rows.append(cells)
            if len(rows) >= 12:
                break
        wb.close()
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Не удалось прочитать файл: {exc}", 400)

    header_row = detect_header_row(rows)
    mapping = {}
    if header_row > 0 and header_row <= len(rows):
        mapping = auto_detect_roles(rows[header_row - 1])
    return jsonify({
        "rows": rows,
        "header_row": header_row,
        "mapping": mapping,
    })


# ---------------------------------------------------------------------------
# Проверка категорий дел (Доработка 6)
# ---------------------------------------------------------------------------

def _filter_rows_for_year(rows, year, alimony: bool) -> list:
    """
    Оставляет дела, попадающие в результат обработки:
    валидный номер за выбранный год + фильтр алиментных дел.
    """
    year = str(year)
    result = []
    for row in rows:
        if not is_valid_case_number(row.get("case_number"), year):
            continue
        if alimony or not contains_alimony(row.get("category")):
            result.append(row)
    return result


@app.route("/check_categories", methods=["POST"])
def check_categories():
    """
    Анализ загруженного файла: поиск дел с отсутствующей категорией,
    аналогов по истцу, групп «Без аналогов».

    Параметры формы:
        file       — файл (исходная таблица .xlsx/.xlsm или готовый результат);
        file_type  — 'source' (исходная таблица) или 'legacy' (готовый результат);
        year       — год дел;
        alimony    — '1' — включать алиментные дела;
        header_row — номер строки заголовков (для исходной таблицы).
    """
    if "file" not in request.files:
        return _json_error("Файл не загружен")
    uploaded = request.files["file"]
    if not uploaded.filename:
        return _json_error("Файл не выбран")

    year = request.form.get("year", "").strip()
    if not year.isdigit():
        return _json_error("Укажите год (например, 2023)")
    alimony = request.form.get("alimony") == "1"
    file_type = request.form.get("file_type", "source")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, os.path.basename(uploaded.filename))
    uploaded.save(path)

    try:
        if file_type == "legacy":
            # Готовый результат: записи извлекаются из заголовков
            raw_rows = parse_legacy_file(path)
        else:
            header_raw = request.form.get("header_row", "").strip()
            if header_raw == "":
                header_row = None
            else:
                try:
                    header_row = int(header_raw)
                except ValueError:
                    header_row = None
            _headers, raw_rows, _mapping = read_source_table(
                path, mapping=None, header_row=header_row)
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Не удалось прочитать файл: {exc}", 400)

    rows = _filter_rows_for_year(raw_rows, year, alimony)

    conn = get_db()
    try:
        org_names = db.organization_names(conn)
        categories_map = db.case_categories_map(conn)
        auto_fix_enabled = db.get_setting(conn, "auto_fix_categories", "1") == "1"
    finally:
        conn.close()

    result = analyze(rows, org_names, categories_map)
    result["cases_total"] = len(rows)
    result["auto_fix_enabled"] = auto_fix_enabled
    return jsonify(result)


@app.route("/apply_corrections", methods=["POST"])
def apply_corrections():
    """
    Сохранение исправлений в словарь «истец -> категория» (case_categories).

    Тело JSON: {"saves": [{"key": ..., "label": ..., "category": ...,
                           "is_organization": bool}, ...]}
    """
    data = request.get_json(force=True)
    saves = data.get("saves", []) or []
    conn = get_db()
    saved = 0
    try:
        for item in saves:
            key = str(item.get("key", "")).strip()
            label = str(item.get("label", "")).strip()
            category = str(item.get("category", "")).strip()
            if not key or not category:
                continue
            db.add_case_category(
                conn, key, label or key, category,
                bool(item.get("is_organization", False)))
            saved += 1
        return jsonify({"ok": True, "saved": saved})
    finally:
        conn.close()


@app.route("/download_no_analog_table", methods=["POST"])
def download_no_analog_table():
    """
    Выгрузка таблицы «Без аналогов» в Excel (.xlsx) для ручной работы.

    Тело JSON: {"groups": [...], "year": "2023"}
    """
    data = request.get_json(force=True)
    groups = data.get("groups", []) or []
    year = data.get("year", "")

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Без аналогов"
    ws.append(["Истец", "№ дела", "Категория (заполнить)"])
    for group in groups:
        label = str(group.get("label", ""))
        for case in group.get("cases", []):
            ws.append([label, str(case.get("case_number", "")), ""])
        # Подсказка из словаря БД
        opts = group.get("dictionary_options") or []
        if opts:
            ws.append(["", "", f"Варианты из словаря: {'; '.join(opts)}"])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"без_аналогов_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
    path = os.path.join(OUTPUT_DIR, filename)
    wb.save(path)
    return send_file(path, as_attachment=True, download_name=filename)


# ---------------------------------------------------------------------------
# Конвертация (stage12c, под-этап B3)
# ---------------------------------------------------------------------------

_CASE_NUM_IN_TITLE_RE = re.compile(r"№\s*(.+-\d+/\d{4})")


@app.route("/convert_page")
def convert_page():
    """Страница «Конвертация» (заготовка B3, полный UI — B4)."""
    return render_template("convert.html")


def _check_xlsx_extension(filename: str) -> None:
    """Проверка расширения для Excel-ветки."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".xlsx", ".xlsm"):
        raise ConverterError("Ожидается файл .xlsx или .xlsm")


@app.route("/inspect_file", methods=["POST"])
def inspect_file():
    """
    Инспекция файла для страницы конвертации.

    Параметры формы:
        file  — .xlsx/.xlsm;
        sheet — (опционально) имя листа; если не передан — отдаём список
                листов и работаем с листом по умолчанию.

    Возвращает JSON:
        sheets       — список листов (только при первом вызове, без sheet)
        sheet        — имя использованного листа
        mapping      — role -> индекс столбца
        preview      — первые 12 записей
        total        — всего записей
        year         — определённый год (самый частый из номеров дел)
        years        — {год: количество}
        others       — [[год, количество], ...] «чужие» годы
        warning      — человекочитаемое предупреждение (может быть "")
    """
    if "file" not in request.files:
        return _json_error("Файл не загружен")
    uploaded = request.files["file"]
    if not uploaded.filename:
        return _json_error("Файл не выбран")

    try:
        _check_xlsx_extension(uploaded.filename)
    except ConverterError as exc:
        return _json_error(str(exc))

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, os.path.basename(uploaded.filename))
    uploaded.save(path)

    sheet_param = request.form.get("sheet", "").strip() or None

    try:
        if sheet_param is None:
            info = inspect_sheets(path)
            sheets = info["sheets"]
            sheet = info["default"]
        else:
            sheets = None
            sheet = sheet_param

        records, mapping = read_result_xlsx(path, sheet_name=sheet)
    except ConverterError as exc:
        return _json_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Ошибка чтения файла: {exc}", 500)

    # Год из номеров дел (по заголовкам)
    nums = []
    for r in records:
        m = _CASE_NUM_IN_TITLE_RE.search(r.get("title") or "")
        if m:
            nums.append(m.group(1))

    try:
        yinfo = detect_year_from_numbers(nums)
    except ConverterError as exc:
        return _json_error(str(exc))

    preview = []
    for r in records[:12]:
        preview.append({
            "sequential": r.get("sequential"),
            "title": r.get("title") or "",
            "dates": (r.get("dates") or "").replace("\n", "<br>"),
            "opis": r.get("opis") or "",
            "unit": r.get("unit") or "",
            "count": r.get("count") or "",
            "retention": r.get("retention") or "",
            "note": r.get("note") or "",
        })

    return jsonify({
        "sheets": sheets,
        "sheet": sheet,
        "mapping": mapping,
        "preview": preview,
        "total": len(records),
        "year": yinfo["year"],
        "years": yinfo["years"],
        "others": yinfo["others"],
        "warning": make_warning_message(yinfo),
    })


@app.route("/convert/xlsx_to_word", methods=["POST"])
def convert_xlsx_to_word_route():
    """
    Конвертация Excel-результата в Word-акт.

    Параметры формы:
        file          — .xlsx/.xlsm;
        year          — год дел (обязателен);
        sheet         — имя листа (опционально);
        court_area_id — id участка (опционально);
        download      — '1' — сразу отдать файл;
        overwrite     — '1' — перезаписать существующий;
        copy          — '1' — сохранить как копию «(1).docx».

    Возвращает:
        download=1 -> файл;
        иначе      -> JSON {filename, count, total, preview};
        конфликт   -> 409 {error, filename, conflict: true}.
    """
    if "file" not in request.files:
        return _json_error("Файл не загружен")
    uploaded = request.files["file"]
    if not uploaded.filename:
        return _json_error("Файл не выбран")

    try:
        _check_xlsx_extension(uploaded.filename)
    except ConverterError as exc:
        return _json_error(str(exc))

    year = request.form.get("year", "").strip()
    if not year.isdigit():
        return _json_error("Укажите год (например, 2020)")

    sheet = request.form.get("sheet", "").strip() or None

    court_area_id_raw = request.form.get("court_area_id", "").strip()
    court_area_id = None
    if court_area_id_raw.isdigit():
        v = int(court_area_id_raw)
        if v > 0:
            court_area_id = v

    download = request.form.get("download") == "1"
    overwrite = request.form.get("overwrite") == "1"
    copy_mode = request.form.get("copy") == "1"

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, os.path.basename(uploaded.filename))
    uploaded.save(path)

    # Реквизиты: приоритет — court_areas, fallback — settings
    conn = get_db()
    try:
        area_values = (db.court_area_settings_dict(conn, court_area_id)
                       if court_area_id else None)
        settings = db.get_settings(conn)
    finally:
        conn.close()

    if area_values:
        num = str(area_values.get("судебный_участок") or "").strip()
        common_values = {k: ("" if v is None else v)
                         for k, v in area_values.items()}
    else:
        num = str(settings.get("судебный_участок") or "").strip()
        common_values = {k: ("" if v is None else v)
                         for k, v in dict(settings).items()}

    from core.filename_utils import make_act_filename
    filename = make_act_filename(num, "civil", year, "docx")
    out_path = os.path.join(OUTPUT_DIR, filename)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Проверка конфликта имени (решения 42/42а/42б)
    if os.path.exists(out_path) and not (overwrite or copy_mode):
        return jsonify({
            "error": "Файл уже существует",
            "filename": filename,
            "conflict": True,
        }), 409

    if copy_mode and os.path.exists(out_path):
        _base = filename[:-5] if filename.lower().endswith(".docx") else filename
        i = 1
        while True:
            cand = f"{_base} ({i}).docx"
            cand_path = os.path.join(OUTPUT_DIR, cand)
            if not os.path.exists(cand_path):
                filename = cand
                out_path = cand_path
                break
            i += 1

    try:
        result = convert_xlsx_to_word(
            path, TEMPLATE_DOCX, out_path,
            common_values=common_values, year=year, sheet_name=sheet)
    except ConverterError as exc:
        return _json_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Ошибка конвертации: {exc}", 500)

    if download:
        return send_file(out_path, as_attachment=True,
                         download_name=filename)

    preview = []
    for r in result["records"][:12]:
        preview.append({
            "sequential": r.get("sequential"),
            "title": r.get("title") or "",
            "dates": (r.get("dates") or "").replace("\n", "<br>"),
            "opis": r.get("opis") or "",
            "unit": r.get("unit") or "",
            "count": r.get("count") or "",
            "retention": r.get("retention") or "",
            "note": r.get("note") or "",
        })

    return jsonify({
        "filename": filename,
        "count": result["count"],
        "total": len(result["records"]),
        "preview": preview,
    })


@app.route("/convert/word_to_xlsx", methods=["POST"])
def convert_word_to_xlsx_route():
    """
    Конвертация Word-акта в Excel-результат.

    Параметры формы:
        file          — .docx;
        download      — '1' — сразу отдать файл;
        overwrite     — '1' — перезаписать существующий;
        copy          — '1' — сохранить как копию;
        restore_gaps  — '1' — восстановить пустые строки для пропусков;
        columns       — (опционально, повторяющийся) список ключей столбцов.

    Возвращает:
        download=1 -> файл;
        иначе      -> JSON {filename, count, total, attention, refs,
                            marker, preview};
        конфликт   -> 409 {error, filename, conflict: true}.
    """
    if "file" not in request.files:
        return _json_error("Файл не загружен")
    uploaded = request.files["file"]
    if not uploaded.filename:
        return _json_error("Файл не выбран")

    ext = os.path.splitext(uploaded.filename)[1].lower()
    if ext != ".docx":
        return _json_error("Ожидается файл .docx")

    download = request.form.get("download") == "1"
    overwrite = request.form.get("overwrite") == "1"
    copy_mode = request.form.get("copy") == "1"
    restore_gaps = request.form.get("restore_gaps") == "1"

    columns = request.form.getlist("columns") or None

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, os.path.basename(uploaded.filename))
    uploaded.save(path)

    # Имя файла: «Акт уничтожения гражданских дел {N}СУ {YYYY}.xlsx»
    # Год берём из номеров дел акта, участок — из реквизитов шапки акта.
    try:
        parsed = read_act_docx(path)
    except ConverterError as exc:
        return _json_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Ошибка чтения акта: {exc}", 500)

    nums = []
    for r in parsed["records"]:
        m = _CASE_NUM_IN_TITLE_RE.search(str(r.get("title") or ""))
        if m:
            nums.append(m.group(1))
    try:
        yinfo = detect_year_from_numbers(nums)
    except ConverterError as exc:
        return _json_error(str(exc))

    # Год: приоритет — номерам дел (решение 6).
    # Участок: из реквизитов шапки акта, если удалось извлечь.
    refs = parsed.get("refs") or {}
    num = (refs.get("номер") or "").strip()

    from core.filename_utils import make_act_filename
    filename = make_act_filename(num, "civil", yinfo["year"], "xlsx")
    out_path = os.path.join(OUTPUT_DIR, filename)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os.path.exists(out_path) and not (overwrite or copy_mode):
        return jsonify({
            "error": "Файл уже существует",
            "filename": filename,
            "conflict": True,
        }), 409

    if copy_mode and os.path.exists(out_path):
        _base = filename[:-5] if filename.lower().endswith(".xlsx") else filename
        i = 1
        while True:
            cand = f"{_base} ({i}).xlsx"
            cand_path = os.path.join(OUTPUT_DIR, cand)
            if not os.path.exists(cand_path):
                filename = cand
                out_path = cand_path
                break
            i += 1

    try:
        from core.converter.word_to_xlsx import convert_word_to_xlsx
        result = convert_word_to_xlsx(
            path, out_path, restore_gaps=restore_gaps, columns=columns)
    except ConverterError as exc:
        return _json_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Ошибка конвертации: {exc}", 500)

    if download:
        return send_file(out_path, as_attachment=True,
                         download_name=filename)

    # Превью первых 12 записей
    preview = []
    for r in result["records"][:12]:
        preview.append({
            "sequential": r.get("sequential"),
            "title": r.get("title") or "",
            "dates": (r.get("dates") or "").replace("\n", "<br>"),
            "opis": r.get("opis") or "",
            "unit": r.get("unit") or "",
            "count": r.get("count") or "",
            "retention": r.get("retention") or "",
            "note": r.get("note") or "",
        })

    return jsonify({
        "filename": filename,
        "count": result["count"],
        "total": len(result["records"]),
        "attention": result["attention"],
        "refs": result["refs"],
        "marker": result["marker"],
        "preview": preview,
        "year": yinfo["year"],
    })


# ---------------------------------------------------------------------------
# Страница года (stage16d6a, заглушка)
# ---------------------------------------------------------------------------

# D7: допустимые значения URL-схемы страницы года.
YEAR_CASE_TYPES = ("civil", "admin")
YEAR_SECTIONS = ("files", "cases", "inventory", "process", "result")


def _year_type_summary(conn, year_id: int, case_type: str) -> dict:
    """
    D7: сводка по одному типу дел за год.

    Файл считается относящимся к типу, если в нём есть хотя бы одно дело
    этого типа (source_files не хранит case_type, тип определяется по cases).
    """
    files = db.list_source_files(conn, year_id)
    type_files = []
    cases = []
    for f in files:
        file_cases = db.list_cases(
            conn, source_file_id=f["id"], case_type=case_type)
        if file_cases:
            type_files.append(f)
            cases.extend(file_cases)

    source_files = [f for f in type_files if f["file_kind"] == "source"]
    processed_files = [f for f in type_files if f["file_kind"] == "processed"]

    valid = sum(1 for c in cases if c["is_valid"])
    problematic = sum(1 for c in cases if c["is_problematic"])
    alimony = sum(1 for c in cases if c["is_alimony"])

    proc = db.get_processing_result_by_pair(conn, year_id, case_type)
    inventory = None
    if proc:
        inventory = db.get_inventory_by_result(conn, proc["id"])

    return {
        "case_type": case_type,
        "files_count": len(type_files),
        "source_files_count": len(source_files),
        "processed_files_count": len(processed_files),
        "cases_count": len(cases),
        "valid_count": valid,
        "problematic_count": problematic,
        "alimony_count": alimony,
        "result_id": proc["id"] if proc else None,
        "result_processed_at": proc["processed_at"] if proc else None,
        "result_record_count": proc["record_count"] if proc else 0,
        "result_is_stale": bool(proc and proc["is_stale"]),
        "inventory_id": inventory["id"] if inventory else None,
    }


@app.route("/db/year/<int:year_id>")
@app.route("/db/year/<int:year_id>/refs")
def db_year_page(year_id):
    """D7: обзорная страница года / раздел «Реквизиты».

    Единый шаблон year.html; конкретный раздел выбирает клиентский
    роутинг (year_page.js) по window.location.pathname.
    """
    return render_template("year.html", year_id=year_id)


@app.route("/db/year/<int:year_id>/<case_type>/<section>")
def db_year_section_page(year_id, case_type, section):
    """D7: раздел года внутри типа дел (files/cases/inventory/process/result)."""
    if case_type not in YEAR_CASE_TYPES:
        abort(404)
    if section not in YEAR_SECTIONS:
        abort(404)
    return render_template("year.html", year_id=year_id)


# ---------------------------------------------------------------------------
# API: дерево базы дел (stage16d5a)
# ---------------------------------------------------------------------------

@app.route("/api/db_tree")
def api_db_tree():
    """
    Дерево «судебный участок → год» со счётчиками для сайдбара (D7).

    Для каждого года добавлен блок "types" с разбивкой по типам дел
    (civil/admin): файлы, дела, результат, опись. Поля верхнего уровня
    (files_count/cases_count/result_id/result_is_stale) сохранены для
    обратной совместимости и отражают суммарные значения по обоим типам.

    Возвращает:
        {
          "areas": [
            {
              "id": 1, "номер": "9", "name": "...", ...,
              "years": [
                {
                  "id": 1, "year": 2020,
                  "is_closed": false, "is_incomplete": false,
                  "files_count": 2, "cases_count": 5,
                  "result_id": 7, "result_is_stale": false,
                  "types": {
                    "civil": { ...сводка... },
                    "admin": { ...сводка... },
                  },
                },
                ...
              ],
              "years_count": N,
            },
            ...
          ],
          "total_areas": N,
        }
    """
    conn = get_db()
    try:
        areas = db.list_court_areas(conn)
        result = []
        for a in areas:
            years = db.list_court_years(conn, a["id"])
            years_info = []
            for y in years:
                types = {
                    ct: _year_type_summary(conn, y["id"], ct)
                    for ct in YEAR_CASE_TYPES
                }
                files_count = sum(t["files_count"] for t in types.values())
                cases_count = sum(t["cases_count"] for t in types.values())
                # Для обратной совместимости: результат civil (как раньше)
                civil = types["civil"]
                years_info.append({
                    "id": y["id"],
                    "year": y["year"],
                    "is_closed": y["is_closed"],
                    "is_incomplete": y["is_incomplete"],
                    "files_count": files_count,
                    "cases_count": cases_count,
                    "result_id": civil["result_id"],
                    "result_is_stale": civil["result_is_stale"],
                    "types": types,
                })
            result.append({
                "id": a["id"],
                "номер": a["номер"],
                "name": a["name"],
                "address": a["address"],
                "note": a["note"],
                "years": years_info,
                "years_count": len(years_info),
            })
        return jsonify({"areas": result, "total_areas": len(result)})
    finally:
        conn.close()


@app.route("/api/court_years/<int:year_id>/summary")
def api_year_summary(year_id):
    """
    D7: обзорная сводка года — реквизиты + счётчики по типам дел.

    Возвращает:
        {
          "year": {...реквизиты court_years...},
          "types": {"civil": {...}, "admin": {...}},
        }
    """
    conn = get_db()
    try:
        cy = db.get_court_year(conn, year_id)
        if not cy:
            return _json_error("Год не найден", 404)
        types = {
            ct: _year_type_summary(conn, year_id, ct)
            for ct in YEAR_CASE_TYPES
        }
        return jsonify({"year": cy, "types": types})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: source_files и cases (stage16d5b)
# ---------------------------------------------------------------------------

@app.route("/api/court_years/<int:year_id>/source_files", methods=["GET"])
def api_source_files_list(year_id):
    """Список версий файлов года. Параметр file_kind: source|processed."""
    kind = request.args.get("file_kind", "").strip() or None
    conn = get_db()
    try:
        if not db.get_court_year(conn, year_id):
            return _json_error("Год не найден", 404)
        return jsonify(db.list_source_files(conn, year_id, file_kind=kind))
    finally:
        conn.close()


@app.route("/api/court_years/<int:year_id>/source_files", methods=["POST"])
def api_source_files_upload(year_id):
    """
    Загрузка файла в БД. multipart/form-data:
        file          — .xlsx / .xlsm
        file_kind     — 'source' (по умолчанию) | 'processed'
        case_type     — 'civil' (по умолчанию) | 'admin'
        sheet_name    — (опционально) имя листа
        header_row    — (опционально) номер строки заголовков
        mapping_json  — (опционально) JSON маппинга ролей
    """
    if "file" not in request.files:
        return _json_error("Файл не загружен")
    uploaded = request.files["file"]
    if not uploaded.filename:
        return _json_error("Файл не выбран")

    ext = os.path.splitext(uploaded.filename)[1].lower()
    if ext not in (".xlsx", ".xlsm"):
        return _json_error("Ожидается файл .xlsx или .xlsm")

    file_kind = (request.form.get("file_kind") or "source").strip()
    if file_kind not in ("source", "processed"):
        return _json_error("file_kind должен быть 'source' или 'processed'")

    case_type = (request.form.get("case_type") or "civil").strip()
    if case_type not in ("civil", "admin"):
        return _json_error("case_type должен быть 'civil' или 'admin'")

    sheet_name = (request.form.get("sheet_name") or "").strip()
    header_raw = (request.form.get("header_row") or "").strip()
    header_row = None
    if header_raw:
        try:
            header_row = int(header_raw)
            if header_row < 0:
                header_row = 0
        except ValueError:
            header_row = None

    mapping = None
    mapping_raw = (request.form.get("mapping_json") or "").strip()
    if mapping_raw:
        try:
            mapping = json.loads(mapping_raw)
        except ValueError:
            return _json_error("mapping_json не является JSON")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, os.path.basename(uploaded.filename))
    uploaded.save(path)

    from core.db_pipeline import save_year_source_from_xlsx

    conn = get_db()
    try:
        if not db.get_court_year(conn, year_id):
            return _json_error("Год не найден", 404)
        result = save_year_source_from_xlsx(
            conn, year_id, path, os.path.basename(uploaded.filename),
            sheet_name=sheet_name, header_row=header_row, mapping=mapping,
            file_kind=file_kind, case_type=case_type)
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Ошибка загрузки: {exc}", 500)
    finally:
        conn.close()


@app.route("/api/source_files/<int:file_id>", methods=["GET"])
def api_source_file_get(file_id):
    conn = get_db()
    try:
        rec = db.get_source_file(conn, file_id)
        if not rec:
            return _json_error("Файл не найден", 404)
        return jsonify(rec)
    finally:
        conn.close()


@app.route("/api/source_files/<int:file_id>/content", methods=["GET"])
def api_source_file_content(file_id):
    """Отдаёт BLOB файла как вложение."""
    conn = get_db()
    try:
        rec = db.get_source_file(conn, file_id)
        if not rec:
            return _json_error("Файл не найден", 404)
        content = db.get_source_file_content(conn, file_id)
        if content is None:
            return _json_error("Содержимое не найдено", 404)
        from io import BytesIO
        return send_file(
            BytesIO(content),
            as_attachment=True,
            download_name=rec["filename"] or "file.xlsx")
    finally:
        conn.close()


@app.route("/api/source_files/<int:file_id>/set_current", methods=["POST"])
def api_source_file_set_current(file_id):
    conn = get_db()
    try:
        ok = db.set_current_source_file(conn, file_id)
        if not ok:
            return _json_error("Файл не найден", 404)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/source_files/<int:file_id>", methods=["DELETE"])
def api_source_file_delete(file_id):
    conn = get_db()
    try:
        if not db.get_source_file(conn, file_id):
            return _json_error("Файл не найден", 404)
        db.delete_source_file(conn, file_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/source_files/<int:file_id>/cases", methods=["GET"])
def api_source_file_cases(file_id):
    """Список дел версии. Параметр case_type: civil|admin."""
    case_type = request.args.get("case_type", "").strip() or None
    conn = get_db()
    try:
        if not db.get_source_file(conn, file_id):
            return _json_error("Файл не найден", 404)
        return jsonify(db.list_cases(conn, source_file_id=file_id,
                                      case_type=case_type))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: обработка и экспорт (stage16d5c)
# ---------------------------------------------------------------------------

@app.route("/api/court_years/<int:year_id>/process", methods=["POST"])
def api_year_process(year_id):
    """
    Запуск обработки по данным года (из актуального source_file).

    Тело JSON:
        {
          "case_type": "civil"|"admin",
          "process_alimony": true|false,
          "source_file_id": int|null,   # конкретная версия (опц.)
          "category_fixes": {...},      # номер -> категория (опц.)
          "auto_fix": true|false,       # автоисправление категорий
          "court_area_id": int|null     # если не задан — берётся из года
        }

    Возвращает:
        {
          "ok": true,
          "result_id": int,
          "source_file_id": int,
          "record_count": int,
          "stats": {...},
          "target_year": int
        }
    """
    data = request.get_json(force=True) or {}
    case_type = (data.get("case_type") or "civil").strip()
    if case_type not in ("civil", "admin"):
        return _json_error("case_type должен быть 'civil' или 'admin'")

    process_alimony = bool(data.get("process_alimony", False))
    source_file_id = data.get("source_file_id")
    if source_file_id is not None:
        try:
            source_file_id = int(source_file_id)
        except (TypeError, ValueError):
            return _json_error("source_file_id должен быть числом")

    category_fixes = data.get("category_fixes") or {}
    if not isinstance(category_fixes, dict):
        return _json_error("category_fixes должен быть объектом")
    # Нормализация ключей
    category_fixes = {str(k).strip(): v
                      for k, v in category_fixes.items() if str(k).strip()}

    auto_fix_enabled = bool(data.get("auto_fix", True))

    court_area_id = data.get("court_area_id")
    if court_area_id is not None:
        try:
            court_area_id = int(court_area_id)
        except (TypeError, ValueError):
            return _json_error("court_area_id должен быть числом")

    from core.db_pipeline import process_year

    conn = get_db()
    try:
        cy = db.get_court_year(conn, year_id)
        if not cy:
            return _json_error("Год не найден", 404)

        # Если court_area_id не передан — берём из года
        if court_area_id is None:
            court_area_id = cy["court_area_id"]

        result = process_year(
            conn, year_id,
            case_type=case_type,
            process_alimony=process_alimony,
            category_fixes=category_fixes or None,
            auto_fix_enabled=auto_fix_enabled,
            court_area_id=court_area_id,
            source_file_id=source_file_id)
        return jsonify({"ok": True, **result})
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Ошибка обработки: {exc}", 500)
    finally:
        conn.close()


@app.route("/api/court_years/<int:year_id>/results", methods=["GET"])
def api_year_results(year_id):
    """Список результатов года (может быть civil и admin)."""
    conn = get_db()
    try:
        if not db.get_court_year(conn, year_id):
            return _json_error("Год не найден", 404)
        return jsonify(db.list_processing_results(conn, year_id))
    finally:
        conn.close()


@app.route("/api/results/<int:result_id>", methods=["GET"])
def api_result_get(result_id):
    """Шапка + строки результата."""
    conn = get_db()
    try:
        rec = db.get_processing_result(conn, result_id)
        if not rec:
            return _json_error("Результат не найден", 404)
        rows = db.list_result_rows(conn, result_id)
        rec["rows"] = rows
        return jsonify(rec)
    finally:
        conn.close()


@app.route("/api/results/<int:result_id>/export", methods=["POST"])
def api_result_export(result_id):
    """
    Экспорт результата в .docx / .xlsx.

    Тело JSON:
        {
          "output_format": "word"|"excel",
          "columns": [...]  # опционально для Excel
        }

    Возвращает файл (send_file).
    """
    data = request.get_json(force=True) or {}
    output_format = (data.get("output_format") or "word").strip()
    if output_format not in ("word", "excel"):
        return _json_error("output_format должен быть 'word' или 'excel'")

    columns = data.get("columns") or None
    if columns is not None and not isinstance(columns, list):
        return _json_error("columns должен быть списком")

    from core.db_pipeline import export_year_result_to_file

    conn = get_db()
    try:
        if not db.get_processing_result(conn, result_id):
            return _json_error("Результат не найден", 404)
        result = export_year_result_to_file(
            conn, result_id,
            template_path=TEMPLATE_DOCX,
            template_path_admin=TEMPLATE_DOCX_ADMIN,
            output_dir=OUTPUT_DIR,
            output_format=output_format,
            columns=columns)
        return send_file(result["path"], as_attachment=True,
                         download_name=result["filename"])
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Ошибка экспорта: {exc}", 500)
    finally:
        conn.close()


@app.route("/api/results/<int:result_id>", methods=["DELETE"])
def api_result_delete(result_id):
    conn = get_db()
    try:
        if not db.get_processing_result(conn, result_id):
            return _json_error("Результат не найден", 404)
        db.delete_processing_result(conn, result_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Обработка и скачивание
# ---------------------------------------------------------------------------

@app.route("/process", methods=["POST"])
def process():
    if "file" not in request.files:
        return _json_error("Файл не загружен")
    uploaded = request.files["file"]
    if not uploaded.filename:
        return _json_error("Файл не выбран")

    year = request.form.get("year", "").strip()
    if not year.isdigit():
        return _json_error("Укажите год (например, 2023)")

    alimony = request.form.get("alimony") == "1"
    output_format = request.form.get("format", "excel")
    if output_format not in ("excel", "word"):
        output_format = "excel"

    # stage11d: выбор судебного участка (id из court_areas)
    court_area_id_raw = request.form.get("court_area_id", "").strip()
    court_area_id = None
    if court_area_id_raw.isdigit():
        v = int(court_area_id_raw)
        if v > 0:
            court_area_id = v

    # Ручной маппинг ролей (если передан)
    mapping = {}
    for role in ROLES:
        value = request.form.get(f"map_{role}", "").strip()
        if value.isdigit() and int(value) > 0:
            mapping[role] = int(value)
    header_raw = request.form.get("header_row", "").strip()
    if header_raw == "":
        header_row = None  # автоопределение
    else:
        try:
            header_row = int(header_raw)
        except ValueError:
            header_row = None
        if header_row is not None and header_row < 0:
            header_row = 0

    # Выбранные столбцы для Excel (пусто = все)
    columns = request.form.getlist("columns")

    # Доработка 6: исправления категорий со страницы проверки + автоисправление
    fixes_raw = request.form.get("fixes", "").strip()
    category_fixes = {}
    if fixes_raw:
        try:
            raw = json.loads(fixes_raw) or {}
            # fix_02: ключи номеров дел — без хвостовых/неразрывных пробелов
            category_fixes = {
                str(k).strip(): v for k, v in raw.items() if str(k).strip()
            }
        except ValueError:
            category_fixes = {}
    auto_fix_enabled = request.form.get("auto_fix", "1") != "0"
    file_type = request.form.get("file_type", "source")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    upload_path = os.path.join(UPLOAD_DIR, os.path.basename(uploaded.filename))
    uploaded.save(upload_path)

    try:
        if file_type == "legacy":
            # Готовый результат (Доработка 7): даты дела, № описи,
            # № ед.хр., кол-во и срок хранения переносятся «как есть».
            raw_rows = parse_legacy_file(upload_path)
            if not raw_rows:
                raise ValueError(
                    "В файле не найдено дел (проверьте, что это результат "
                    "обработки или акт уничтожения)")
            result = process_rows(
                raw_rows, int(year), alimony, output_format,
                DB_PATH, TEMPLATE_DOCX, OUTPUT_DIR,
                columns=columns or None,
                category_fixes=category_fixes,
                auto_fix_enabled=auto_fix_enabled,
                court_area_id=court_area_id)
        else:
            result = process_upload(
                upload_path, int(year), alimony, output_format,
                DB_PATH, TEMPLATE_DOCX, OUTPUT_DIR,
                columns=columns or None,
                mapping=mapping or None,
                header_row=header_row,
                category_fixes=category_fixes,
                auto_fix_enabled=auto_fix_enabled,
                court_area_id=court_area_id,
            )
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Ошибка обработки: {exc}", 500)

    # Доработка 7: прямое скачивание результата (кнопка «Скачать результат»)
    if request.form.get("download") == "1":
        return send_file(result["path"], as_attachment=True,
                         download_name=result["filename"])

    # Подготовка данных для предпросмотра
    preview = []
    for record in result["records"]:
        preview.append({
            "sequential": record.get("sequential"),
            "title": record.get("title") or "",
            "dates": (record.get("dates") or "").replace("\n", "<br>"),
            "opis": record.get("opis") or "",
            "unit": record.get("unit") or "",
            "count": record.get("count") or "",
            "retention": record.get("retention") or "",
            "note": record.get("note") or "",
        })

    stats = result["stats"]
    stats_message = (
        f"Всего номеров в диапазоне: {stats['total_in_range']}\n"
        f"Найдено подходящих дел: {stats['valid_count']}\n"
        f"Пропущенных номеров: {stats['skipped_numbers']}\n"
        f"Алиментных дел исключено: {stats['alimony_excluded']}\n"
        f"Категорий автоподставлено из словаря: {stats.get('auto_fixed', 0)}"
    )
    return jsonify({
        "records": preview,
        "stats": stats,
        "stats_message": stats_message,
        "filename": result["filename"],
    })


@app.route("/download/<path:filename>")
def download(filename):
    safe = os.path.basename(filename)
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path, as_attachment=True)


# ---------------------------------------------------------------------------
# API: организации
# ---------------------------------------------------------------------------

@app.route("/api/organizations", methods=["GET"])
def api_orgs_list():
    conn = get_db()
    try:
        return jsonify(db.list_organizations(conn))
    finally:
        conn.close()


@app.route("/api/organizations", methods=["POST"])
def api_orgs_add():
    data = request.get_json(force=True)
    name = str(data.get("name", "")).strip()
    if not name:
        return _json_error("Название организации не может быть пустым")
    claim_type = str(data.get("claim_type", "по иску")).strip()
    conn = get_db()
    try:
        db.add_organization(conn, name, claim_type)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/organizations/<int:org_id>", methods=["PUT"])
def api_orgs_update(org_id):
    data = request.get_json(force=True)
    name = str(data.get("name", "")).strip()
    if not name:
        return _json_error("Название организации не может быть пустым")
    claim_type = str(data.get("claim_type", "по иску")).strip()
    conn = get_db()
    try:
        db.update_organization(conn, org_id, name, claim_type)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/organizations/<int:org_id>", methods=["DELETE"])
def api_orgs_delete(org_id):
    conn = get_db()
    try:
        db.delete_organization(conn, org_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: судебные участки и годы (stage16a1a, схема v2)
# ---------------------------------------------------------------------------

@app.route("/api/court_areas", methods=["GET"])
def api_court_areas_list():
    conn = get_db()
    try:
        return jsonify(db.list_court_areas(conn))
    finally:
        conn.close()


@app.route("/api/court_areas", methods=["POST"])
def api_court_areas_add():
    data = request.get_json(force=True)
    conn = get_db()
    try:
        area_id = db.add_court_area(conn, data)
        return jsonify({"ok": True, "id": area_id})
    except ValueError as exc:
        return _json_error(str(exc))
    finally:
        conn.close()


@app.route("/api/court_areas/<int:area_id>", methods=["GET"])
def api_court_areas_get(area_id):
    conn = get_db()
    try:
        rec = db.get_court_area(conn, area_id)
        if not rec:
            return _json_error("Участок не найден", 404)
        return jsonify(rec)
    finally:
        conn.close()


@app.route("/api/court_areas/<int:area_id>", methods=["PUT"])
def api_court_areas_update(area_id):
    data = request.get_json(force=True)
    conn = get_db()
    try:
        if not db.get_court_area(conn, area_id):
            return _json_error("Участок не найден", 404)
        db.update_court_area(conn, area_id, data)
        return jsonify({"ok": True})
    except ValueError as exc:
        return _json_error(str(exc))
    finally:
        conn.close()


@app.route("/api/court_areas/<int:area_id>", methods=["DELETE"])
def api_court_areas_delete(area_id):
    conn = get_db()
    try:
        db.delete_court_area(conn, area_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/court_areas/<int:area_id>/years", methods=["GET"])
def api_court_years_list(area_id):
    conn = get_db()
    try:
        if not db.get_court_area(conn, area_id):
            return _json_error("Участок не найден", 404)
        return jsonify(db.list_court_years(conn, area_id))
    finally:
        conn.close()


@app.route("/api/court_areas/<int:area_id>/years", methods=["POST"])
def api_court_years_add(area_id):
    data = request.get_json(force=True)
    year = data.get("year")
    try:
        year_int = int(year)
    except (TypeError, ValueError):
        return _json_error("Укажите год (число)")
    conn = get_db()
    try:
        if not db.get_court_area(conn, area_id):
            return _json_error("Участок не найден", 404)
        if db.court_year_for(conn, area_id, year_int):
            return _json_error(f"Год {year_int} уже существует у этого участка")
        yid = db.add_court_year(conn, area_id, year_int, data)
        return jsonify({"ok": True, "id": yid})
    finally:
        conn.close()


@app.route("/api/court_years/<int:year_id>", methods=["GET"])
def api_court_year_get(year_id):
    conn = get_db()
    try:
        rec = db.get_court_year(conn, year_id)
        if not rec:
            return _json_error("Год не найден", 404)
        return jsonify(rec)
    finally:
        conn.close()


@app.route("/api/court_years/<int:year_id>", methods=["PUT"])
def api_court_year_update(year_id):
    data = request.get_json(force=True)
    conn = get_db()
    try:
        if not db.get_court_year(conn, year_id):
            return _json_error("Год не найден", 404)
        db.update_court_year(conn, year_id, data)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/court_years/<int:year_id>", methods=["DELETE"])
def api_court_year_delete(year_id):
    conn = get_db()
    try:
        db.delete_court_year(conn, year_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/court_areas/<int:area_id>/copy_refs", methods=["POST"])
def api_court_area_copy_refs(area_id):
    """
    Копирование реквизитов из одного года в другой у того же участка.

    Тело JSON: {"from_year": 2019, "to_year": 2020}
    """
    data = request.get_json(force=True) or {}
    try:
        from_year = int(data.get("from_year"))
        to_year = int(data.get("to_year"))
    except (TypeError, ValueError):
        return _json_error("Укажите from_year и to_year (числа)")

    conn = get_db()
    try:
        if not db.get_court_area(conn, area_id):
            return _json_error("Участок не найден", 404)
        src = db.court_year_for(conn, area_id, from_year)
        if not src:
            return _json_error(f"Год {from_year} не найден")
        dst = db.court_year_for(conn, area_id, to_year)
        payload = {f: src.get(f, "") for f in (
            "судья", "секретарь", "дата_утверждения", "дата_акта",
            "номер_акта", "дата_подписи", "протокол_эк_дата",
            "протокол_эк_номер")}
        if dst:
            db.update_court_year(conn, dst["id"], {**dst, **payload})
            return jsonify({"ok": True, "updated": dst["id"]})
        yid = db.add_court_year(conn, area_id, to_year, payload)
        return jsonify({"ok": True, "created": yid})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: импорт/экспорт базы данных
# ---------------------------------------------------------------------------

@app.route("/api/db/import", methods=["POST"])
def api_db_import():
    """Импорт организаций из Excel-файла (лист «База данных»)."""
    if "file" not in request.files:
        return _json_error("Файл не загружен")
    uploaded = request.files["file"]
    if not uploaded.filename:
        return _json_error("Файл не выбран")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, os.path.basename(uploaded.filename))
    uploaded.save(path)
    conn = get_db()
    try:
        added = db.import_database_from_excel(conn, path)
        return jsonify({"ok": True, "added": added})
    except Exception as exc:  # noqa: BLE001
        return _json_error(f"Ошибка импорта: {exc}", 400)
    finally:
        conn.close()


@app.route("/api/db/export")
def api_db_export():
    """Экспорт базы данных в Excel-файл."""
    conn = get_db()
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filename = f"база_данных_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = os.path.join(OUTPUT_DIR, filename)
        db.export_database_to_excel(conn, path)
        return send_file(path, as_attachment=True,
                         download_name=filename)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: правила сроков хранения
# ---------------------------------------------------------------------------

@app.route("/api/retention_rules", methods=["GET"])
def api_rules_list():
    conn = get_db()
    try:
        return jsonify(db.list_retention_rules(conn))
    finally:
        conn.close()


@app.route("/api/retention_rules", methods=["POST"])
def api_rules_add():
    data = request.get_json(force=True)
    keyword = str(data.get("keyword", "")).strip()
    code = str(data.get("code", "")).strip()
    if not keyword or not code:
        return _json_error("Укажите корень и код типа")
    conn = get_db()
    try:
        db.add_retention_rule(conn, keyword, code,
                              data.get("result_text"))
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/retention_rules/<int:rule_id>", methods=["PUT"])
def api_rules_update(rule_id):
    data = request.get_json(force=True)
    keyword = str(data.get("keyword", "")).strip()
    code = str(data.get("code", "")).strip()
    if not keyword or not code:
        return _json_error("Укажите корень и код типа")
    conn = get_db()
    try:
        db.update_retention_rule(conn, rule_id, keyword, code,
                                 data.get("result_text"))
        return jsonify({"ok": True})
    finally:
        conn.close()


@app.route("/api/retention_rules/<int:rule_id>", methods=["DELETE"])
def api_rules_delete(rule_id):
    conn = get_db()
    try:
        db.delete_retention_rule(conn, rule_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: настройки
# ---------------------------------------------------------------------------

@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    conn = get_db()
    try:
        return jsonify(db.get_settings(conn))
    finally:
        conn.close()


@app.route("/api/settings", methods=["POST"])
def api_settings_save():
    data = request.get_json(force=True)
    conn = get_db()
    try:
        for key, value in data.items():
            db.set_setting(conn, str(key), str(value))
        return jsonify({"ok": True})
    finally:
        conn.close()


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    _logger.info("Сервер стартует. app.py=%s", __file__)
    _logger.info("DB_PATH=%s", DB_PATH)
    _logger.info("Server log: %s", _SERVER_LOG)
    _logger.info("Console log: %s",
                 locals().get("_CONSOLE_LOG", "(no console log)"))
    # Инициализация БД при старте.
    # stage16a1c: если схема старая (v1) — просим запустить миграцию.
    try:
        get_db().close()
    except RuntimeError as exc:
        print()
        print("=" * 64)
        print("ТРЕБУЕТСЯ МИГРАЦИЯ БАЗЫ ДАННЫХ")
        print("=" * 64)
        print(str(exc))
        print()
        print("Запустите:")
        print("  .venv\\Scripts\\python.exe migrate_db_v2.py")
        print()
        sys.exit(1)
    # Автозапуск браузера и контроль закрытия вкладки (остановка сервера)
    start_beat_watchdog()
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)