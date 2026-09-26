# -*- coding: utf-8 -*-
"""
Общие настройки pytest.

Добавляет court_case_app в sys.path (для импорта core/database),
чтобы будущие pytest-тесты работали без ручных sys.path.insert.
"""

import sys
from pathlib import Path

_COURT_APP = Path(__file__).resolve().parent / "court_case_app"
if str(_COURT_APP) not in sys.path:
    sys.path.insert(0, str(_COURT_APP))
