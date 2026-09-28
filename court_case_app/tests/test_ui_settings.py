# stage_42
# -*- coding: utf-8 -*-
"""
Тесты страницы настроек (/settings_page).

Запуск:
    .venv\\Scripts\\python.exe court_case_app\\tests\\test_ui_settings.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as app_module

FAILED = 0
PASSED = 0


def check(name, actual, expected):
    global FAILED, PASSED
    if actual == expected:
        PASSED += 1
        print(f"  OK   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось: {expected!r}\n       получено:  {actual!r}")


def main():
    tmp = tempfile.mkdtemp(prefix="ui_settings_")
    app_module.DB_PATH = os.path.join(tmp, "app.db")
    app_module.OUTPUT_DIR = os.path.join(tmp, "out")
    app_module.UPLOAD_DIR = os.path.join(tmp, "up")
    os.makedirs(app_module.OUTPUT_DIR, exist_ok=True)
    os.makedirs(app_module.UPLOAD_DIR, exist_ok=True)

    client = app_module.app.test_client()

    print("[1] GET /settings_page — 200 + оба toggle")
    r = client.get("/settings_page")
    check("HTTP 200", r.status_code, 200)
    html = r.get_data(as_text=True)
    check("есть set-auto-fix", 'id="set-auto-fix"' in html, True)
    check("есть set-taxonomy-diff", 'id="set-taxonomy-diff"' in html, True)
    check("есть data-key auto_fix_categories",
          'data-key="auto_fix_categories"' in html, True)
    check("есть data-key taxonomy_diff_logging",
          'data-key="taxonomy_diff_logging"' in html, True)
    check("есть кнопка settings-save",
          'id="settings-save"' in html, True)

    print("\n[2] POST /api/settings — сохранение флагов")
    r = client.post("/api/settings",
                    json={"auto_fix_categories": "0",
                          "taxonomy_diff_logging": "1"})
    check("HTTP 200", r.status_code, 200)
    check("ok = True", r.get_json().get("ok"), True)

    print("\n[3] GET /api/settings — значения сохранены")
    r = client.get("/api/settings")
    s = r.get_json()
    check("auto_fix_categories = 0", s.get("auto_fix_categories"), "0")
    check("taxonomy_diff_logging = 1", s.get("taxonomy_diff_logging"), "1")

    print("\n[4] Переключение обратно")
    client.post("/api/settings",
                json={"auto_fix_categories": "1",
                      "taxonomy_diff_logging": "0"})
    r = client.get("/api/settings")
    s = r.get_json()
    check("auto_fix_categories = 1", s.get("auto_fix_categories"), "1")
    check("taxonomy_diff_logging = 0", s.get("taxonomy_diff_logging"), "0")

    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
