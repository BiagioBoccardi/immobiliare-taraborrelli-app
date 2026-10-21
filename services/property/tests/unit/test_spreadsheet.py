from datetime import datetime

import pytest
from py_common.errors import AppError

from app.services.spreadsheet import read_spreadsheet, write_spreadsheet
from tests.factories import import_row, spreadsheet_bytes


def test_read_xlsx_returns_headers_and_rows_with_excel_numbers() -> None:
    data = spreadsheet_bytes([import_row(Riferimento="RS-1"), import_row(Riferimento="RS-2")])

    sheet = read_spreadsheet(data, max_rows=10)

    assert sheet.headers[0] == "Riferimento"
    assert [row.number for row in sheet.rows] == [2, 3]
    assert sheet.rows[1].cells[0] == "RS-2"


def test_read_xlsx_keeps_dates_and_numbers() -> None:
    data = write_spreadsheet(["Prezzo", "Disponibile dal"], [[450, datetime(2026, 9, 1)]])

    sheet = read_spreadsheet(data, max_rows=10)

    assert sheet.rows[0].cells == (450, datetime(2026, 9, 1))


def test_read_skips_empty_rows_and_finds_header_below_blank_lines() -> None:
    data = write_spreadsheet([], [[None, None], ["Comune", "Prezzo"], [None], ["Chieti", 1]])

    sheet = read_spreadsheet(data, max_rows=10)

    assert sheet.headers == ("Comune", "Prezzo")
    assert [row.number for row in sheet.rows] == [5]


def test_read_csv_with_semicolons_and_windows_encoding() -> None:
    data = "Comune;Città;Prezzo\nChieti;Chieti;120.000\n".encode("cp1252")

    sheet = read_spreadsheet(data, max_rows=10)

    assert sheet.headers == ("Comune", "Città", "Prezzo")
    assert sheet.rows[0].cells == ("Chieti", "Chieti", "120.000")


def test_read_pads_short_rows_to_header_width() -> None:
    data = b"Comune,Prezzo,Zona\nChieti,1\n"

    sheet = read_spreadsheet(data, max_rows=10)

    assert sheet.rows[0].cells == ("Chieti", "1", None)


def test_read_old_xls_raises_xls_not_supported() -> None:
    with pytest.raises(AppError) as exc_info:
        read_spreadsheet(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100, max_rows=10)

    assert exc_info.value.code == "xls_not_supported"


def test_read_corrupted_xlsx_raises_invalid_file() -> None:
    with pytest.raises(AppError) as exc_info:
        read_spreadsheet(b"PK\x03\x04 not really a zip", max_rows=10)

    assert exc_info.value.code == "invalid_file"


def test_read_binary_garbage_raises_invalid_file() -> None:
    with pytest.raises(AppError) as exc_info:
        read_spreadsheet(b"\x00\x01\x02 binary", max_rows=10)

    assert exc_info.value.code == "invalid_file"


def test_read_header_only_raises_empty_file() -> None:
    with pytest.raises(AppError) as exc_info:
        read_spreadsheet(b"Comune;Prezzo\n", max_rows=10)

    assert exc_info.value.code == "empty_file"


def test_read_more_rows_than_allowed_raises_too_many_rows() -> None:
    data = spreadsheet_bytes([import_row() for _ in range(4)])

    with pytest.raises(AppError) as exc_info:
        read_spreadsheet(data, max_rows=3)

    assert exc_info.value.code == "too_many_rows"
    assert exc_info.value.details == {"max": 3}
