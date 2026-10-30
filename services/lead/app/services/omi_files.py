"""Reading of the OMI files of the Agenzia delle Entrate ("Forniture dati OMI").

- Quotations ("..._VALORI.csv"): one row per zone, building type and maintenance state, with
  the sale range in €/m². Separated by ";", with a title line before the header.
- Zones ("..._ZONE.csv", optional): the description of each zone.
- Perimeters (".kml" or ".kmz", from "Download perimetri"): the polygons of the zones; each
  Placemark carries the municipality cadastral code (CODCOM) and the zone code (CODZONA).
"""

import csv
import io
import re
import unicodedata
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from defusedxml import ElementTree  # type: ignore[import-untyped]

from app.models.enums import OmiState, OmiType
from app.models.omi import Polygons

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_KML_FILES = 2000

OMI_TYPES = {
    "abitazioni signorili": OmiType.LUXURY,
    "abitazioni civili": OmiType.CIVIL,
    "abitazioni di tipo economico": OmiType.ECONOMIC,
    "ville e villini": OmiType.VILLA,
}
OMI_STATES = {"ottimo": OmiState.EXCELLENT, "normale": OmiState.NORMAL, "scadente": OmiState.POOR}
SEMESTER = re.compile(r"(20\d\d)\s*/\s*([12])\b")
SEMESTER_IN_NAME = re.compile(r"_(20\d\d)([12])_")


class OmiFileError(Exception):
    """A file that is not an OMI file or cannot be read."""

    def __init__(self, code: str, file_name: str) -> None:
        super().__init__(code)
        self.code = code
        self.file_name = file_name


@dataclass(frozen=True)
class ParsedQuote:
    municipality_code: str
    alternative_code: str  # Comune_cat: differs from Comune_amm only for split municipalities
    municipality: str
    zone_code: str
    omi_type: OmiType
    state: OmiState
    prevalent: bool
    sale_min: float
    sale_max: float


@dataclass(frozen=True)
class ParsedZone:
    municipality_code: str
    zone_code: str
    polygons: Polygons


@dataclass
class ParsedQuotes:
    semester: str | None
    quotes: list[ParsedQuote] = field(default_factory=list)
    skipped_rows: int = 0


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().lower()


def _decode(data: bytes) -> str:
    # The files of different semesters do not all use the same encoding.
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _rows(data: bytes, file_name: str, required: Iterable[str]) -> tuple[str, list[dict[str, str]]]:
    """Returns the text before the header (title line) and the rows as dictionaries."""
    if len(data) > MAX_FILE_BYTES:
        raise OmiFileError("omi_file_too_large", file_name)
    lines = _decode(data).splitlines()
    required = tuple(required)
    for index, line in enumerate(lines):
        if all(name in line for name in required):
            reader = csv.DictReader(lines[index:], delimiter=";")
            rows = [
                {key.strip(): (value or "").strip() for key, value in row.items() if key}
                for row in reader
            ]
            return " ".join(lines[:index]), rows
    raise OmiFileError("omi_invalid_file", file_name)


def _number(text: str) -> float:
    """ "1250", "1250,5", "1.250,5" and "1.250" (thousands): values are €/m², never 1,25."""
    text = text.replace(" ", "")
    if "," in text or re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "").replace(",", ".")
    return float(text)


def semester_of(*texts: str) -> str | None:
    for text in texts:
        match = SEMESTER.search(text) or SEMESTER_IN_NAME.search(text)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    return None


def parse_quotes(data: bytes, file_name: str) -> ParsedQuotes:
    """Residential sale quotations; other building types (shops, offices...) are left out."""
    title, rows = _rows(data, file_name, ("Descr_Tipologia", "Compr_min", "Compr_max"))
    result = ParsedQuotes(semester=semester_of(title, file_name))
    for row in rows:
        omi_type = OMI_TYPES.get(_normalize(row.get("Descr_Tipologia", "")))
        state = OMI_STATES.get(_normalize(row.get("Stato", "")))
        code = (row.get("Comune_amm") or row.get("Comune_cat") or "").upper()
        zone = row.get("Zona", "").upper()
        if omi_type is None:
            continue
        try:
            sale_min = _number(row.get("Compr_min", ""))
            sale_max = _number(row.get("Compr_max", ""))
        except ValueError:
            result.skipped_rows += 1
            continue
        if state is None or not code or not zone or not 0 < sale_min <= sale_max:
            result.skipped_rows += 1
            continue
        result.quotes.append(
            ParsedQuote(
                municipality_code=code,
                alternative_code=(row.get("Comune_cat") or code).upper(),
                municipality=row.get("Comune_descrizione", "").title(),
                zone_code=zone,
                omi_type=omi_type,
                state=state,
                prevalent=row.get("Stato_prev", "").upper() == "P",
                sale_min=sale_min,
                sale_max=sale_max,
            )
        )
    return result


def parse_zone_descriptions(data: bytes, file_name: str) -> dict[tuple[str, str], str]:
    """(municipality code, zone code) -> description, e.g. "CENTRO STORICO"."""
    _, rows = _rows(data, file_name, ("Zona_Descr", "Zona"))
    descriptions: dict[tuple[str, str], str] = {}
    for row in rows:
        code = (row.get("Comune_amm") or row.get("Comune_cat") or "").upper()
        zone = row.get("Zona", "").upper()
        text = row.get("Zona_Descr", "").strip().strip("'").strip()
        if code and zone and text:
            descriptions[(code, zone)] = re.sub(r"\s+", " ", text)
    return descriptions


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: Element, name: str) -> list[Element]:
    return [child for child in element.iter() if _local(child.tag) == name]


def _ring(element: Element) -> list[list[float]]:
    points: list[list[float]] = []
    for coordinates in _children(element, "coordinates"):
        for token in (coordinates.text or "").split():
            parts = token.split(",")
            if len(parts) >= 2:
                points.append([float(parts[0]), float(parts[1])])
    return points


def _polygons(placemark: Element) -> Polygons:
    polygons: Polygons = []
    for polygon in _children(placemark, "Polygon"):
        rings = [
            _ring(boundary)
            for name in ("outerBoundaryIs", "innerBoundaryIs")
            for boundary in polygon
            if _local(boundary.tag) == name
        ]
        if rings and len(rings[0]) >= 3:
            polygons.append([ring for ring in rings if len(ring) >= 3])
    return polygons


def _extended(placemark: Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for data in _children(placemark, "Data"):
        value = next((c.text for c in data if _local(c.tag) == "value"), None)
        values[data.get("name", "").upper()] = (value or "").strip()
    for data in _children(placemark, "SimpleData"):
        values[data.get("name", "").upper()] = (data.text or "").strip()
    return values


def _parse_kml(data: bytes, file_name: str) -> tuple[str | None, list[ParsedZone]]:
    try:
        root = ElementTree.fromstring(data)
    except Exception as exc:  # defusedxml raises several error types
        raise OmiFileError("omi_invalid_file", file_name) from exc
    names = " ".join(c.text or "" for c in _children(root, "name")[:1])
    zones: list[ParsedZone] = []
    for placemark in _children(root, "Placemark"):
        values = _extended(placemark)
        code, zone = values.get("CODCOM", "").upper(), values.get("CODZONA", "").upper()
        polygons = _polygons(placemark)
        if code and zone and polygons:
            zones.append(ParsedZone(code, zone, polygons))
    return semester_of(names, file_name), zones


def parse_perimeters(data: bytes, file_name: str) -> tuple[str | None, list[ParsedZone]]:
    """Zones of a .kml file or of all the .kml files inside a .kmz (a zip)."""
    if len(data) > MAX_FILE_BYTES:
        raise OmiFileError("omi_file_too_large", file_name)
    if not zipfile.is_zipfile(io.BytesIO(data)):
        return _parse_kml(data, file_name)
    semester: str | None = None
    zones: list[ParsedZone] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = [i for i in archive.infolist() if i.filename.lower().endswith(".kml")]
        if not entries or len(entries) > MAX_KML_FILES:
            raise OmiFileError("omi_invalid_file", file_name)
        if sum(i.file_size for i in entries) > 4 * MAX_FILE_BYTES:
            raise OmiFileError("omi_file_too_large", file_name)
        for entry in entries:
            found_semester, found = _parse_kml(archive.read(entry), file_name)
            semester = semester or found_semester
            zones.extend(found)
    return semester, zones


def contains(polygons: Polygons, longitude: float, latitude: float) -> bool:
    """Point in polygon (ray casting); points inside a hole are outside."""

    def in_ring(ring: list[list[float]]) -> bool:
        inside = False
        j = len(ring) - 1
        for i, (x, y) in enumerate(ring):
            xj, yj = ring[j]
            if (y > latitude) != (yj > latitude) and longitude < (xj - x) * (latitude - y) / (
                yj - y
            ) + x:
                inside = not inside
            j = i
        return inside

    return any(
        in_ring(rings[0]) and not any(in_ring(hole) for hole in rings[1:]) for rings in polygons
    )


def bounding_box(polygons: Polygons) -> tuple[float, float, float, float]:
    """(min longitude, min latitude, max longitude, max latitude) of the outer rings."""
    points = [point for rings in polygons for point in rings[0]]
    longitudes = [p[0] for p in points]
    latitudes = [p[1] for p in points]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)
