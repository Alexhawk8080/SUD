# -*- coding: utf-8 -*-
"""
Утилиты работы с текстом (fix_10_v2).

sanitize_text() приводит любые варианты переносов строк и артефакты
Word/Excel к единому представлению \n.

Варианты, которые встречаются в реальных данных:
    _x000D_   — литеральный escape CR (Word/Excel)
    \r\n      — Windows-перенос
    \r        — Mac-перенос / CR
    \v        — vertical tab (Excel)
"""

import re

# Регистронезависимо ищем _x000D_ / _x000d_
_ESCAPE_CR_RE = re.compile(r"_x000[dD]_")


def sanitize_text(value):
    """
    Возвращает строку с нормализованными переносами строк.

    Не-строки и None возвращаются без изменений.
    """
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    s = _ESCAPE_CR_RE.sub("\n", value)
    s = s.replace("\r\n", "\n")
    s = s.replace("\r", "\n")
    s = s.replace("\v", "\n")
    return s
