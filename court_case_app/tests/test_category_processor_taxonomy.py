# stage_37
# -*- coding: utf-8 -*-
"""Тесты таксономических гипотез prefix/retention (C-сценарий)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.category_processor_taxonomy import (
    PREFIX_BY_GROUP,
    RETENTION_BY_GROUP,
    taxonomy_prefix,
    taxonomy_retention,
)
from core.category_taxonomy import CANON_RULES


def test_all_groups_have_prefix_hypothesis():
    """Каждая канон-группа должна иметь гипотезу prefix."""
    for name, _ in CANON_RULES:
        assert name in PREFIX_BY_GROUP, f"Нет гипотезы prefix для {name!r}"


def test_prefix_values_are_valid():
    for group, val in PREFIX_BY_GROUP.items():
        assert val in ("по иску", "по заявлению"), (
            f"Недопустимый prefix {val!r} для {group!r}")


def test_retention_hypotheses_subset_of_groups():
    """Гипотезы retention — только для подмножества групп."""
    assert len(RETENTION_BY_GROUP) <= len(CANON_RULES)


def test_taxonomy_prefix_real_samples():
    cases = [
        ("Споры, связанные с жилищными отношениями о взыскании платы за жилую площадь", "по иску"),
        ("Споры, связанные с имущественными правами иски о взыскании сумм по договору займа", "по иску"),
        ("о взыскании денежных сумм в счет уплаты установленных законом обязательных платежей", "по заявлению"),
        ("Отношения, связанные с защитой прав потребителей о защите прав потребителей", "по иску"),
        ("Споры, возникающие из семейных правоотношений о расторжении брака", "по иску"),
        ("Споры, возникающие из пенсионных отношений из нарушений пенсионного законодательства", "по заявлению"),
        ("Дела особого производства прочие дела особого производства", "по заявлению"),
    ]
    failures = []
    for text, expected in cases:
        actual = taxonomy_prefix(text)
        if actual != expected:
            failures.append(f"  {text!r}\n    ожидалось: {expected!r}\n    получено:  {actual!r}")
    assert not failures, "Не прошли:\n" + "\n".join(failures)


def test_taxonomy_retention_real_samples():
    cases = [
        ("Споры, связанные с жилищными отношениями о взыскании платы", "3 года Ст. 227"),
        ("о взыскании денежных сумм в счет уплаты обязательных платежей", "3 года Ст. 221"),
        ("Отношения, связанные с защитой прав потребителей о защите", "3 года ЭПК Ст. 208"),
        ("Споры, возникающие из пенсионных отношений", "5 лет ЭПК Ст. 203"),
    ]
    failures = []
    for text, expected in cases:
        actual = taxonomy_retention(text)
        if actual != expected:
            failures.append(f"  {text!r}\n    ожидалось: {expected!r}\n    получено:  {actual!r}")
    assert not failures, "Не прошли:\n" + "\n".join(failures)


def test_taxonomy_returns_none_for_unknown():
    assert taxonomy_prefix("совершенно непонятная строка") is None
    assert taxonomy_retention("совершенно непонятная строка") is None
    assert taxonomy_prefix(None) is None
    assert taxonomy_retention(None) is None


def test_taxonomy_retention_returns_none_for_groups_without_hypothesis():
    """Семейные — нет гипотезы (алименты vs развод различаются)."""
    assert taxonomy_retention(
        "Споры, возникающие из семейных правоотношений о расторжении брака") is None
    assert taxonomy_retention(
        "Споры, связанные с земельными отношениями другие споры") is None
