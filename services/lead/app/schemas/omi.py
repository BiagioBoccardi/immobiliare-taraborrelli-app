from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

OmiWarningCode = Literal[
    "zone_without_perimeter",  # quoted zone with no polygon: no estimate for its addresses
    "perimeter_without_quotes",  # a polygon with no residential quotation
    "semester_mismatch",  # the files are of different semesters
    "rows_skipped",  # rows that could not be read
]


class OmiWarning(BaseModel):
    code: OmiWarningCode
    count: int
    examples: list[str] = []


class OmiImportOut(BaseModel):
    """The OMI data in use: semester and coverage."""

    model_config = ConfigDict(from_attributes=True)

    semester: str
    quotes: int
    zones: int
    municipalities: list[str]
    imported_at: datetime


class OmiImportResult(OmiImportOut):
    warnings: list[OmiWarning]
