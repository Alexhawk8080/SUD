# -*- coding: utf-8 -*-
"""
Тесты склонения ФИО (Этап 2). Сверка с VBA-логикой и примерами из акта.

Запуск: .venv\\Scripts\\python.exe court_case_app\\tests\\test_names.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.genitive import genitive_case, get_genitive_exception, surname_to_genitive
from core.dative import dative_case, get_dative_exception, surname_to_dative
from core.names_utils import is_male, masculinize_surname, parse_full_name

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


def test_parse():
    print("\n[1] Парсинг ФИО")
    check("ФИО полностью",
          parse_full_name("Саркисян Юлия Геннадьевна"),
          ("Саркисян", "", "Юлия", "Геннадьевна"))
    check("Старая фамилия в скобках",
          parse_full_name("Иванов (Петрова) Иван Иванович"),
          ("Иванов", "Петрова", "Иван", "Иванович"))
    check("Оглы",
          parse_full_name("Алиев Али оглы"),
          ("Алиев", "", "Али", "оглы"))
    check("Кызы",
          parse_full_name("Каримова Айгуль кызы"),
          ("Каримова", "", "Айгуль", "кызы"))
    check("Без отчества",
          parse_full_name("Иванов Иван"),
          ("Иванов", "", "Иван", ""))
    check("Только фамилия",
          parse_full_name("Иванов"),
          ("Иванов", "", "", ""))


def test_sex():
    print("\n[2] Определение пола")
    check("Мужчина (…ич)", is_male("Иванович"), True)
    check("Женщина (…на)", is_male("Геннадьевна"), False)
    check("Женщина (кызы)", is_male("кызы"), False)
    check("Оглы — мужчина", is_male("оглы"), True)


def test_masculinize():
    print("\n[3] Маскулинизация фамилий")
    check("ова -> ов", masculinize_surname("Голованова"), "Голованов")
    check("ева -> ев", masculinize_surname("Смирнева"), "Смирнев")
    check("ина -> ин", masculinize_surname("Никитина"), "Никитин")
    check("ская -> ский", masculinize_surname("Троицкая"), "Троицкий")
    check("ая -> ый", masculinize_surname("Белая"), "Белый")
    check("яя -> ий (ж/ш/ч/щ)", masculinize_surname("Хорошая"), "Хороший")


def test_genitive():
    print("\n[4] Родительный падеж (сверка с актом и VBA)")
    check("Саркисян Юлия Геннадьевна",
          genitive_case("Саркисян Юлия Геннадьевна"),
          "Саркисян Юлии Геннадьевны")
    check("Орехова Людмила Николаевна",
          genitive_case("Орехова Людмила Николаевна"),
          "Ореховой Людмилы Николаевны")
    check("Сурков Эдуард Владимирович",
          genitive_case("Сурков Эдуард Владимирович"),
          "Суркова Эдуарда Владимировича")
    check("Чернова Наталья Олеговна",
          genitive_case("Чернова Наталья Олеговна"),
          "Черновой Натальи Олеговны")
    check("Китаева Наталья Александровна",
          genitive_case("Китаева Наталья Александровна"),
          "Китаевой Натальи Александровны")
    check("Суздальцева Юлия Михайловна",
          genitive_case("Суздальцева Юлия Михайловна"),
          "Суздальцевой Юлии Михайловны")
    check("Зверева Галина Евгеньевна",
          genitive_case("Зверева Галина Евгеньевна"),
          "Зверевой Галины Евгеньевны")
    check("Маскулинизация: Голованова Владимир Валерьевич",
          genitive_case("Голованова Владимир Валерьевич"),
          "Голованова Владимира Валерьевича")
    check("Старая фамилия в скобках",
          genitive_case("Иванов (Петрова) Иван Иванович"),
          "Иванова (Петрова) Ивана Ивановича")
    check("Оглы не склоняется",
          genitive_case("Алиев Али оглы"),
          "Алиева Али Оглы")
    check("Исключение: Павел",
          genitive_case("Петров Павел Петрович"),
          "Петрова Павла Петровича")
    check("Исключение: Лев",
          genitive_case("Толстой Лев Николаевич"),
          "Толстого Льва Николаевича")
    check("Исключение: Пётр",
          genitive_case("Петров Пётр Иванович"),
          "Петрова Петра Ивановича")
    check("Исключение: Любовь",
          genitive_case("Иванова Любовь Андреевна"),
          "Ивановой Любови Андреевны")


def test_dative():
    print("\n[5] Дательный падеж (сверка с актом и VBA)")
    check("Саркисян Юлия Геннадьевна",
          dative_case("Саркисян Юлия Геннадьевна"),
          "Саркисян Юлии Геннадьевне")
    check("Саркисян Давид Сергеевич",
          dative_case("Саркисян Давид Сергеевич"),
          "Саркисяну Давиду Сергеевичу")
    check("Орехов Игорь Анатольевич",
          dative_case("Орехов Игорь Анатольевич"),
          "Орехову Игорю Анатольевичу")
    check("Гринчева Оксана Геннадьевна",
          dative_case("Гринчева Оксана Геннадьевна"),
          "Гринчевой Оксане Геннадьевне")
    check("Суздальцева Юлия Михайловна",
          dative_case("Суздальцева Юлия Михайловна"),
          "Суздальцевой Юлии Михайловне")
    check("Маскулинизация: Голованова Владимир Валерьевич",
          dative_case("Голованова Владимир Валерьевич"),
          "Голованову Владимиру Валерьевичу")
    check("Старая фамилия в скобках",
          dative_case("Иванов (Петрова) Иван Иванович"),
          "Иванову (Петрову) Ивану Ивановичу")
    check("Оглы не склоняется",
          dative_case("Алиев Али оглы"),
          "Алиеву Али Оглы")
    check("Исключение: Павел",
          dative_case("Петров Павел Петрович"),
          "Петрову Павлу Петровичу")
    check("Исключение: Лев",
          dative_case("Толстой Лев Николаевич"),
          "Толстому Льву Николаевичу")
    check("Исключение: Пётр",
          dative_case("Петров Пётр Иванович"),
          "Петрову Петру Ивановичу")


def test_exceptions():
    print("\n[6] Функции исключений")
    check("GetGenitiveException Павел", get_genitive_exception("Павел"), "Павла")
    check("GetDativeException Павел", get_dative_exception("Павел"), "Павлу")
    check("GetGenitiveException Али (не склоняется)", get_genitive_exception("Али"), "Али")
    check("Нет исключения", get_genitive_exception("Иван"), "")


def test_surname_rules():
    print("\n[7] Правила склонения фамилий (SurnameToGenitive/SurnameToDative)")
    check("Ген: Иванов (м)", surname_to_genitive("Иванов", True), "Иванова")
    check("Ген: Белый (м)", surname_to_genitive("Белый", True), "Белого")
    check("Ген: Толстой (м)", surname_to_genitive("Толстой", True), "Толстого")
    check("Ген: Дрозд (м)", surname_to_genitive("Дрозд", True), "Дрозда")
    check("Ген: Гончаренко (м, неизмен.)", surname_to_genitive("Гончаренко", True), "Гончаренко")
    check("Ген: Черных (м, неизмен.)", surname_to_genitive("Черных", True), "Черных")
    check("Ген: Иванова (ж)", surname_to_genitive("Иванова", False), "Ивановой")
    check("Ген: Саркисян (ж, неизмен.)", surname_to_genitive("Саркисян", False), "Саркисян")
    check("Дат: Иванов (м)", surname_to_dative("Иванов", True), "Иванову")
    check("Дат: Белый (м)", surname_to_dative("Белый", True), "Белому")
    check("Дат: Толстой (м)", surname_to_dative("Толстой", True), "Толстому")
    check("Дат: Дрозд (м)", surname_to_dative("Дрозд", True), "Дрозду")
    check("Дат: Иванова (ж)", surname_to_dative("Иванова", False), "Ивановой")
    check("Дат: Гринчева (ж)", surname_to_dative("Гринчева", False), "Гринчевой")


if __name__ == "__main__":
    test_parse()
    test_sex()
    test_masculinize()
    test_genitive()
    test_dative()
    test_exceptions()
    test_surname_rules()
    print(f"\nИТОГО: пройдено {PASSED}, ошибок {FAILED}")
    sys.exit(1 if FAILED else 0)