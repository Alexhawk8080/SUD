# stage_43
# -*- coding: utf-8 -*-
"""
Общий conftest для тестов court_case_app.

Добавляет в sys.path:
  * court_case_app/   — чтобы работал импорт 'from core.X import ...';
  * корень проекта    — чтобы работал 'from court_case_app.core.X import ...'.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent            # court_case_app/tests
COURT_CASE_APP = HERE.parent            # court_case_app
PROJECT_ROOT = COURT_CASE_APP.parent    # корень проекта

for p in (COURT_CASE_APP, PROJECT_ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
