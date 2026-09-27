# -*- coding: utf-8 -*-
"""
Окно-пульт управления сервером «Акт уничтожения гражданских дел».

Запускает court_case_app/app.py в отдельном процессе. Позволяет:
    * открыть веб-интерфейс в браузере;
    * перезапустить сервер (если упал или завис);
    * остановить сервер;
    * наблюдать последние события в журнале (stdout + stderr сервера);
    * открыть файл server_errors.log.

Запуск:
    .venv\\Scripts\\pythonw.exe launcher.py
или двойной клик по start.bat.
"""

import atexit
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk
except ImportError:
    print("tkinter не установлен. Установите python3-tk или полный Python.")
    sys.exit(1)

BASE = Path(__file__).resolve().parent
APP_PY = BASE / "court_case_app" / "app.py"
LOG_PATH = BASE / "court_case_app" / "server_errors.log"
SERVER_URL = "http://127.0.0.1:5000"


def get_python_executable() -> str:
    """Возвращает интерпретатор .venv, либо текущий."""
    if os.name == "nt":
        venv_py = BASE / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = BASE / ".venv" / "bin" / "python"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def is_port_in_use(port: int = 5000, host: str = "127.0.0.1") -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def http_check(url: str, timeout: float = 1.0) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False


# ============================================================================
# Окно-пульт
# ============================================================================

class LauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.proc: subprocess.Popen = None
        self.python = get_python_executable()
        self._stopping = False
        self._starting_at = 0.0

        root.title("Акт уничтожения гражданских дел — управление сервером")
        root.geometry("720x520")
        root.minsize(560, 420)

        # --- Шапка со статусом ---
        header = ttk.Frame(root, padding=(14, 12, 14, 8))
        header.pack(fill="x")

        self.status_var = tk.StringVar(value="⏹ Сервер остановлен")
        self.status_lbl = ttk.Label(
            header, textvariable=self.status_var,
            font=("Segoe UI", 13, "bold"))
        self.status_lbl.pack(anchor="w")

        self.pid_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.pid_var,
                  foreground="#666").pack(anchor="w", pady=(2, 0))

        # --- Кнопки ---
        btns = ttk.Frame(root, padding=(14, 6, 14, 6))
        btns.pack(fill="x")

        self.btn_browser = ttk.Button(
            btns, text="Открыть в браузере",
            command=self.open_browser, width=22)
        self.btn_browser.pack(side="left", padx=(0, 6))

        self.btn_restart = ttk.Button(
            btns, text="Перезапустить сервер",
            command=self.restart_server, width=22)
        self.btn_restart.pack(side="left", padx=6)

        self.btn_stop = ttk.Button(
            btns, text="Остановить",
            command=self.stop_server, width=14)
        self.btn_stop.pack(side="left", padx=6)

        self.btn_log = ttk.Button(
            btns, text="Открыть логи",
            command=self.open_logs, width=14)
        self.btn_log.pack(side="right")

        # --- Журнал ---
        ttk.Label(root, text="Последние события:",
                  padding=(14, 8, 14, 2)).pack(anchor="w")
        log_frame = ttk.Frame(root, padding=(14, 0, 14, 12))
        log_frame.pack(fill="both", expand=True)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=18, wrap="word",
            font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        # --- Завершение ---
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        # fix_32: страховка — если launcher завершится не через on_close,
        # atexit всё равно остановит сервер.
        atexit.register(self._atexit_stop)

        # --- Периодическая проверка статуса ---
        self.root.after(500, self._poll_status)

        # --- Автостарт ---
        self.root.after(200, self.auto_start)

    # -----------------------------------------------------------------
    # Журнал
    # -----------------------------------------------------------------

    def log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"{ts}  {msg}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # -----------------------------------------------------------------
    # Запуск / остановка
    # -----------------------------------------------------------------

    def auto_start(self):
        if self.proc is not None and self.proc.poll() is None:
            self.log("Сервер уже запущен.")
            return
        if is_port_in_use(5000):
            self.log("Порт 5000 занят — возможно, сервер уже работает.")
            self._update_status_from_http()
            return
        self.start_server()

    def start_server(self):
        if self.proc is not None and self.proc.poll() is None:
            self.log("Уже запущен (PID=%d)." % self.proc.pid)
            return
        if not APP_PY.exists():
            self.log("НЕ НАЙДЕН: %s" % APP_PY)
            return
        if is_port_in_use(5000):
            self.log("Порт 5000 уже занят другим процессом.")
            self._update_status_from_http()
            return

        self.log("Запуск сервера: %s %s" % (self.python, APP_PY.name))
        self._starting_at = time.time()

        creationflags = 0
        if os.name == "nt":
            # Скрываем окно консоли дочернего процесса.
            # CREATE_NO_WINDOW — у дочернего процесса не будет своего окна;
            # CREATE_NEW_PROCESS_GROUP — при остановке можно убить его вместе
            # с потомками (taskkill /T).
            creationflags = (subprocess.CREATE_NO_WINDOW |
                             subprocess.CREATE_NEW_PROCESS_GROUP)

        # fix_32: передаём серверу env-переменные:
        #   NO_WATCHDOG=1  — не слушать heartbeat (нет вкладки),
        #                    вместо этого следить за нашим PID;
        #   PARENT_PID     — чтобы сервер знал, чей PID проверять.
        child_env = os.environ.copy()
        child_env["COURT_CASE_NO_WATCHDOG"] = "1"
        child_env["COURT_CASE_PARENT_PID"] = str(os.getpid())

        try:
            self.proc = subprocess.Popen(
                [self.python, str(APP_PY)],
                cwd=str(BASE / "court_case_app"),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                bufsize=1,
                creationflags=creationflags,
                env=child_env,
            )
        except Exception as exc:
            self.log("ОШИБКА запуска: %s" % exc)
            self.proc = None
            return

        self.log("Процесс запущен, PID=%d" % self.proc.pid)

        # Поток чтения stdout
        threading.Thread(target=self._read_stdout,
                         args=(self.proc,), daemon=True).start()

    def _read_stdout(self, proc):
        try:
            for line in proc.stdout:
                line = line.rstrip("\n")
                if line:
                    self.root.after(0, self.log, line)
        except Exception:
            pass
        # Дождаться РЕАЛЬНОГО завершения процесса. Если поток stdout
        # закрылся раньше (ошибка чтения), процесс может быть ещё жив —
        # не сбрасываем self.proc, пока proc.wait() не вернёт код.
        try:
            proc.wait()
        except Exception:
            pass
        self.root.after(0, self._on_proc_exit)

    def _on_proc_exit(self):
        if self.proc is None:
            return
        rc = self.proc.poll()
        if rc is None:
            # Процесс ещё жив (была ошибка в потоке чтения) — оставляем.
            return
        self.log("Процесс завершился, код=%s" % rc)
        self.proc = None

    def stop_server(self):
        if self.proc is None or self.proc.poll() is not None:
            self.log("Сервер не запущен.")
            self._update_status_from_http()
            return
        self.log("Остановка сервера (PID=%d)…" % self.proc.pid)
        self._stopping = True
        pid = self.proc.pid

        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                               capture_output=True)
            else:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        except Exception as exc:
            self.log("Ошибка остановки: %s" % exc)
        finally:
            self.proc = None
            self._stopping = False
            self.log("Сервер остановлен.")
            self._update_status_from_http()

    def restart_server(self):
        self.log("Перезапуск сервера…")
        self.stop_server()
        self.root.after(800, self._after_stop_for_restart)

    def _after_stop_for_restart(self):
        # подождать освобождения порта
        for _ in range(10):
            if not is_port_in_use(5000):
                break
            time.sleep(0.3)
            self.root.update()
        self.start_server()

    # -----------------------------------------------------------------
    # Прочее
    # -----------------------------------------------------------------

    def open_browser(self):
        webbrowser.open(SERVER_URL)
        self.log("Открываю %s" % SERVER_URL)

    def open_logs(self):
        # Ищем первый существующий лог из списка
        candidates = [
            LOG_PATH,                              # server_errors.log
           #BASE / "test_error.log",               # ошибки тестов
           #BASE / "test.log",                     # полный лог тестов
           #BASE / "server_test.log",              # старый лог сервера
        ]
        target = next((c for c in candidates if c.exists()), None)

        # Если ни один не найден — открываем папку проекта
        if target is None:
            self.log("Файлы логов ещё не созданы — открываю папку проекта.")
            try:
                if os.name == "nt":
                    os.startfile(str(BASE))  # noqa: S606
                else:
                    subprocess.Popen(["xdg-open", str(BASE)])
            except Exception as exc:
                messagebox.showerror("Ошибка", "Не удалось открыть:\n%s" % exc)
            return

        self.log("Открываю лог: %s" % target.name)
        try:
            if os.name == "nt":
                os.startfile(str(target))  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:
            messagebox.showerror("Ошибка", "Не удалось открыть:\n%s" % exc)

    # -----------------------------------------------------------------
    # Периодическая проверка статуса
    # -----------------------------------------------------------------

    def _poll_status(self):
        self._update_status_from_http()
        self._update_buttons()
        self.root.after(1500, self._poll_status)

    def _update_status_from_http(self):
        running = self.proc is not None and self.proc.poll() is None
        port_open = is_port_in_use(5000)
        http_ok = False
        if port_open:
            http_ok = http_check(SERVER_URL, timeout=0.6)

        if http_ok:
            self.status_var.set("🟢 Сервер работает")
        elif running and (time.time() - self._starting_at) < 20:
            self.status_var.set("🟡 Сервер запускается…")
        elif running:
            self.status_var.set("🟡 Процесс запущен, сервер не отвечает")
        else:
            self.status_var.set("🔴 Сервер остановлен")

        if running:
            self.pid_var.set("PID: %d   ·   %s" % (self.proc.pid, SERVER_URL))
        else:
            self.pid_var.set(SERVER_URL)

    def _update_buttons(self):
        running = self.proc is not None and self.proc.poll() is None
        state_stop = "normal" if running else "disabled"
        state_restart = "normal"
        self.btn_stop.configure(state=state_stop)
        self.btn_restart.configure(state=state_restart)

    # -----------------------------------------------------------------
    # Закрытие
    # -----------------------------------------------------------------

    def on_close(self):
        """
        fix_32: при закрытии окна launcher всегда останавливаем сервер
        перед выходом.
        """
        running = self.proc is not None and self.proc.poll() is None
        if running:
            if not messagebox.askyesno(
                    "Закрытие",
                    "Закрыть окно управления?\n"
                    "Сервер будет остановлен."):
                return
            self.log("Закрытие окна — останавливаю сервер.")
            self.stop_server()
        self.root.destroy()

    def _atexit_stop(self):
        """Страховка: добить дочерний процесс при выходе Python."""
        try:
            if self.proc is not None and self.proc.poll() is None:
                pid = self.proc.pid
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True)
                else:
                    try:
                        self.proc.terminate()
                        self.proc.wait(timeout=3)
                    except Exception:
                        try:
                            self.proc.kill()
                        except Exception:
                            pass
        except Exception:
            pass


def main():
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
