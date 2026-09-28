# stage_40
# -*- coding: utf-8 -*-
"""Тесты гибридного логирования taxonomy_diff (вариант D)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import taxonomy_diff as td


def _flush():
    import logging
    for name in ("taxonomy_prefix_diff", "taxonomy_retention_diff"):
        for h in logging.getLogger(name).handlers:
            try:
                h.flush()
            except Exception:
                pass


def test_build_line_limiting_and_summary():
    td.reset()
    for i in range(100):
        td.log_prefix_diff(
            f"2-{i}/2020",
            "Споры, связанные с жилищными отношениями о взыскании платы",
            "по заявлению", "по иску")
    _flush()

    log_path = td.ROOT / "taxonomy_prefix_diff.log"
    assert log_path.exists(), "построчный лог не создан"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert len(lines) == td.LIMIT_PER_KEY, (
        f"ожидалось {td.LIMIT_PER_KEY} строк, получено {len(lines)}")

    td.write_summary()
    sum_path = td.ROOT / "taxonomy_prefix_diff_summary.log"
    assert sum_path.exists(), "summary не создан"
    text = sum_path.read_text(encoding="utf-8")
    assert "\t100\t" in text, f"счётчик 100 не найден:\n{text}"


def test_diff_keys_are_separate():
    td.reset()
    for i in range(60):
        td.log_retention_diff(
            f"2-{i}/2020",
            "Споры, связанные с жилищными отношениями о взыскании платы",
            "3 года Ст. 179", "3 года Ст. 227")
    for i in range(60):
        td.log_retention_diff(
            f"3-{i}/2020",
            "о взыскании денежных сумм обязательных платежей",
            "3 года Ст. 227", "3 года Ст. 221")
    td.write_summary()

    text = (td.ROOT / "taxonomy_retention_diff_summary.log").read_text(
        encoding="utf-8")
    assert text.count("\t60\t") == 2, (
        f"ожидалось две пары со счётчиком 60:\n{text}")


def test_no_write_when_equal():
    td.reset()
    td.log_prefix_diff("2-1/2020", "категория", "по иску", "по иску")
    td.log_prefix_diff("2-2/2020", "категория", "по иску", None)
    td.write_summary()
    text = (td.ROOT / "taxonomy_prefix_diff_summary.log").read_text(
        encoding="utf-8")
    body = [ln for ln in text.splitlines()
            if ln.strip() and not ln.startswith("#")]
    assert not body, f"не ожидалось строк данных:\n{text}"


def test_reset_clears_stats_and_files():
    td.reset()
    td.log_prefix_diff("2-1/2020", "жилищные споры о взыскании",
                       "по заявлению", "по иску")
    assert td._prefix_stats, "статистика не заполнена"
    td.reset()
    assert not td._prefix_stats, "reset не очистил статистику"
    log_path = td.ROOT / "taxonomy_prefix_diff.log"
    assert not log_path.exists(), "reset не удалил построчный лог"
