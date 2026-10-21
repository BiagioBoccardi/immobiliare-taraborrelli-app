"""Excel import of listings: preview with the problems found, and result."""

from typing import Literal

from pydantic import BaseModel

from app.models.enums import Contract


class ImportIssue(BaseModel):
    """A problem in a row. `code` is translated by the admin panel."""

    code: str
    column: str | None = None  # header as written in the file
    field: str | None = None  # property field it refers to
    value: str | None = None  # the value found, when useful to fix it


class ImportColumn(BaseModel):
    header: str
    field: str  # property field, or "features.<feature>" for a yes/no feature column


class ImportRowOut(BaseModel):
    row: int  # row number as shown by Excel
    action: Literal["create", "update", "invalid"]
    external_ref: str | None
    title: str | None
    municipality: str | None
    contract: Contract | None
    price: int | None
    errors: list[ImportIssue]
    warnings: list[ImportIssue]


class ImportTotals(BaseModel):
    create: int
    update: int
    invalid: int


class ImportPreview(BaseModel):
    columns: list[ImportColumn]
    ignored_columns: list[str]
    missing_columns: list[str]  # required fields with no column in the file
    rows: list[ImportRowOut]
    totals: ImportTotals


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int  # rows with errors, not imported
