# fix_49a_01
import pytest
from court_case_app.core.inventory_editor.model import Doc
from court_case_app.core.inventory_editor.validator import (
    validate_all, validate_unique_cases, validate_prefixes,
    InventoryValidationError,
)


def test_ok_two_cases():
    validate_all([Doc("X", "2", 105, 2019, 1),
                  Doc("Y", "2", 106, 2019, 1)])


def test_conflict_prefix_same_case():
    with pytest.raises(InventoryValidationError):
        validate_all([Doc("X", "2", 105, 2019, 1),
                      Doc("Y", "2a", 105, 2019, 1)])


def test_ok_other_prefixes():
    validate_all([Doc("X", "2", 105, 2019, 1),
                  Doc("Y", "2a", 106, 2019, 1),
                  Doc("Z", "5", 107, 2019, 1)])


def test_ok_same_case_number_different_year():
    validate_all([Doc("X", "2", 105, 2019, 1),
                  Doc("Y", "2", 105, 2020, 1)])
