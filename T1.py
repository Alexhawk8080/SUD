# -*- coding: utf-8 -*-
"""
fix_24_launcher_fix.py

Правки launcher.py:
    1. Скрыть окно сервера: CREATE_NO_WINDOW в creationflags
       (при запуске через pythonw.exe — вообще без окон;
       при запуске через python.exe консоль родителя не наследуется).
    2. Исправить ложный статус «остановлен»:
       - _read_stdout корректно ждёт proc.wait();
       - _on_proc_exit не сбрасывает self.proc, если poll() вернул None.
    3. «Открыть логи» — ищет server_errors.log → test_error.log →
       test.log → server_test.log → иначе открывает папку проекта.

Запуск:
    .venv\\Scripts\\python.exe fix_24_launcher_fix.py
    .venv\\Scripts\\python.exe run_tests.py
    :: перезапустить launcher (закрыть/открыть start.bat или run_app.pyw)
"""

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
LAUNCHER = BASE / "launcher.py"


# ---------------------------------------------------------------------------
# 1. Патч: скрыть окно сервера
# ---------------------------------------------------------------------------

CREATIONFLAGS_OLD = '''        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP'''

CREATIONFLAGS_NEW = '''        creationflags = 0
        if os.name == "nt":
            # Скрываем окно консоли дочернего процесса.
            # CREATE_NO_WINDOW — у дочернего процесса не будет своего окна;
            # CREATE_NEW_PROCESS_GROUP — при остановке можно убить его вместе
            # с потомками (taskkill /T).
            creationflags = (subprocess.CREATE_NO_WINDOW |
                             subprocess.CREATE_NEW_PROCESS_GROUP)'''


# ---------------------------------------------------------------------------
# 2. Патч: корректная обработка завершения процесса
# ---------------------------------------------------------------------------

READ_STDOUT_OLD = '''    def _read_stdout(self, proc):
        try:
            for line in proc.stdout:
                line = line.rstrip("\\n")
                if line:
                    self.root.after(0, self.log, line)
        except Exception:
            pass
        # Процесс завершился
        self.root.after(0, self._on_proc_exit)

    def _on_proc_exit(self):
        if self.proc is None:
            return
        rc = self.proc.poll()
        self.log("Процесс завершился, код=%s" % rc)
        self.proc = None'''

READ_STDOUT_NEW = '''    def _read_stdout(self, proc):
        try:
            for line in proc.stdout:
                line = line.rstrip("\\n")
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
        self.proc = None'''

READ_STDOUT_OLD_ALT = '''    def _read_stdout(self, proc):
        try:
            for line in proc.stdout:
                line = line.rstrip("\\n")
                if line:
                    self.root.after(0, self.log, line)
        except Exception:
            pass
        # Процесс завершился
        self.root.after(0, self._on_proc_exit)

    def _on_proc_exit(self):
        if self.proc is None:
            return
        rc = self.proc.poll()
        self.log("Процесс завершился, код=%s" % rc)
        self.proc = None'''

READ_STDOUT_NEW_ALT = READ_STDOUT_NEW  # одинаково


# ---------------------------------------------------------------------------
# 3. Патч: улучшить «Открыть логи»
# ---------------------------------------------------------------------------

OPEN_LOGS_OLD = '''    def open_logs(self):
        if not LOG_PATH.exists():
            messagebox.showinfo("Логи", "Файл ещё не создан:\\n%s" % LOG_PATH)
            return
        try:
            if os.name == "nt":
                os.startfile(str(LOG_PATH))  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(LOG_PATH)])
        except Exception as exc:
            messagebox.showerror("Ошибка", "Не удалось открыть:\\n%s" % exc)'''

OPEN_LOGS_NEW = '''    def open_logs(self):
        # Ищем первый существующий лог из списка
        candidates = [
            LOG_PATH,                              # server_errors.log
            BASE / "test_error.log",               # ошибки тестов
            BASE / "test.log",                     # полный лог тестов
            BASE / "server_test.log",              # старый лог сервера
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
                messagebox.showerror("Ошибка", "Не удалось открыть:\\n%s" % exc)
            return

        self.log("Открываю лог: %s" % target.name)
        try:
            if os.name == "nt":
                os.startfile(str(target))  # noqa: S606
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:
            messagebox.showerror("Ошибка", "Не удалось открыть:\\n%s" % exc)'''


# ---------------------------------------------------------------------------
# Патчи
# ---------------------------------------------------------------------------

def _replace(text: str, old: str, new: str, label: str) -> str:
    if new.split("\n")[0] in text and old not in text:
        print(f"  УЖЕ ПРИМЕНЁН: {label}")
        return text
    if old not in text:
        print(f"  НЕ НАЙДЕН: {label}")
        return text
    print(f"  ИЗМЕНЁН: {label}")
    return text.replace(old, new, 1)


def main() -> int:
    print("fix_24: правки launcher.py")
    print("=" * 60)

    if not LAUNCHER.exists():
        print(f"НЕ НАЙДЕН: {LAUNCHER.relative_to(BASE)}")
        return 1

    text = LAUNCHER.read_text(encoding="utf-8")
    original = text

    print("[1] Скрытие окна сервера (CREATE_NO_WINDOW)")
    text = _replace(text, CREATIONFLAGS_OLD, CREATIONFLAGS_NEW,
                    "creationflags")

    print("\n[2] Статус процесса (proc.wait)")
    # попробуем оба варианта
    if READ_STDOUT_OLD in text:
        text = _replace(text, READ_STDOUT_OLD, READ_STDOUT_NEW,
                        "_read_stdout / _on_proc_exit")
    elif READ_STDOUT_OLD_ALT in text:
        text = _replace(text, READ_STDOUT_OLD_ALT, READ_STDOUT_NEW_ALT,
                        "_read_stdout / _on_proc_exit")
    else:
        print("  НЕ НАЙДЕН ни один вариант _read_stdout")

    print("\n[3] Открытие логов (искать первый существующий)")
    text = _replace(text, OPEN_LOGS_OLD, OPEN_LOGS_NEW, "open_logs")

    if text == original:
        print("\nНичего не изменено (все правки уже применены или не найдены).")
        return 0

    LAUNCHER.write_text(text, encoding="utf-8")
    print()
    print("Готово.")
    print()
    print("Перезапустите launcher:")
    print("  * Закрыть окно-пульт (с подтверждением).")
    print("  * Двойной клик по start.bat / run_app.pyw.")
    print()
    print("Что изменилось:")
    print("  1) У дочернего процесса (app.py) больше нет своего окна")
    print("     консоли — его нельзя случайно закрыть.")
    print("  2) Статус в окне корректно показывает «🟢 работает», пока")
    print("     процесс жив, даже если поток чтения stdout прервётся.")
    print("  3) Кнопка «Открыть логи» ищет любой существующий лог")
    print("     (server_errors.log / test_error.log / test.log /")
    print("     server_test.log) или открывает папку проекта.")
    return 0


if __name__ == "__main__":
    sys.exit(main())