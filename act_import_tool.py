#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Инструмент переноса данных Excel → Word-акт (GUI).

Окно tkinter: выбрать Excel с листом «Результат обработки», выбрать Word
с таблицей «1..8», нажать «Перенести». Результат — рядом с Word-файлом
с суффиксом _filled. Оригинал не изменяется.

Не запускает Flask-приложение — самостоятельный инструмент.

Запуск:
    .venv\\Scripts\\pythonw.exe act_import_tool.py
"""

import os
import sys
import threading
import time
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "court_case_app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class ActImportTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Перенос Excel → Word-акт")
        self.root.geometry("800x600")
        self.root.minsize(720, 520)

        self.excel_path = tk.StringVar()
        self.word_path = tk.StringVar()
        self.status = tk.StringVar(value="Выберите файлы и нажмите «Перенести».")
        self.last_output = None
        self.started_at = None

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        tk.Label(
            self.root,
            text="Перенос данных из Excel-результата в Word-акт",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 4))

        tk.Label(
            self.root,
            text=(
                "Из Excel берётся лист «Результат обработки» (столбцы B:H).\n"
                "В Word-таблице с заголовками «1..8» старые строки данных\n"
                "удаляются, вместо них добавляются строки из Excel."
            ),
            justify="left",
            fg="#555",
        ).pack(anchor="w", padx=12, pady=(0, 8))

        frm = tk.Frame(self.root)
        frm.pack(fill="x", **pad)
        frm.columnconfigure(1, weight=1)

        tk.Label(frm, text="Excel-файл (.xlsx):", anchor="w").grid(
            row=0, column=0, sticky="w", pady=4
        )
        tk.Entry(frm, textvariable=self.excel_path).grid(
            row=0, column=1, sticky="ew", padx=6, pady=4
        )
        tk.Button(frm, text="Обзор…", command=self._browse_excel).grid(row=0, column=2, pady=4)

        tk.Label(frm, text="Word-файл (.docx):", anchor="w").grid(
            row=1, column=0, sticky="w", pady=4
        )
        tk.Entry(frm, textvariable=self.word_path).grid(
            row=1, column=1, sticky="ew", padx=6, pady=4
        )
        tk.Button(frm, text="Обзор…", command=self._browse_word).grid(row=1, column=2, pady=4)

        tk.Label(
            self.root,
            text=(
                "Результат сохранится рядом с Word-файлом как "
                "<имя>_filled.docx. Оригинал не изменяется."
            ),
            justify="left",
            fg="#555",
        ).pack(anchor="w", padx=12, pady=(0, 6))

        # --- Кнопки ---
        btns = tk.Frame(self.root)
        btns.pack(fill="x", **pad)

        self.run_btn = tk.Button(btns, text="Перенести", width=16, command=self._run)
        self.run_btn.pack(side="left")

        self.open_btn = tk.Button(
            btns,
            text="Открыть папку с результатом",
            width=28,
            command=self._open_folder,
            state="disabled",
        )
        self.open_btn.pack(side="left", padx=6)

        self.timer_label = tk.Label(btns, text="", fg="#666")
        self.timer_label.pack(side="right")

        # --- Прогрессбар ---
        prog_frame = tk.Frame(self.root)
        prog_frame.pack(fill="x", padx=12, pady=(0, 4))

        self.progress = ttk.Progressbar(
            prog_frame, orient="horizontal", mode="determinate", length=100, maximum=100, value=0
        )
        self.progress.pack(fill="x")

        self.progress_label = tk.Label(self.root, text="", anchor="w", fg="#333")
        self.progress_label.pack(fill="x", padx=12, pady=(0, 6))

        # --- Лог ---
        tk.Label(self.root, text="Лог:", anchor="w").pack(anchor="w", padx=12)

        log_frame = tk.Frame(self.root)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            height=10,
            state="disabled",
            bg="#f7f7f7",
            relief="sunken",
            borderwidth=1,
            font=("Consolas", 9),
        )
        scrollbar = tk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Label(self.root, textvariable=self.status, anchor="w", fg="#333").pack(
            fill="x", padx=12, pady=(0, 10)
        )

    # --- Действия ---
    def _browse_excel(self):
        path = filedialog.askopenfilename(
            title="Выберите Excel-файл",
            initialdir=str(ROOT),
            filetypes=[("Excel", "*.xlsx *.xlsm"), ("Все файлы", "*.*")],
        )
        if path:
            self.excel_path.set(path)

    def _browse_word(self):
        path = filedialog.askopenfilename(
            title="Выберите Word-файл",
            initialdir=str(ROOT),
            filetypes=[("Word", "*.docx"), ("Все файлы", "*.*")],
        )
        if path:
            self.word_path.set(path)

    def _log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _run(self):
        excel = self.excel_path.get().strip()
        word = self.word_path.get().strip()

        if not excel or not os.path.isfile(excel):
            messagebox.showerror("Ошибка", "Выберите существующий Excel-файл.")
            return
        if not excel.lower().endswith((".xlsx", ".xlsm")):
            messagebox.showerror("Ошибка", "Excel-файл должен быть .xlsx или .xlsm.")
            return
        if not word or not os.path.isfile(word):
            messagebox.showerror("Ошибка", "Выберите существующий Word-файл.")
            return
        if not word.lower().endswith(".docx"):
            messagebox.showerror("Ошибка", "Word-файл должен быть .docx.")
            return

        self._log("=" * 60)
        self._log(f"Excel: {excel}")
        self._log(f"Word:  {word}")
        self._log("Старт.")
        self.status.set("Обработка…")
        self.progress_label.config(text="")
        self.progress["value"] = 0
        self.run_btn.config(state="disabled")
        self.open_btn.config(state="disabled")
        self.last_output = None
        self.started_at = time.time()

        threading.Thread(target=self._worker, args=(excel, word), daemon=True).start()
        self._tick_timer()

    def _tick_timer(self):
        if self.started_at is None:
            return
        if str(self.run_btn["state"]) == "normal":
            self.timer_label.config(text="")
            return
        dt = time.time() - self.started_at
        self.timer_label.config(text=f"прошло: {dt:.1f} с")
        self.root.after(200, self._tick_timer)

    def _worker(self, excel, word):
        try:
            from core.converter.excel_to_act import import_excel_to_act

            info = import_excel_to_act(excel, word, on_progress=self._progress_cb)
            self.root.after(0, self._on_success, info)
        except Exception as e:
            tb = traceback.format_exc()
            self.root.after(0, self._on_error, str(e), tb)

    def _progress_cb(self, message, current, total):
        # колбэк приходит из фонового потока — пробрасываем в UI-поток
        self.root.after(0, self._apply_progress, message, current, total)

    def _apply_progress(self, message, current, total):
        self._log(f"    {message}")
        self.status.set(message)
        if total > 0:
            self.progress["maximum"] = total
            self.progress["value"] = current
            self.progress_label.config(text=f"{current} / {total}")
        elif current == 0 and total == 0:
            # этап без счётчика
            self.progress_label.config(text=message)

    def _on_success(self, info):
        self.last_output = info.get("output_path")
        dt = time.time() - self.started_at if self.started_at else 0
        self.started_at = None
        self._log("-" * 60)
        self._log(f"Готово за {dt:.1f} с.")
        self._log(f"  строк перенесено: {info.get('rows_written')}")
        self._log(f"  лист Excel:       {info.get('sheet_used')}")
        self._log(f"  таблица №:        {info.get('table_index')}")
        self._log(f"  сохранено:        {info.get('output_path')}")
        self.status.set(f"Готово. Строк перенесено: {info.get('rows_written')} " f"за {dt:.1f} с.")
        self.run_btn.config(state="normal")
        self.open_btn.config(state="normal")
        messagebox.showinfo(
            "Готово",
            f"Перенесено строк: {info.get('rows_written')}\n"
            f"Время: {dt:.1f} с\n\n"
            f"Файл:\n{info.get('output_path')}",
        )

    def _on_error(self, message, tb):
        self.started_at = None
        self._log("ОШИБКА:")
        self._log(message)
        self._log(tb)
        self.status.set("Ошибка. См. лог.")
        self.run_btn.config(state="normal")
        messagebox.showerror("Ошибка", message)

    def _open_folder(self):
        if not self.last_output:
            return
        folder = os.path.dirname(os.path.abspath(self.last_output))
        try:
            if os.name == "nt":
                os.startfile(folder)
            elif sys.platform == "darwin":
                os.system(f'open "{folder}"')
            else:
                os.system(f'xdg-open "{folder}"')
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))


def main():
    root = tk.Tk()
    root.withdraw()
    try:
        from core.converter.excel_to_act import import_excel_to_act  # noqa
    except Exception as e:
        root.deiconify()
        messagebox.showerror(
            "Ошибка импорта",
            f"Не удалось импортировать core.converter.excel_to_act:\n\n{e}\n\n"
            f"Проверьте, что запускаете из корня проекта D:\\Python\\SUD.",
        )
        return 1
    root.deiconify()
    ActImportTool(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
