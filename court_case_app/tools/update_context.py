# -*- coding: utf-8 -*-
"""
Служебный скрипт: обновление context.md после завершения этапа.

Отмечает этап в блоке «Текущее состояние» и добавляет запись в
«История обновлений».

Использование:
    python tools/update_context.py "Этап N. Название" "Текст записи"
"""

import sys
import os
from datetime import date

CONTEXT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "context.md")


def main() -> int:
    if len(sys.argv) < 3:
        print("Использование: update_context.py \"Этап N. Название\" \"Текст записи\"")
        return 1

    stage_label = sys.argv[1].strip()
    note_text = sys.argv[2].strip()

    with open(CONTEXT_PATH, encoding="utf-8") as f:
        content = f.read()

    today = date.today().strftime("%Y-%m-%d")

    # 1. Отметка этапа в «Текущее состояние» (перед строкой «- [ ] Остальные этапы»)
    marker = "- [ ] Остальные этапы — см. `Plan.md`"
    entry = f"- [x] {stage_label}\n"
    if marker in content and entry not in content:
        content = content.replace(marker, entry + marker)

    # 2. Запись в «История обновлений» (первой строкой после заголовка)
    history_header = "## История обновлений\n\n"
    log_line = f"- **{today} ({stage_label})**: {note_text}\n"
    if history_header in content and log_line not in content:
        content = content.replace(history_header, history_header + log_line)

    with open(CONTEXT_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"context.md обновлён: {stage_label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())