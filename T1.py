# -*- coding: utf-8 -*-
"""
fix_31_pipeline_base_cleanup.py

Проблема:
    В core/pipeline.py в excel-ветке process_rows остался старый код
        filename = f"{base}.xlsx"
    Переменная `base` больше не определяется (её заменил fix_25 на
    make_act_filename). Это NameError → HTTP 500 при /process с
    format=excel (в т.ч. для file_type=legacy).

Решение:
    1. Удаляем все строки вида `filename = f"{base}.xxx"` — где бы они
       ни остались (regex покрывает .xlsx/.docx и любой суффикс).
    2. Сканируем все .py в court_case_app/ (кроме tests) на остатки
       f-строк с {base} — показываем, если что-то ещё осталось.
    3. По результату — либо всё чисто, либо список «доработать».

Запуск:
    .venv\\Scripts\\python.exe fix_31_pipeline_base_cleanup.py
    .venv\\Scripts\\python.exe run_tests.py
"""

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COURT = BASE_DIR / "court_case_app"
PIPELINE = COURT / "core" / "pipeline.py"


# ---------------------------------------------------------------------------
# 1. Удаление строк filename = f"{base}..." в pipeline.py
# ---------------------------------------------------------------------------

# Строка целиком: только пробелы, `filename = f"{base}..."`
LINE_RE = re.compile(
    r'^[ \t]*filename[ \t]*=[ \t]*f"\{base\}[^"]*"[ \t]*$',
    re.MULTILINE)


def clean_pipeline() -> int:
    if not PIPELINE.exists():
        print(f"  НЕ НАЙДЕН: {PIPELINE.relative_to(BASE_DIR)}")
        return 0
    text = PIPELINE.read_text(encoding="utf-8")

    matches = LINE_RE.findall(text)
    if not matches:
        print(f"  УЖЕ ЧИСТО: {PIPELINE.relative_to(BASE_DIR)}")
        return 0

    new_text = LINE_RE.sub("", text)
    # убираем лишние пустые строки, которые могли остаться (2+ подряд)
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)

    PIPELINE.write_text(new_text, encoding="utf-8")
    print(f"  ИЗМЕНЁН: {PIPELINE.relative_to(BASE_DIR)}")
    for m in matches:
        print(f"          удалено: {m.strip()}")
    return len(matches)


# ---------------------------------------------------------------------------
# 2. Сканирование всех .py в court_case_app/ на остатки {base}
# ---------------------------------------------------------------------------

SCAN_RE = re.compile(r'f"[^"]*\{base\b')
SCAN_RE_TICK = re.compile(r"f'[^']*\{base\b")


def scan_all() -> list:
    hits = []
    for py in COURT.rglob("*.py"):
        if "tests" in py.parts:
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if SCAN_RE.search(line) or SCAN_RE_TICK.search(line):
                rel = py.relative_to(BASE_DIR)
                hits.append((rel, i, line.strip()))
    return hits


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    print("fix_31: очистка остатков f\"{base}\" в pipeline.py")
    print("=" * 64)

    print("[1] До патча — сканирование файлов на f-строки с {base}")
    before = scan_all()
    if before:
        for rel, line_no, text in before:
            print(f"    {rel}:{line_no}  {text}")
    else:
        print("    (ничего не найдено)")

    print("\n[2] Патч core/pipeline.py — удаление filename = f\"{base}.xxx\"")
    n = clean_pipeline()

    print("\n[3] После патча — повторное сканирование")
    after = scan_all()
    if after:
        print("    ОСТАЛОСЬ (возможно, в другом контексте):")
        for rel, line_no, text in after:
            print(f"      {rel}:{line_no}  {text}")
    else:
        print("    Чисто — f-строк с {base} больше нет.")

    print()
    print("=" * 64)
    if after:
        print(f"Внимание: ещё осталось {len(after)} строк. Пришлите их —")
        print("добавлю точечный патч (fix_31_v2.py).")
        return 2
    print("Готово. Все f-строки с {base} удалены ({} шт. в pipeline)."
          .format(n))
    print()
    print("Проверка:")
    print("  .venv\\Scripts\\python.exe court_case_app\\tests\\test_api_convert.py")
    print("  .venv\\Scripts\\python.exe run_tests.py")
    print()
    print("Ожидание: 51 модуль OK, FAIL = 0.")
    return 0


if __name__ == "__main__":
    sys.exit(main())