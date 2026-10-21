"""Reads the first sheet of an Excel (.xlsx), CSV or HTML-table file into header and rows."""

import csv
import io
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
from py_common.errors import AppError

XLSX_MAGIC = b"PK\x03\x04"  # .xlsx files are zip archives
XLS_MAGIC = b"\xd0\xcf\x11\xe0"  # old binary .xls format (Excel 97-2003)
MAX_COLUMNS = 80

Cell = str | int | float | bool | date | datetime | None


@dataclass(frozen=True)
class SheetRow:
    number: int  # row number as shown by Excel (the header is row 1 or later)
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class Sheet:
    headers: tuple[str, ...]
    rows: tuple[SheetRow, ...]


def _is_empty(cell: Any) -> bool:
    return cell is None or (isinstance(cell, str) and not cell.strip())


def _cell(value: object) -> Cell:
    """Excel values reduced to the kinds the import understands."""
    if value is None or isinstance(value, str | bool | int | float | date):
        return value
    if isinstance(value, Decimal):
        return float(value)
    return str(value)  # rich text, times, formulas without a cached value


def _limited(rows: Iterable[tuple[Cell, ...]], limit: int) -> list[tuple[Cell, ...]]:
    """Stops reading once more than `limit` non-empty rows are found (huge files)."""
    kept: list[tuple[Cell, ...]] = []
    filled = 0
    for row in rows:
        kept.append(row)
        if not all(_is_empty(c) for c in row):
            filled += 1
            if filled > limit:
                break
    return kept


def _xlsx_rows(data: bytes, limit: int) -> list[tuple[Cell, ...]]:
    try:
        # read_only streams the sheet; data_only returns computed values instead of formulas.
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as exc:
        raise AppError("The file is not a valid Excel file", code="invalid_file") from exc
    try:
        sheet = workbook.worksheets[0]
        rows = (
            tuple(_cell(value) for value in row)
            for row in sheet.iter_rows(max_col=MAX_COLUMNS, values_only=True)
        )
        return _limited(rows, limit)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError, SyntaxError) as exc:
        raise AppError("The file is not a valid Excel file", code="invalid_file") from exc
    finally:
        workbook.close()


def _decode(data: bytes) -> str:
    """UTF-8 when valid, otherwise the Windows encoding used by Italian Excel exports."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _csv_rows(data: bytes, limit: int) -> list[tuple[Cell, ...]]:
    text = _decode(data)
    if "\x00" in text:
        raise AppError("The file is not a valid Excel or CSV file", code="invalid_file")
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(
            text[:4096], delimiters=";,\t"
        )
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    return _limited((tuple(row[:MAX_COLUMNS]) for row in reader), limit)


# Elements without a closing tag: they never contain text.
VOID_TAGS = {"br", "img", "input", "meta", "link", "hr", "col", "wbr", "source", "area", "base"}


class _TableParser(HTMLParser):
    """Rows of the first HTML table, with the visible text of each cell."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[Cell, ...]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._hidden: list[bool] = []  # one entry per open element
        self._tables = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._tables += 1
        if self._tables != 1:
            return
        if tag not in VOID_TAGS:
            style = (dict(attrs).get("style") or "").replace(" ", "").lower()
            parent_hidden = bool(self._hidden and self._hidden[-1])
            self._hidden.append(parent_hidden or "display:none" in style)
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self._tables == 1 and tag not in VOID_TAGS and self._hidden:
            self._hidden.pop()
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(tuple(self._row[:MAX_COLUMNS]))
            self._row = None
        elif tag == "table":
            self._tables += 1  # only the first table is read

    def handle_data(self, data: str) -> None:
        if self._cell is not None and not (self._hidden and self._hidden[-1]):
            self._cell.append(data)


def _is_html(data: bytes) -> bool:
    """Web-based software often exports an HTML table saved with the .xls extension."""
    start = data[:4096].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    return start.startswith(b"<") and (b"<table" in start or b"<html" in start)


def _html_rows(data: bytes, limit: int) -> list[tuple[Cell, ...]]:
    text = _decode(data)
    parser = _TableParser()
    parser.feed(text)
    parser.close()
    if not parser.rows:
        raise AppError("The file is not a valid Excel or CSV file", code="invalid_file")
    return _limited(iter(parser.rows), limit)


def read_spreadsheet(data: bytes, max_rows: int) -> Sheet:
    """First non-empty row is the header; fully empty rows are skipped."""
    if data.startswith(XLS_MAGIC):
        raise AppError(
            "Old .xls files are not supported: save the file as .xlsx",
            code="xls_not_supported",
        )
    limit = max_rows + 1  # header included
    if data.startswith(XLSX_MAGIC):
        raw = _xlsx_rows(data, limit)
    elif _is_html(data):
        raw = _html_rows(data, limit)
    else:
        raw = _csv_rows(data, limit)

    numbered = [
        (index + 1, row) for index, row in enumerate(raw) if not all(_is_empty(c) for c in row)
    ]
    if not numbered:
        raise AppError("The file is empty", code="empty_file")
    _, header_cells = numbered[0]
    headers = tuple("" if _is_empty(c) else str(c).strip() for c in header_cells)
    # Excel pads rows to the widest one: drop the empty columns on the right.
    while headers and not headers[-1]:
        headers = headers[:-1]
    body = numbered[1:]
    if not body:
        raise AppError("The file contains no listings", code="empty_file")
    if len(body) > max_rows:
        raise AppError(
            f"Too many rows: at most {max_rows} listings per file",
            code="too_many_rows",
            details={"max": max_rows},
        )
    width = len(headers)
    rows = tuple(
        SheetRow(number=number, cells=tuple(cells[:width]) + (None,) * (width - len(cells)))
        for number, cells in body
    )
    return Sheet(headers=headers, rows=rows)


def write_spreadsheet(headers: list[str], rows: list[list[Cell]]) -> bytes:
    """A one-sheet .xlsx file, used for the import template."""
    workbook = Workbook()
    sheet = workbook.create_sheet("Immobili", 0)
    for extra in workbook.worksheets[1:]:
        workbook.remove(extra)
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    for index, header in enumerate(headers, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = max(14, len(header) + 4)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
