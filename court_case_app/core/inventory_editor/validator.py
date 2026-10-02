# fix_49a_01
"""Валидация описи: (year, case_number) уникально, prefix согласован."""
from __future__ import annotations
from typing import List, Dict
from .model import Doc


class InventoryValidationError(ValueError):
    pass


def validate_unique_cases(docs: List[Doc]) -> None:
    seen: Dict[tuple, str] = {}
    for d in docs:
        key = (d.year, d.case_number)
        if key in seen and seen[key] != d.prefix:
            raise InventoryValidationError(
                f"Дело {d.prefix}-{d.case_number}/{d.year} уже существует "
                f"с префиксом '{seen[key]}'."
            )
        seen[key] = d.prefix


def validate_prefixes(docs: List[Doc]) -> None:
    seen: Dict[tuple, str] = {}
    for d in docs:
        key = (d.year, d.case_number)
        if key in seen and seen[key] != d.prefix:
            raise InventoryValidationError(
                f"Внутри дела {key} разные префиксы: "
                f"'{seen[key]}' и '{d.prefix}'."
            )
        seen[key] = d.prefix


def validate_all(docs: List[Doc]) -> None:
    validate_unique_cases(docs)
    validate_prefixes(docs)
