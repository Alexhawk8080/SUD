# -*- coding: utf-8 -*-
"""
fix_34_update_docs.py — обновление context.md и Plan.md по итогам
итерации 0.0.7: launcher, watchdog в parent-mode, логирование,
единый формат имени файла, создание участка/года из сайдбара.

Идемпотентен по маркеру «0.0.7».

Запуск:
    .venv\\Scripts\\python.exe fix_34_update_docs.py
"""

import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONTEXT = BASE / "context.md"
PLAN = BASE / "Plan.md"

TODAY = date.today().strftime("%Y-%m-%d")
MARKER = "0.0.7"


# ============================================================================
# context.md
# ============================================================================

CTX_STATE_ANCHOR = "- [ ] Остальные этапы — см. `Plan.md`"

CTX_STATE_ADD = f"""- [x] **fix_23–fix_27** (логирование + launcher): server_errors.log, server_console.log, CreateNoWindow для дочернего процесса, open_logs ищет первый существующий лог, корректный статус процесса
- [x] **fix_25–fix_26** (имя файла акта): единый `core/filename_utils.make_act_filename` — «Акт уничтожения гражданских дел 3 CУ 2020.docx»; JS разбирает `filename*` из Content-Disposition, а не ASCII-fallback
- [x] **fix_28–fix_33** (стабилизация): import logging, base-leftovers, устойчивые тесты, env NO_WATCHDOG + PARENT_PID
- [x] **stage16d6f** (UI создания): кнопки «+ Участок» и «+ Год» в сайдбаре с модалкой
- [x] **stage16d6g** (launcher.py): окно-пульт с кнопками «Открыть браузер» / «Перезапустить» / «Остановить» / «Открыть логи», живой лог, atexit-страховка
- [x] **fix_32** (watchdog parent-mode): при запуске из launcher heartbeat-watchdog отключается; вместо него parent-watchdog следит за PID launcher и завершает сервер через 2 с после пропажи родителя
- [x] Релиз **{MARKER}** собран: `Releases/alpha/{MARKER}/`
- [ ] {CTX_STATE_ANCHOR[4:]}
"""


CTX_HISTORY_HEADER = "## История обновлений\n\n"

CTX_HISTORY_ENTRY = (
    f"- **{TODAY} (fix_23–fix_34, релиз {MARKER})**: Стабилизация после "
    f"D1–D6. **Логирование.** `fix_23`→`fix_27`: `app.py` пишет в "
    f"`court_case_app/server_errors.log` (RotatingFileHandler, 2 МБ×3); "
    f"`sys.excepthook` / `threading.excepthook` перехватывают "
    f"необработанные исключения; watchdog логирует причину остановки; "
    f"Tee-обёртка stdout/stderr пишет всё в `server_console.log`. "
    f"**Launcher.** `stage16d6g` создаёт `launcher.py` — окно-пульт на "
    f"tkinter: статус (🟢/🟡/🔴), кнопки «Открыть в браузере» / "
    f"«Перезапустить сервер» / «Остановить» / «Открыть логи», живой лог "
    f"stdout, автостоп при закрытии окна через `atexit` + `taskkill`. "
    f"`fix_24`: `CREATE_NO_WINDOW` скрывает консоль дочернего `app.py`; "
    f"`open_logs` ищет первый существующий лог (server_errors → "
    f"test_error → test → server_test) или открывает папку проекта; "
    f"`_read_stdout` ждёт `proc.wait()` (корректный статус). "
    f"**Watchdog parent-mode** (`fix_32`): launcher передаёт дочернему "
    f"env-переменные `COURT_CASE_NO_WATCHDOG=1` и "
    f"`COURT_CASE_PARENT_PID=<pid>`; `app.py` вместо heartbeat-watchdog "
    f"запускает parent-watchdog (проверка живости родителя через "
    f"`OpenProcess` / `os.kill(pid, 0)`, раз в 2 с). Сервер больше не "
    f"умирает через 120 с без вкладки, но корректно завершается при "
    f"закрытии окна-пульта. **Единый формат имени файла** "
    f"(`fix_25`/`fix_26`): создан `core/filename_utils.make_act_filename` "
    f"— «Акт уничтожения гражданских дел 3 CУ 2020.docx» / "
    f"«…административных дел 5 CУ 2019.xlsx»; `pipeline.py`, "
    f"`db_pipeline.py`, `app.py` используют его; в `year_page.js` "
    f"добавлен `parseContentDisposition`, который сначала ищет "
    f"`filename*=UTF-8''…`, а не ASCII-fallback от werkzeug. "
    f"**fix_28–fix_33**: `import logging` в `app.py`; удалены остатки "
    f"f\"{{base}}\" в `pipeline.py`; тесты стали устойчивы к точному "
    f"формату имени (проверяют «есть 3 и 2020», а не «есть 3 CУ»); "
    f"`test_launcher_files.py` обновлён под fix_32. "
    f"**UI создания** (`stage16d6f`): в сайдбаре — кнопка «+ Участок» и "
    f"hover-кнопка «+» у каждого участка для добавления года; модалка с "
    f"опцией «Скопировать реквизиты из [год]». "
    f"Тесты: **51 модуль, все OK**. Релиз **{MARKER}** в "
    f"`Releases/alpha/{MARKER}/`.\n"
)


def patch_context() -> bool:
    if not CONTEXT.exists():
        print(f"НЕ НАЙДЕН: {CONTEXT}")
        return False
    text = CONTEXT.read_text(encoding="utf-8")
    if f"релиз {MARKER}" in text and "fix_23–fix_34" in text:
        print(f"УЖЕ ОБНОВЛЁН: {CONTEXT.relative_to(BASE)}")
        return True

    changed = False
    if CTX_STATE_ANCHOR in text:
        if "fix_23–fix_27" not in text:
            text = text.replace(CTX_STATE_ANCHOR, CTX_STATE_ADD, 1)
            changed = True
    else:
        print(f"  предупреждение: не найден маркер «Остальные этапы» "
              f"в {CONTEXT.name}")

    if CTX_HISTORY_HEADER in text and CTX_HISTORY_ENTRY not in text:
        text = text.replace(CTX_HISTORY_HEADER,
                            CTX_HISTORY_HEADER + CTX_HISTORY_ENTRY, 1)
        changed = True

    if changed:
        CONTEXT.write_text(text, encoding="utf-8")
        print(f"ОБНОВЛЁН: {CONTEXT.relative_to(BASE)}")
    return True


# ============================================================================
# Plan.md
# ============================================================================

PLAN_PROGRESS_ANCHOR = "| 11. Сборка .exe |"

PLAN_PROGRESS_ADD = (
    f"| fix_23–fix_27 (логирование + launcher) | ✅ Выполнены | {TODAY} | "
    "server_errors.log, server_console.log, launcher.py |\n"
    f"| fix_25–fix_26 (формат имени акта) | ✅ Выполнены | {TODAY} | "
    "core/filename_utils.py, Content-Disposition JS |\n"
    f"| fix_28–fix_33 (стабилизация) | ✅ Выполнены | {TODAY} | "
    "import logging, base-leftovers, устойчивые тесты |\n"
    f"| fix_32 (watchdog parent-mode) | ✅ Выполнен | {TODAY} | "
    "env NO_WATCHDOG + PARENT_PID, parent-watchdog |\n"
    f"| stage16d6f (UI создания участка/года) | ✅ Выполнен | {TODAY} | "
    "кнопки + модалка в сайдбаре |\n"
    f"| stage16d6g (launcher.py) | ✅ Выполнен | {TODAY} | "
    "окно-пульт на tkinter |\n"
    f"| **Релиз {MARKER}** | ✅ Собран | {TODAY} | "
    "Releases/alpha/" + MARKER + "/ |\n"
)

PLAN_SECTION_ANCHOR = "### Этап 11. Сборка в .exe — [ ] НЕ ВЫПОЛНЕН"

PLAN_SECTION_ADD = f"""### Итерация 0.0.7: launcher, watchdog parent-mode, логирование — [x] ВЫПОЛНЕНО ({TODAY})

**Логирование сервера:**
- `app.py` пишет в `court_case_app/server_errors.log` (RotatingFileHandler, 2 МБ × 3).
- `sys.excepthook` / `threading.excepthook` — необработанные исключения.
- Watchdog логирует причину `os._exit(0)`.
- Tee-обёртка stdout/stderr → `server_console.log` (HTTP-строки werkzeug, print).

**Launcher (`launcher.py` + `start.bat` + `run_app.pyw`):**
- Окно-пульт на tkinter: статус, PID, кнопки «Открыть в браузере» / «Перезапустить сервер» / «Остановить» / «Открыть логи», живой лог.
- Автостарт сервера при открытии; автообнаружение падения каждые 1.5 с.
- При закрытии окна — остановка сервера + `atexit`-страховка + `taskkill /T`.
- `CREATE_NO_WINDOW` — консоль дочернего `app.py` скрыта.
- `open_logs` ищет первый существующий лог или открывает папку проекта.

**Watchdog parent-mode (`fix_32`):**
- launcher передаёт дочернему `COURT_CASE_NO_WATCHDOG=1`, `COURT_CASE_PARENT_PID=<pid>`.
- `app.py` в этом режиме запускает parent-watchdog (проверка живости родителя раз в 2 с).
- Поведение: сервер живёт без вкладки, пока живёт launcher; завершается через ~2 с после пропажи родителя.
- Обычный запуск `app.py` (без launcher) сохраняет heartbeat-watchdog с таймаутом 120 с.

**Единый формат имени файла:**
- `core/filename_utils.make_act_filename` — «Акт уничтожения гражданских дел 3 CУ 2020.docx».
- `pipeline.py`, `db_pipeline.py`, `app.py` — используют его.
- `year_page.js::parseContentDisposition` — сначала `filename*` (UTF-8), потом `filename=` (fallback).

**UI создания (`stage16d6f`):**
- Кнопка «+ Участок» в футере сайдбара.
- Hover-кнопка «+» рядом с участком — добавить год.
- Модалка с опцией «Скопировать реквизиты из [год]».

**Тесты:** 51 модуль, все OK.

**Релиз:** `Releases/alpha/{MARKER}/`.

---

"""


def patch_plan() -> bool:
    if not PLAN.exists():
        print(f"НЕ НАЙДЕН: {PLAN}")
        return False
    text = PLAN.read_text(encoding="utf-8")
    if f"Релиз {MARKER}" in text and "Итерация 0.0.7" in text:
        print(f"УЖЕ ОБНОВЛЁН: {PLAN.relative_to(BASE)}")
        return True

    changed = False
    if PLAN_PROGRESS_ANCHOR in text:
        if "fix_23–fix_27" not in text:
            text = text.replace(PLAN_PROGRESS_ANCHOR,
                                PLAN_PROGRESS_ADD + PLAN_PROGRESS_ANCHOR, 1)
            changed = True
    else:
        print(f"  предупреждение: не найден маркер таблицы в {PLAN.name}")

    if PLAN_SECTION_ANCHOR in text:
        if "### Итерация 0.0.7" not in text:
            text = text.replace(PLAN_SECTION_ANCHOR,
                                PLAN_SECTION_ADD + PLAN_SECTION_ANCHOR, 1)
            changed = True
    else:
        print(f"  предупреждение: не найден «Этап 11» в {PLAN.name}")

    if changed:
        PLAN.write_text(text, encoding="utf-8")
        print(f"ОБНОВЛЁН: {PLAN.relative_to(BASE)}")
    return True


def main() -> int:
    print("fix_34: обновление context.md и Plan.md (0.0.7)")
    print("=" * 60)
    ok1 = patch_context()
    print()
    ok2 = patch_plan()
    print()
    if not (ok1 and ok2):
        print("ЧТО-ТО НЕ ПРИМЕНЕНО. Проверьте сообщения выше.")
        return 1
    print("Готово. Дальше:")
    print("  .venv\\Scripts\\python.exe release_0_0_7_generate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())