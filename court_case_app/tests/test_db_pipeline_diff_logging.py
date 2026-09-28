# stage_38
# -*- coding: utf-8 -*-
"""Тест: process_cases с diff_logging=True пишет taxonomy_*_diff.log."""
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.case_processor import process_cases

ROOT = Path(__file__).resolve().parent.parent.parent
PREFIX_LOG = ROOT / "taxonomy_prefix_diff.log"


def _flush_prefix_logger():
    for h in logging.getLogger("taxonomy_prefix_diff").handlers:
        try:
            h.flush()
        except Exception:
            pass


def _row(case_number, category):
    return {
        "case_number": case_number,
        "date": None,
        "end_date": None,
        "category": category,
        "applicants": "Иванов Иван Иванович",
        "respondents": "Петров Петр Петрович",
        "opis_number": None,
        "unit_number": None,
        "note": None,
    }


def test_diff_logging_true_writes_line():
    if PREFIX_LOG.exists():
        PREFIX_LOG.unlink()
    rows = [_row("2-1/2020",
                 "Споры, связанные с жилищными отношениями о взыскании платы")]
    process_cases(rows, 2020, False, {}, [], diff_logging=True)
    _flush_prefix_logger()
    assert PREFIX_LOG.exists(), "taxonomy_prefix_diff.log не создан"
    text = PREFIX_LOG.read_text(encoding="utf-8")
    assert "case=2-1/2020" in text, f"case=2-1/2020 нет в логе:\n{text}"
    assert "tax='по иску'" in text, f"tax='по иску' нет в логе:\n{text}"


def test_diff_logging_false_does_not_write_for_case():
    """При diff_logging=False конкретное дело в лог не попадает."""
    rows = [_row("2-999/2020",
                 "Споры, связанные с жилищными отношениями о взыскании платы")]
    process_cases(rows, 2020, False, {}, [], diff_logging=False)
    _flush_prefix_logger()
    if PREFIX_LOG.exists():
        text = PREFIX_LOG.read_text(encoding="utf-8")
        assert "case=2-999/2020" not in text, (
            f"case=2-999/2020 появился в логе при diff_logging=False:\n{text}")
