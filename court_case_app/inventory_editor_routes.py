# stage_49c
"""Веб-редактор Внутренней описи (акт уничтожения).

Blueprint ``inventory_editor``. URL-префиксы:
    /inventory_editor/...          — HTML-страница редактора;
    /api/inventory_editor/...      — JSON API.

Соединение с БД берётся через ``current_app.config["DB_PATH"]``
(устанавливает app.py при регистрации blueprint'а). Перед каждым
запросом выполняется ``inventory_doc_types.ensure_schema(conn)`` —
идемпотентная миграция справочника типов документов.
"""
from __future__ import annotations

import os
import tempfile
from io import BytesIO

from flask import (Blueprint, current_app, jsonify, render_template,
                   request, send_file)

from database import db
from database import inventory_doc_types

from core.inventory_editor import (
    InventoryValidationError,
    add_case,
    compute_derived,
    delete_case,
    delete_row,
    export_to_excel,
    generate_from_cases,
    group_by_case,
    import_from_excel,
    list_docs,
    replace_docs,
)


inventory_editor_bp = Blueprint("inventory_editor", __name__)

ALLOWED_KINDS = ("civil", "admin")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _json_err(message: str, code: int = 400):
    return jsonify({"error": message}), code


def _get_conn():
    """Открывает соединение и гарантирует наличие inventory_doc_types."""
    db_path = current_app.config.get("DB_PATH")
    if not db_path:
        raise RuntimeError("DB_PATH не задан в конфиге приложения")
    conn = db.init_db(db_path)
    inventory_doc_types.ensure_schema(conn)
    return conn


def _inventory_exists(conn, inventory_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM processing_inventories WHERE id = ? LIMIT 1",
        (inventory_id,)).fetchone()
    return row is not None


def _pack(docs):
    """Doc[] -> сериализуемый ответ: rows (с A/B/E/I/J) + groups + total."""
    derived = compute_derived(docs)
    rows = []
    for d, der in zip(docs, derived):
        item = d.to_dict()
        item.update({
            "A": der["A"], "B": der["B"], "E": der["E"],
            "I": der["I"], "J": der["J"],
        })
        rows.append(item)
    groups = [
        {"prefix": g["prefix"], "case_number": g["case_number"],
         "year": g["year"], "count": len(g["docs"])}
        for g in group_by_case(docs)
    ]
    return {"rows": rows, "groups": groups, "total": len(rows)}


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

@inventory_editor_bp.route("/inventory_editor/<int:inventory_id>")
def page(inventory_id: int):
    return render_template("inventory_editor.html", inventory_id=inventory_id)


# ---------------------------------------------------------------------------
# API: справочник типов документов
# ---------------------------------------------------------------------------

@inventory_editor_bp.route("/api/inventory_editor/doc-types", methods=["GET"])
def api_doc_types():
    kind = request.args.get("kind", "").strip() or None
    if kind and kind not in ALLOWED_KINDS:
        return _json_err("kind: 'civil' или 'admin'")
    conn = _get_conn()
    try:
        return jsonify(inventory_doc_types.list_types(conn, kind))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: получить/создать опись по result_id
# ---------------------------------------------------------------------------

@inventory_editor_bp.route(
    "/api/inventory_editor/by_result/<int:result_id>",
    methods=["GET", "POST"])
def api_inventory_by_result(result_id: int):
    """Возвращает inventory_id для result_id; при отсутствии — создаёт."""
    conn = _get_conn()
    try:
        rec = db.get_processing_result(conn, result_id)
        if not rec:
            return _json_err("Результат не найден", 404)
        row = conn.execute(
            "SELECT id FROM processing_inventories WHERE result_id = ?",
            (result_id,)).fetchone()
        if row:
            return jsonify({"inventory_id": row[0], "result_id": result_id})
        cur = conn.execute(
            "INSERT INTO processing_inventories (result_id) VALUES (?)",
            (result_id,))
        conn.commit()
        return jsonify({"inventory_id": cur.lastrowid, "result_id": result_id})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: строки описи
# ---------------------------------------------------------------------------

@inventory_editor_bp.route(
    "/api/inventory_editor/<int:inventory_id>/rows", methods=["GET"])
def api_rows_list(inventory_id: int):
    conn = _get_conn()
    try:
        if not _inventory_exists(conn, inventory_id):
            return _json_err("Опись не найдена", 404)
        docs = list_docs(conn, inventory_id)
        return jsonify(_pack(docs))
    finally:
        conn.close()


@inventory_editor_bp.route(
    "/api/inventory_editor/<int:inventory_id>/rows", methods=["POST"])
def api_rows_add(inventory_id: int):
    data = request.get_json(force=True) or {}
    prefix = str(data.get("prefix", "")).strip()
    try:
        case_number = int(data.get("case_number", 0))
        year = int(data.get("year", 0))
    except (TypeError, ValueError):
        return _json_err("case_number и year должны быть числами")
    docs_in = data.get("docs") or []
    if not docs_in:
        return _json_err("Нужен хотя бы один документ")
    titles, pages = [], []
    for d in docs_in:
        t = str(d.get("title", "")).strip()
        if not t:
            return _json_err("У каждого документа должно быть наименование")
        try:
            p = int(d.get("pages_count", 1) or 1)
        except (TypeError, ValueError):
            p = 1
        titles.append(t)
        pages.append(p)

    conn = _get_conn()
    try:
        if not _inventory_exists(conn, inventory_id):
            return _json_err("Опись не найдена", 404)
        try:
            add_case(conn, inventory_id, prefix, case_number, year,
                     titles, pages)
        except InventoryValidationError as exc:
            return _json_err(str(exc), 400)
        return jsonify(_pack(list_docs(conn, inventory_id)))
    finally:
        conn.close()


@inventory_editor_bp.route(
    "/api/inventory_editor/<int:inventory_id>/rows/<int:row_id>",
    methods=["PUT"])
def api_row_update(inventory_id: int, row_id: int):
    data = request.get_json(force=True) or {}
    conn = _get_conn()
    try:
        if not _inventory_exists(conn, inventory_id):
            return _json_err("Опись не найдена", 404)
        docs = list_docs(conn, inventory_id)
        found = False
        for d in docs:
            if d.row_id != row_id:
                continue
            if "title" in data:
                d.title = str(data["title"]).strip()
            if "prefix" in data:
                d.prefix = str(data["prefix"]).strip()
            if "pages_count" in data:
                try:
                    d.pages_count = int(data["pages_count"] or 1)
                except (TypeError, ValueError):
                    d.pages_count = 1
            found = True
        if not found:
            return _json_err("Строка не найдена", 404)
        try:
            replace_docs(conn, inventory_id, docs)
        except InventoryValidationError as exc:
            return _json_err(str(exc), 400)
        return jsonify(_pack(list_docs(conn, inventory_id)))
    finally:
        conn.close()


@inventory_editor_bp.route(
    "/api/inventory_editor/<int:inventory_id>/rows/<int:row_id>",
    methods=["DELETE"])
def api_row_delete(inventory_id: int, row_id: int):
    conn = _get_conn()
    try:
        if not _inventory_exists(conn, inventory_id):
            return _json_err("Опись не найдена", 404)
        try:
            delete_row(conn, inventory_id, row_id)
        except InventoryValidationError as exc:
            return _json_err(str(exc), 400)
        return jsonify(_pack(list_docs(conn, inventory_id)))
    finally:
        conn.close()


@inventory_editor_bp.route(
    "/api/inventory_editor/<int:inventory_id>/cases/<int:year>/<int:case_number>",
    methods=["DELETE"])
def api_case_delete(inventory_id: int, year: int, case_number: int):
    conn = _get_conn()
    try:
        if not _inventory_exists(conn, inventory_id):
            return _json_err("Опись не найдена", 404)
        removed = delete_case(conn, inventory_id, year, case_number)
        payload = _pack(list_docs(conn, inventory_id))
        payload["removed"] = removed
        return jsonify(payload)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: импорт / генерация / экспорт
# ---------------------------------------------------------------------------

@inventory_editor_bp.route(
    "/api/inventory_editor/<int:inventory_id>/import", methods=["POST"])
def api_import(inventory_id: int):
    if "file" not in request.files:
        return _json_err("Файл не загружен")
    upload = request.files["file"]
    if not upload.filename:
        return _json_err("Файл не выбран")
    sheet = (request.form.get("sheet_name") or "Таблица").strip() or "Таблица"

    suffix = os.path.splitext(upload.filename)[1] or ".xlsx"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        upload.save(tmp_path)
        try:
            docs = import_from_excel(tmp_path, sheet_name=sheet)
        except ValueError as exc:
            return _json_err(str(exc), 400)
        conn = _get_conn()
        try:
            if not _inventory_exists(conn, inventory_id):
                return _json_err("Опись не найдена", 404)
            try:
                replace_docs(conn, inventory_id, docs)
            except InventoryValidationError as exc:
                return _json_err(str(exc), 400)
            payload = _pack(list_docs(conn, inventory_id))
            payload["imported"] = len(docs)
            return jsonify(payload)
        finally:
            conn.close()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@inventory_editor_bp.route(
    "/api/inventory_editor/<int:inventory_id>/generate", methods=["POST"])
def api_generate(inventory_id: int):
    data = request.get_json(force=True) or {}
    try:
        year = int(data.get("year", 0))
    except (TypeError, ValueError):
        return _json_err("year должен быть числом")
    kind = (data.get("kind") or "civil").strip()
    if kind not in ALLOWED_KINDS:
        return _json_err("kind: 'civil' или 'admin'")

    conn = _get_conn()
    try:
        if not _inventory_exists(conn, inventory_id):
            return _json_err("Опись не найдена", 404)
        docs = generate_from_cases(conn, year, kind)
        if not docs:
            return _json_err(
                "Нет дел для указанного года и типа (или в БД нет нужных "
                "колонок)", 400)
        try:
            replace_docs(conn, inventory_id, docs)
        except InventoryValidationError as exc:
            return _json_err(str(exc), 400)
        payload = _pack(list_docs(conn, inventory_id))
        payload["generated"] = len(docs)
        return jsonify(payload)
    finally:
        conn.close()


@inventory_editor_bp.route(
    "/api/inventory_editor/<int:inventory_id>/export", methods=["POST"])
def api_export(inventory_id: int):
    if "template" not in request.files:
        return _json_err("Не загружен шаблон .xlsx (поле 'template')")
    tmpl = request.files["template"]
    if not tmpl.filename:
        return _json_err("Шаблон не выбран")
    sheet = (request.form.get("sheet_name") or "Таблица").strip() or "Таблица"
    out_name = (request.form.get("output_filename") or "inventory.xlsx").strip()
    if not out_name.lower().endswith(".xlsx"):
        out_name += ".xlsx"

    suffix = os.path.splitext(tmpl.filename)[1] or ".xlsx"
    fd_t, tmp_tmpl = tempfile.mkstemp(suffix=suffix)
    os.close(fd_t)
    fd_o, tmp_out = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd_o)
    try:
        tmpl.save(tmp_tmpl)
        conn = _get_conn()
        try:
            if not _inventory_exists(conn, inventory_id):
                return _json_err("Опись не найдена", 404)
            docs = list_docs(conn, inventory_id)
            if not docs:
                return _json_err("Опись пуста — экспортировать нечего", 400)
            try:
                export_to_excel(docs, tmp_tmpl, tmp_out, sheet_name=sheet)
            except ValueError as exc:
                return _json_err(str(exc), 400)
        finally:
            conn.close()
        with open(tmp_out, "rb") as fh:
            buf = BytesIO(fh.read())
        return send_file(
            buf, as_attachment=True, download_name=out_name,
            mimetype="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet")
    finally:
        for p in (tmp_tmpl, tmp_out):
            try:
                os.unlink(p)
            except OSError:
                pass
