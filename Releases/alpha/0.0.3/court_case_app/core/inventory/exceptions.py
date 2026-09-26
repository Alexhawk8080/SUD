# -*- coding: utf-8 -*-
"""
Типы ошибок модуля «Внутренняя опись» (Word -> лист «Таблица»).

Роуты /inventory/* ловят InventoryError и возвращают 400
с текстом исключения. Прочие (unexpected) ошибки — 500.

Наследники ConverterError не используются: модуль «Внутренняя опись» —
самостоятельный конвейер со своим набором ожидаемых ошибок.
"""


class InventoryError(Exception):
    """Базовое исключение модуля «Внутренняя опись» (ожидаемые ошибки -> 400)."""


class BadInventoryFileError(InventoryError):
    """Файл не удалось открыть как docx (битый, не zip, нет ключевого XML)."""


class NoInventoryTableError(InventoryError):
    """В docx не найдено ни одной таблицы описи (№ п/п | Наименование | Номера листов)."""


class FlowBreakError(InventoryError):
    """Разрыв потока: конец одного docx не стыкуется с началом другого."""


class MixedTypesError(InventoryError):
    """В одном потоке смешаны административные и гражданские дела."""


class TemplateError(InventoryError):
    """Ошибка шаблона Excel (лист «Таблица» и т.п.)."""


class TemplateSheetNotFound(TemplateError):
    """В шаблоне нет листа строго с именем «Таблица»."""
