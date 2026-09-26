# -*- coding: utf-8 -*-
"""
Роуты модуля «Внутренняя опись» (этап 14e, решения 22–23).

Регистрация (из app.py):
    from core.inventory.api import register_routes
    register_routes(app, lambda: (OUTPUT_DIR, UPLOAD_DIR))

Роуты:
    GET  /inventory_page        — страница «Внутренняя опись»;
    POST /inventory/inspect      — предварительный анализ docx-файлов;
    POST /inventory/convert      — конвертация Word -> лист «Таблица».

Каталоги передаются ленивой функцией dirs_getter() -> (output, upload),
чтобы тесты могли подменять app.OUTPUT_DIR/UPLOAD_DIR.
"""

import os

from flask import jsonify, render_template, request, send_file

from .docx_reader import read_inventory_docx
from .exceptions import InventoryError
from .flow import build_flow
from .normalizer import CASE_ADMIN, CASE_CIVIL
from .writer import prepare_rows, write_result

DEFAULT_AREA = ""


def _json_error(message, code=400):
    return jsonify({"error": message}), code


def _type_word(flow_type: str) -> str:
    """«гражданских» / «административных» / «»."""
    if flow_type == CASE_CIVIL:
        return "гражданских"
    if flow_type == CASE_ADMIN:
        return "административных"
    return ""


def default_name(flow_type: str, court_area: str, year) -> str:
    """Имя по умолчанию (решение 22)."""
    parts = ["Внутренняя опись"]
    word = _type_word(flow_type)
    if word:
        parts.append(f"{word} дел")
    else:
        parts.append("дел")
    if court_area:
        parts.append(str(court_area).strip())
    if year:
        parts.append(str(year))
    return " ".join(parts).strip()


def _read_docs(paths):
    """Читает все docx-описи."""
    return [read_inventory_docx(p) for p in paths]


def build_stats(flow, prepared) -> dict:
    """Блок статистики после конвертации (решение 23)."""
    rows = prepared.get("rows", [])
    cases = [r["case"] for r in rows if r.get("case")]
    skipped = [a for a in prepared.get("attention", [])
               if a.get("action") == "строка пропущена"]
    return {
        "files": len(flow.get("files", [])),
        "type": flow.get("type", ""),
        "type_word": _type_word(flow.get("type", "")),
        "year": prepared.get("year") or flow.get("year"),
        "count": len(rows),
        "first": cases[0] if cases else None,
        "last": cases[-1] if cases else None,
        "skipped": len(skipped),
        "attention": len(prepared.get("attention", [])),
        "names": flow.get("files", []),
    }


def preview_rows(prepared, limit=12) -> list:
    """Первые строки для предпросмотра (C/D/E/G/H)."""
    out = []
    for r in prepared.get("rows", [])[:limit]:
        out.append({
            "C": r.get("C", ""), "D": r.get("D", ""),
            "E": "" if r.get("E") is None else r.get("E"),
            "G": r.get("G", ""), "H": r.get("H", ""),
        })
    return out


def attention_rows(attention) -> list:
    """Записи «Требует внимания» для UI."""
    return [{
        "file": a.get("file", ""),
        "word_row": a.get("word_row", ""),
        "number": a.get("number", ""),
        "reason": a.get("reason", ""),
        "action": a.get("action", ""),
    } for a in attention]


def _save_uploads(upload_dir) -> list:
    """Сохраняет все .docx из формы; возвращает пути."""
    os.makedirs(upload_dir, exist_ok=True)
    paths = []
    for f in request.files.getlist("files"):
        if not f or not f.filename:
            continue
        if not f.filename.lower().endswith(".docx"):
            raise InventoryError(f"Ожидается файл .docx: «{f.filename}»")
        path = os.path.join(upload_dir, os.path.basename(f.filename))
        f.save(path)
        paths.append(path)
    return paths


def _analyze(docx_paths, flow_year=None) -> dict:
    """Читает docx и собирает поток (без записи)."""
    docs = _read_docs(docx_paths)
    flow = build_flow(docs, flow_year=flow_year)
    prepared = prepare_rows(flow)
    return {"flow": flow, "prepared": prepared}


def _resolve_output(output_dir, base, form):
    """
    Имя и путь выходного файла; конфликт -> (None, None, response409).

    form: download/overwrite/copy (как в /convert/xlsx_to_word).
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{base}.xlsx"
    out_path = os.path.join(output_dir, filename)
    overwrite = form.get("overwrite") == "1"
    copy_mode = form.get("copy") == "1"

    if os.path.exists(out_path) and not (overwrite or copy_mode):
        resp = (jsonify({"error": "Файл уже существует",
                         "filename": filename, "conflict": True}), 409)
        return None, None, resp

    if copy_mode and os.path.exists(out_path):
        i = 1
        while True:
            cand = f"{base} ({i}).xlsx"
            cand_path = os.path.join(output_dir, cand)
            if not os.path.exists(cand_path):
                return cand, cand_path, None
            i += 1
    return filename, out_path, None


def register_routes(app, dirs_getter):
    """Регистрирует роуты модуля на Flask-приложении."""

    @app.route("/inventory_page")
    def inventory_page():
        return render_template("inventory.html")

    @app.route("/inventory/inspect", methods=["POST"])
    def inventory_inspect():
        """
        Предварительный анализ: docx-файлы -> тип, год, счётчики, превью.
        Форма: files (несколько .docx), year (опц.).
        """
        _, upload_dir = dirs_getter()
        try:
            paths = _save_uploads(upload_dir)
            if not paths:
                return _json_error("Загрузите хотя бы один .docx")
            year_raw = request.form.get("year", "").strip()
            flow_year = int(year_raw) if year_raw.isdigit() else None
            data = _analyze(paths, flow_year=flow_year)
        except InventoryError as exc:
            return _json_error(str(exc))
        except Exception as exc:  # noqa: BLE001
            return _json_error(f"Ошибка анализа: {exc}", 500)

        flow, prepared = data["flow"], data["prepared"]
        plan = flow.get("stream", {}).get("year_plan", {})
        return jsonify({
            "stats": build_stats(flow, prepared),
            "preview": preview_rows(prepared),
            "attention": attention_rows(prepared.get("attention", [])),
            "needs_choice": bool(plan.get("needs_choice")),
            "years": plan.get("attention", []),
        })

    @app.route("/inventory/convert", methods=["POST"])
    def inventory_convert():
        """
        Конвертация Word-описей в лист «Таблица» шаблона.

        Форма: template (.xlsx), files (несколько .docx), court_area,
        name (опц.), year (опц.), download/overwrite/copy.
        """
        output_dir, upload_dir = dirs_getter()
        if not request.files.get("template"):
            return _json_error("Загрузите шаблон .xlsx")
        template = request.files["template"]
        if not template.filename or \
                not template.filename.lower().endswith(".xlsx"):
            return _json_error("Шаблон должен быть .xlsx")

        os.makedirs(upload_dir, exist_ok=True)
        tpl_path = os.path.join(upload_dir,
                                os.path.basename(template.filename))
        template.save(tpl_path)

        court_area = request.form.get("court_area", "").strip()
        year_raw = request.form.get("year", "").strip()
        flow_year = int(year_raw) if year_raw.isdigit() else None

        try:
            paths = _save_uploads(upload_dir)
            if not paths:
                return _json_error("Загрузите хотя бы один .docx")
            data = _analyze(paths, flow_year=flow_year)
        except InventoryError as exc:
            return _json_error(str(exc))
        except Exception as exc:  # noqa: BLE001
            return _json_error(f"Ошибка анализа: {exc}", 500)

        flow, prepared = data["flow"], data["prepared"]
        base = (request.form.get("name", "").strip()
                or default_name(flow.get("type", ""), court_area,
                                prepared.get("year")))
        filename, out_path, err = _resolve_output(
            output_dir, base, request.form)
        if err is not None:
            return err
        assert out_path is not None

        try:
            write_result(tpl_path, flow, out_path)
        except InventoryError as exc:
            return _json_error(str(exc))
        except Exception as exc:  # noqa: BLE001
            return _json_error(f"Ошибка конвертации: {exc}", 500)

        if request.form.get("download") == "1":
            return send_file(out_path, as_attachment=True,
                             download_name=filename)

        return jsonify({
            "filename": filename,
            "stats": build_stats(flow, prepared),
            "preview": preview_rows(prepared),
            "attention": attention_rows(prepared.get("attention", [])),
        })
