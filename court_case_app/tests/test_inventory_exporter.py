# stage_49b
import openpyxl
from court_case_app.core.inventory_editor.model import Doc
from court_case_app.core.inventory_editor.exporter import export_to_excel


def _mk_template(tmp_path, data_rows: int):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Таблица"
    for i in range(data_rows):
        r = 4 + i
        # Заглушки-формулы в A/B/F/I/J (как в реальном шаблоне).
        ws.cell(r, 1).value = 1
        ws.cell(r, 2).value = 1
        ws.cell(r, 7).value = 9999        # «старый» год — должен быть перезаписан
    p = tmp_path / "tpl.xlsx"
    wb.save(p)
    return str(p)


def test_writes_all_input_cells(tmp_path):
    tpl = _mk_template(tmp_path, 10)
    out = str(tmp_path / "out.xlsx")
    docs = [
        Doc("Приказ", "2", 105, 2019, 1),
        Doc("Определение", "2а", 106, 2019, 2),
    ]
    info = export_to_excel(docs, tpl, out)
    assert info["rows"] == 2
    assert info["tail_zeroed"] == 8
    wb = openpyxl.load_workbook(out)
    ws = wb["Таблица"]
    assert ws.cell(4, 3).value == "Приказ"
    assert ws.cell(4, 4).value == "2"
    assert ws.cell(4, 5).value == 105     # E первой строки = case_number
    assert ws.cell(4, 7).value == 2019
    assert ws.cell(4, 8).value == 1
    assert ws.cell(5, 3).value == "Определение"
    assert ws.cell(5, 4).value == "2а"
    assert ws.cell(5, 5).value == 1       # E второй строки = 106-105
    assert ws.cell(5, 8).value == 2


def test_tail_G_zeroed(tmp_path):
    tpl = _mk_template(tmp_path, 5)
    out = str(tmp_path / "out.xlsx")
    docs = [Doc("A", "2", 1, 2019, 1)]
    export_to_excel(docs, tpl, out)
    wb = openpyxl.load_workbook(out)
    ws = wb["Таблица"]
    # Строки 5..8 — хвост, G=0
    for r in range(5, 9):
        assert ws.cell(r, 7).value == 0


def test_does_not_touch_other_columns(tmp_path):
    tpl = _mk_template(tmp_path, 3)
    out = str(tmp_path / "out.xlsx")
    export_to_excel([Doc("X", "2", 10, 2019, 1)], tpl, out)
    wb = openpyxl.load_workbook(out)
    ws = wb["Таблица"]
    # A/B в строке 4 — не изменились (остались 1/1 заглушки).
    assert ws.cell(4, 1).value == 1
    assert ws.cell(4, 2).value == 1


def test_too_many_rows_raises(tmp_path):
    tpl = _mk_template(tmp_path, 2)
    out = str(tmp_path / "out.xlsx")
    docs = [Doc(f"D{i}", "2", i + 1, 2019, 1) for i in range(5)]
    import pytest
    with pytest.raises(ValueError):
        export_to_excel(docs, tpl, out)
