# stage_40
# -*- coding: utf-8 -*-
"""
Логирование расхождений VBA vs таксономия (C-сценарий, вариант D).

Гибридный режим:
  * построчный лог — только первые LIMIT_PER_KEY строк на ключ (vba, tax, group);
  * summary-файл — счётчики и топ-категория для каждой пары.

Файлы (в корне проекта, gitignored):
  taxonomy_prefix_diff.log          — построчный (RotatingFileHandler 2 МБ x 3)
  taxonomy_prefix_diff_summary.log  — перезаписывается целиком
  taxonomy_retention_diff.log
  taxonomy_retention_diff_summary.log

Сброс состояния — reset() (закрывает handlers, удаляет построчные логи,
очищает счётчики).
"""
from __future__ import annotations

import atexit
import logging
from collections import Counter, defaultdict
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .category_taxonomy import get_group


ROOT = Path(__file__).resolve().parent.parent.parent

# Сколько построчных строк на ключ (vba, tax, group).
LIMIT_PER_KEY = 50

_prefix_logger = None
_retention_logger = None


def _make_logger(name, filename):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = RotatingFileHandler(
        ROOT / filename,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s\t%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(handler)
    return logger


def _prefix():
    global _prefix_logger
    if _prefix_logger is None:
        _prefix_logger = _make_logger(
            "taxonomy_prefix_diff", "taxonomy_prefix_diff.log")
    return _prefix_logger


def _retention():
    global _retention_logger
    if _retention_logger is None:
        _retention_logger = _make_logger(
            "taxonomy_retention_diff", "taxonomy_retention_diff.log")
    return _retention_logger


# ключ: (vba, tax, group); значение: Counter[category]
_prefix_stats = defaultdict(Counter)
_retention_stats = defaultdict(Counter)

# сколько строк уже выведено в построчный лог на ключ
_prefix_written = Counter()
_retention_written = Counter()


def reset():
    """Сброс: закрыть построчные логгеры, удалить их файлы, очистить счётчики."""
    global _prefix_logger, _retention_logger
    for logger in (_prefix_logger, _retention_logger):
        if logger:
            for h in list(logger.handlers):
                try:
                    h.close()
                    logger.removeHandler(h)
                except Exception:
                    pass
    _prefix_logger = None
    _retention_logger = None
    for name in ("taxonomy_prefix_diff.log", "taxonomy_retention_diff.log"):
        p = ROOT / name
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    _prefix_stats.clear()
    _retention_stats.clear()
    _prefix_written.clear()
    _retention_written.clear()


def log_prefix_diff(case_num, category, vba_prefix, tax_prefix):
    if not tax_prefix or tax_prefix == vba_prefix:
        return
    group = get_group(category) or "-"
    key = (vba_prefix, tax_prefix, group)
    _prefix_stats[key][category] += 1
    if _prefix_written[key] < LIMIT_PER_KEY:
        _prefix_written[key] += 1
        _prefix().info(
            "case=%s\tvba=%r\ttax=%r\tcategory=%r",
            case_num, vba_prefix, tax_prefix, category,
        )


def log_retention_diff(case_num, category, vba_retention, tax_retention):
    if not tax_retention or tax_retention == vba_retention:
        return
    group = get_group(category) or "-"
    key = (vba_retention, tax_retention, group)
    _retention_stats[key][category] += 1
    if _retention_written[key] < LIMIT_PER_KEY:
        _retention_written[key] += 1
        _retention().info(
            "case=%s\tvba=%r\ttax=%r\tcategory=%r",
            case_num, vba_retention, tax_retention, category,
        )


def _dump_summary(path: Path, title: str, stats: dict) -> None:
    lines = [
        f"# {title}",
        "# vba \t tax \t group \t count \t top_category \t top_count",
    ]
    items = []
    for key, cat_counter in stats.items():
        total = sum(cat_counter.values())
        if not cat_counter or total == 0:
            continue
        top_cat, top_cnt = cat_counter.most_common(1)[0]
        items.append((total, key, top_cat, top_cnt))
    items.sort(reverse=True)
    for total, (vba, tax, group), top_cat, top_cnt in items:
        lines.append(
            f"{vba}\t{tax}\t{group}\t{total}\t{top_cat}\t{top_cnt}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary():
    """Записать оба summary-файла."""
    _dump_summary(
        ROOT / "taxonomy_prefix_diff_summary.log",
        "taxonomy_prefix_diff_summary.log",
        _prefix_stats,
    )
    _dump_summary(
        ROOT / "taxonomy_retention_diff_summary.log",
        "taxonomy_retention_diff_summary.log",
        _retention_stats,
    )


atexit.register(write_summary)
