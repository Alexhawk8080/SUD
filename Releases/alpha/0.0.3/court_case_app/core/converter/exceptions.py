# -*- coding: utf-8 -*-
"""
Типы ошибок конвертации.

Роуты /convert/* и /inspect_file ловят ConverterError и возвращают 400
с текстом исключения. Прочие (unexpected) ошибки — 500.
"""


class ConverterError(Exception):
    """Базовое исключение конвертации (ожидаемые ошибки -> 400)."""


class BadFileError(ConverterError):
    """Файл не удалось открыть как xlsx/docx (битый, не zip, нет ключевого XML)."""


class WrongDirectionError(ConverterError):
    """Расширение файла не соответствует выбранному направлению."""


class NoSheetsFound(ConverterError):
    """В xlsx не найдено ни одного листа."""


class NoValidCaseNumbers(ConverterError):
    """В файле нет ни одного номера вида N-N/YYYY (нельзя определить год)."""


class NoCasesFound(ConverterError):
    """Не найдено ни одной строки с делом (заголовок «Гражданское дело №...»)."""


class SheetNotFound(ConverterError):
    """Запрошенный лист отсутствует в книге."""


class ColumnsNotFound(ConverterError):
    """В таблице не удалось определить обязательные столбцы."""
