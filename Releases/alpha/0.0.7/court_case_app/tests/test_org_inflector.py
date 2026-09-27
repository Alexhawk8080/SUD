# -*- coding: utf-8 -*-
"""
Тесты склонения родовых слов в названиях организаций (org_inflector.py).

Запуск: .venv\\Scripts\\python.exe court_case_app\\tests\\test_org_inflector.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.org_inflector import inflect_organization_name  # noqa: E402

FAILED = 0
PASSED = 0


def check(name: str, actual: str, expected: str):
    global FAILED, PASSED
    ok = actual == expected
    if ok:
        PASSED += 1
        print(f"  OK   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}\n       ожидалось: {expected!r}\n       получено:  {actual!r}")


def test_genitive():
    print("\n[1] Родительный падеж (заявители)")
    check("Администрация города",
          inflect_organization_name("Администрация города", "Genitive"),
          "Администрации города")
    check("Государственное учреждение (первый компонент)",
          inflect_organization_name("Государственное учреждение - Управление ПФР", "Genitive"),
          "Государственного учреждения - Управление ПФР")
    check("Муниципальное унитарное предприятие с кавычками",
          inflect_organization_name('Муниципальное унитарное предприятие "Водоканал"', "Genitive"),
          'Муниципального унитарного предприятия "Водоканал"')
    check("Закрытое акционерное общество",
          inflect_organization_name('Закрытое акционерное общество "Х"', "Genitive"),
          'Закрытого акционерного общества "Х"')
    check("Банк с кавычками",
          inflect_organization_name('Банк "Открытие"', "Genitive"),
          'Банка "Открытие"')


def test_dative():
    print("\n[2] Дательный падеж (ответчики)")
    check("Администрация города",
          inflect_organization_name("Администрация города", "Dative"),
          "Администрации города")
    check("Общество с ограниченной ответственностью",
          inflect_organization_name('Общество с ограниченной ответственностью "Ромашка"', "Dative"),
          'Обществу с ограниченной ответственностью "Ромашка"')


def test_abbreviations():
    print("\n[3] Аббревиатуры и названия в кавычках не склоняются")
    for s in ['ООО "Сеть Связной"', 'АО "МАКС"', 'ПАО «Сбербанк России»',
              "ИП Иванов", "СБЕРБАНК", "НАО", "МФК «Займер»", "ГК"]:
        check(repr(s) + " (род.)",
              inflect_organization_name(s, "Genitive"), s)
    check("Только кавычки",
          inflect_organization_name('«Связной»', "Genitive"),
          '«Связной»')


def test_edge_cases():
    print("\n[4] Граничные случаи")
    check("Пустая строка", inflect_organization_name("", "Genitive"), "")
    check("None", inflect_organization_name(None, "Genitive"), "")
    check("Предлог перед аббревиатурой",
          inflect_organization_name('По ООО "Х"', "Genitive"),
          'По ООО "Х"')


if __name__ == "__main__":
    test_genitive()
    test_dative()
    test_abbreviations()
    test_edge_cases()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)