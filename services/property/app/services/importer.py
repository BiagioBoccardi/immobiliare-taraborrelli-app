"""Bulk import of listings from a spreadsheet (e.g. the Excel export of Reasoft).

Pure functions, no I/O: column recognition, Italian value parsing and consistency checks.
Every problem is reported per row as an error (the row is not imported) or a warning (the
row is imported, but something deserves a look). Codes are translated by the admin panel.
"""

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from pydantic import ValidationError

from app.models.enums import (
    Accommodation,
    Contract,
    EnergyClass,
    Feature,
    PropertyCondition,
    PropertyType,
)
from app.models.property import Property
from app.schemas.imports import ImportIssue
from app.schemas.property import PropertyCreate, PropertyFields
from app.services.spreadsheet import Cell, Sheet

ImportAction = Literal["create", "update", "invalid"]

REQUIRED_FIELDS = ("contract", "property_type", "price", "surface_sqm", "municipality")
TITLE_MAX = 120
DESCRIPTION_MAX = 10_000

# Thresholds of the plausibility warnings.
MAX_PLAUSIBLE_RENT = 10_000  # euros per month
MIN_PLAUSIBLE_SALE = 5_000
SALE_PRICE_PER_SQM = (150, 8_000)  # euros per square meter, Chieti area and beyond


def normalize(text: str) -> str:
    """Lowercase, without accents and punctuation: "Città " -> "citta"."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


# Column headers accepted for each field (normalized). Reasoft and most management
# software use Italian headers; the template of the admin panel uses the first one.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "external_ref": (
        "riferimento",
        "rif",
        "codice",
        "codice immobile",
        "codice annuncio",
        "cod immobile",
        "riferimento immobile",
        "riferimento agenzia",
        "id immobile",
        "id annuncio",
    ),
    "contract": ("contratto", "tipo contratto", "operazione", "vendita affitto", "causale"),
    "property_type": ("tipologia", "tipo immobile", "tipologia immobile", "categoria", "tipo"),
    "title": ("titolo", "titolo annuncio"),
    "description": ("descrizione", "descrizione annuncio", "testo annuncio", "testo"),
    "price": ("prezzo", "prezzo richiesto", "canone", "prezzo canone", "importo", "prezzo euro"),
    "condominium_fees": ("spese condominiali", "spese condominio", "condominio"),
    "surface_sqm": (
        "superficie",
        "mq",
        "metri quadri",
        "metri quadrati",
        "superficie mq",
        "superficie commerciale",
    ),
    "rooms": ("locali", "vani", "numero locali", "n locali", "numero vani"),
    "bedrooms": ("camere", "camere da letto", "numero camere", "n camere"),
    "bathrooms": ("bagni", "numero bagni", "n bagni", "servizi"),
    "floor": ("piano",),
    "total_floors": ("piani totali", "totale piani", "piani edificio", "numero piani"),
    "year_built": ("anno costruzione", "anno di costruzione", "anno"),
    "condition": ("stato", "stato immobile", "condizioni", "stato conservativo"),
    "energy_class": ("classe energetica", "classe", "ape", "classe ape"),
    "municipality": ("comune", "citta", "localita", "paese"),
    "zone": ("zona", "quartiere", "frazione"),
    "address": ("indirizzo", "via"),
    "latitude": ("latitudine", "lat"),
    "longitude": ("longitudine", "lng", "lon"),
    "available_from": ("disponibile dal", "disponibilita", "data disponibilita", "libero dal"),
    "is_featured": ("in evidenza", "evidenza"),
    "features": ("caratteristiche", "dotazioni", "accessori"),
}

# One yes/no column per feature.
FEATURE_COLUMNS: dict[Feature, tuple[str, ...]] = {
    Feature.ELEVATOR: ("ascensore",),
    Feature.PARKING: ("posto auto", "parcheggio"),
    Feature.GARAGE: ("box", "garage", "box auto"),
    Feature.GARDEN: ("giardino",),
    Feature.TERRACE: ("terrazzo", "terrazza"),
    Feature.BALCONY: ("balcone", "balconi"),
    Feature.CELLAR: ("cantina",),
    Feature.FURNISHED: ("arredato", "arredamento"),
    Feature.AIR_CONDITIONING: ("aria condizionata", "climatizzato", "climatizzazione"),
    Feature.AUTONOMOUS_HEATING: ("riscaldamento autonomo",),
}

# Template header for each field, in the order of the downloadable template.
TEMPLATE_HEADERS: dict[str, str] = {
    "external_ref": "Riferimento",
    "contract": "Contratto",
    "property_type": "Tipologia",
    "title": "Titolo",
    "description": "Descrizione",
    "price": "Prezzo",
    "condominium_fees": "Spese condominiali",
    "surface_sqm": "Superficie",
    "rooms": "Locali",
    "bedrooms": "Camere",
    "bathrooms": "Bagni",
    "floor": "Piano",
    "total_floors": "Piani totali",
    "year_built": "Anno costruzione",
    "condition": "Stato",
    "energy_class": "Classe energetica",
    "municipality": "Comune",
    "zone": "Zona",
    "address": "Indirizzo",
    "available_from": "Disponibile dal",
}
TEMPLATE_FEATURE_HEADERS: dict[Feature, str] = {
    Feature.ELEVATOR: "Ascensore",
    Feature.PARKING: "Posto auto",
    Feature.GARAGE: "Box",
    Feature.GARDEN: "Giardino",
    Feature.TERRACE: "Terrazzo",
    Feature.BALCONY: "Balcone",
    Feature.CELLAR: "Cantina",
    Feature.FURNISHED: "Arredato",
    Feature.AIR_CONDITIONING: "Aria condizionata",
    Feature.AUTONOMOUS_HEATING: "Riscaldamento autonomo",
}

CONTRACT_WORDS: dict[str, Contract] = {
    "vendita": Contract.SALE,
    "v": Contract.SALE,
    "vendesi": Contract.SALE,
    "compravendita": Contract.SALE,
    "sale": Contract.SALE,
    "affitto": Contract.RENT,
    "a": Contract.RENT,
    "affittasi": Contract.RENT,
    "locazione": Contract.RENT,
    "affitto transitorio": Contract.RENT,
    "affitto per studenti": Contract.RENT,
    "rent": Contract.RENT,
}

# Checked in order: the first word found in the value decides the type.
TYPE_WORDS: tuple[tuple[str, PropertyType], ...] = (
    # Before "locale" (commercial premises), which they contain.
    ("monolocale", PropertyType.APARTMENT),
    ("bilocale", PropertyType.APARTMENT),
    ("trilocale", PropertyType.APARTMENT),
    ("quadrilocale", PropertyType.APARTMENT),
    ("plurilocale", PropertyType.APARTMENT),
    ("attico", PropertyType.ATTIC),
    ("mansarda", PropertyType.ATTIC),
    ("villa", PropertyType.VILLA),
    ("villetta", PropertyType.VILLA),
    ("terreno", PropertyType.LAND),
    ("box", PropertyType.GARAGE),
    ("garage", PropertyType.GARAGE),
    ("autorimessa", PropertyType.GARAGE),
    ("posto auto", PropertyType.GARAGE),
    ("negozio", PropertyType.COMMERCIAL),
    ("ufficio", PropertyType.COMMERCIAL),
    ("commerciale", PropertyType.COMMERCIAL),
    ("capannone", PropertyType.COMMERCIAL),
    ("laboratorio", PropertyType.COMMERCIAL),
    ("magazzino", PropertyType.COMMERCIAL),
    ("locale", PropertyType.COMMERCIAL),
    ("appartamento", PropertyType.APARTMENT),
    ("stanza", PropertyType.APARTMENT),
    ("posto letto", PropertyType.APARTMENT),
    ("loft", PropertyType.APARTMENT),
    ("casa", PropertyType.HOUSE),
    ("rustico", PropertyType.HOUSE),
    ("casale", PropertyType.HOUSE),
    ("terratetto", PropertyType.HOUSE),
    ("porzione", PropertyType.HOUSE),
    ("apartment", PropertyType.APARTMENT),
    ("house", PropertyType.HOUSE),
)
ROOMS_FROM_TYPE = {"monolocale": 1, "bilocale": 2, "trilocale": 3, "quadrilocale": 4}
# Rooms for students and workers: the type says the kind of accommodation.
ACCOMMODATION_FROM_TYPE = {
    "stanza": Accommodation.SINGLE_ROOM,
    "posto letto": Accommodation.SHARED_ROOM,
}
TYPE_LABELS: dict[PropertyType, str] = {
    PropertyType.APARTMENT: "Appartamento",
    PropertyType.HOUSE: "Casa",
    PropertyType.VILLA: "Villa",
    PropertyType.ATTIC: "Attico",
    PropertyType.COMMERCIAL: "Locale commerciale",
    PropertyType.LAND: "Terreno",
    PropertyType.GARAGE: "Box",
    PropertyType.OTHER: "Immobile",
}

CONDITION_WORDS: tuple[tuple[str, PropertyCondition], ...] = (
    ("da ristrutturare", PropertyCondition.TO_RENOVATE),
    ("da rimodernare", PropertyCondition.TO_RENOVATE),
    ("nuov", PropertyCondition.NEW),
    ("in costruzione", PropertyCondition.NEW),
    ("ristrutturat", PropertyCondition.RENOVATED),
    ("ottimo", PropertyCondition.RENOVATED),
    ("buono", PropertyCondition.GOOD),
    ("abitabile", PropertyCondition.GOOD),
    ("discreto", PropertyCondition.GOOD),
)

# Values meaning "no energy class yet": not an error, just nothing to show.
ENERGY_CLASS_NONE = ("esente", "in fase", "non classificabile", "non soggetto", "n d", "nd")

FLOOR_WORDS = {
    "terra": 0,
    "piano terra": 0,
    "t": 0,
    "pt": 0,
    "rialzato": 0,
    "piano rialzato": 0,
    "r": 0,
    "seminterrato": -1,
    "s": -1,
    "interrato": -1,
}

TRUE_WORDS = {"si", "s", "x", "yes", "y", "true", "vero", "1", "presente", "ok"}
FALSE_WORDS = {"no", "n", "false", "falso", "0", "assente"}


class CellError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class ParsedRow:
    number: int
    values: dict[str, Any]  # only the fields with a value in the file
    errors: list[ImportIssue] = field(default_factory=list)
    warnings: list[ImportIssue] = field(default_factory=list)


@dataclass
class PlannedRow:
    number: int
    action: ImportAction
    external_ref: str | None
    title: str | None
    municipality: str | None
    contract: Contract | None
    price: int | None
    errors: list[ImportIssue]
    warnings: list[ImportIssue]
    create: PropertyCreate | None = None
    update: tuple[Property, PropertyFields] | None = None


@dataclass(frozen=True)
class ColumnMap:
    fields: dict[int, str]  # column index -> field name
    feature_columns: dict[int, Feature]
    ignored: tuple[str, ...]


def map_columns(headers: Iterable[str]) -> ColumnMap:
    """Matches each header with a field. The first column for a field wins."""
    by_alias = {alias: name for name, aliases in COLUMN_ALIASES.items() for alias in aliases}
    by_feature = {alias: f for f, aliases in FEATURE_COLUMNS.items() for alias in aliases}
    fields: dict[int, str] = {}
    features: dict[int, Feature] = {}
    ignored: list[str] = []
    for index, header in enumerate(headers):
        key = normalize(header)
        name = by_alias.get(key)
        feature = by_feature.get(key)
        if name is not None and name not in fields.values():
            fields[index] = name
        elif feature is not None and feature not in features.values():
            features[index] = feature
        elif header:
            ignored.append(header)
    return ColumnMap(fields=fields, feature_columns=features, ignored=tuple(ignored))


# Cell parsers --------------------------------------------------------------------------


def _text(cell: Cell) -> str:
    if isinstance(cell, float) and cell.is_integer():
        return str(int(cell))
    return str(cell).strip()


def parse_number(cell: Cell) -> float:
    """Numbers as written in Italy: "120.000 €", "1.234,50", "95 mq", "95,5"."""
    if isinstance(cell, bool):
        raise CellError("invalid_number")
    if isinstance(cell, int | float):
        return float(cell)
    text = re.sub(r"(?i)(euro|eur|€|mq|m2|m²|metri quadri|\s)", "", _text(cell))
    if not text:
        raise CellError("invalid_number")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")  # "120.000" is thousands, not a decimal
    try:
        return float(text)
    except ValueError as exc:
        raise CellError("invalid_number") from exc


def parse_int(cell: Cell) -> int:
    return round(parse_number(cell))


def parse_bool(cell: Cell) -> bool:
    if isinstance(cell, bool):
        return cell
    key = normalize(_text(cell))
    if key in TRUE_WORDS:
        return True
    if key in FALSE_WORDS:
        return False
    raise CellError("invalid_boolean")


def parse_date(cell: Cell) -> date:
    if isinstance(cell, datetime):
        return cell.date()
    if isinstance(cell, date):
        return cell
    match = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", _text(cell))
    if match:
        day, month, year = (int(g) for g in match.groups())
        try:
            return date(year + 2000 if year < 100 else year, month, day)
        except ValueError as exc:
            raise CellError("invalid_date") from exc
    try:
        return date.fromisoformat(_text(cell)[:10])
    except ValueError as exc:
        raise CellError("invalid_date") from exc


def parse_contract(cell: Cell) -> Contract:
    key = normalize(_text(cell))
    if key in CONTRACT_WORDS:
        return CONTRACT_WORDS[key]
    if "vend" in key:
        return Contract.SALE
    if "affitt" in key or "locaz" in key:
        return Contract.RENT
    raise CellError("invalid_value")


def parse_type(cell: Cell) -> tuple[PropertyType, int | None]:
    """Type and, for "bilocale" and the like, the number of rooms it implies."""
    key = normalize(_text(cell))
    rooms = next((n for word, n in ROOMS_FROM_TYPE.items() if word in key), None)
    for word, kind in TYPE_WORDS:
        if word in key:
            return kind, rooms
    raise CellError("type_other")


def parse_condition(cell: Cell) -> PropertyCondition:
    key = normalize(_text(cell))
    for word, condition in CONDITION_WORDS:
        if word in key:
            return condition
    raise CellError("condition_ignored")


def parse_energy_class(cell: Cell) -> EnergyClass | None:
    key = normalize(_text(cell))
    if any(word in key for word in ENERGY_CLASS_NONE) or not key:
        return None
    key = key.removeprefix("classe ").replace(" ", "").upper()
    try:
        return EnergyClass(key)
    except ValueError as exc:
        raise CellError("energy_class_ignored") from exc


def parse_floor(cell: Cell) -> int:
    key = normalize(_text(cell))
    if key in FLOOR_WORDS:
        return FLOOR_WORDS[key]
    match = re.search(r"-?\d+", key)
    if match:
        return int(match.group())
    raise CellError("invalid_number")


def parse_features(cell: Cell) -> set[Feature]:
    """A free list such as "Ascensore, posto auto, cantina"."""
    found: set[Feature] = set()
    key = normalize(_text(cell))
    for feature, aliases in FEATURE_COLUMNS.items():
        if any(re.search(rf"\b{alias}\b", key) for alias in aliases):
            found.add(feature)
    return found


def _clean_place(cell: Cell) -> str:
    text = re.sub(r"\s+", " ", _text(cell))
    # "CHIETI SCALO" or "chieti scalo" -> "Chieti Scalo"; mixed case is kept as written.
    return text.title() if text.isupper() or text.islower() else text


TEXT_FIELDS = {"external_ref", "title", "description", "zone", "address"}
NUMBER_FIELDS: dict[str, Callable[[Cell], Any]] = {
    "price": parse_int,
    "condominium_fees": parse_int,
    "surface_sqm": parse_int,
    "rooms": parse_int,
    "bedrooms": parse_int,
    "bathrooms": parse_int,
    "total_floors": parse_int,
    "year_built": parse_int,
    "latitude": parse_number,
    "longitude": parse_number,
}
WARNING_CODES = {"type_other", "condition_ignored", "energy_class_ignored", "invalid_boolean"}


def _is_blank(cell: Cell) -> bool:
    return cell is None or (isinstance(cell, str) and not cell.strip())


def parse_row(
    number: int, cells: tuple[Cell, ...], columns: ColumnMap, headers: tuple[str, ...]
) -> ParsedRow:
    row = ParsedRow(number=number, values={})

    def issue(code: str, index: int, name: str | None, cell: Cell = None) -> ImportIssue:
        value = None if cell is None else _text(cell)[:80]
        return ImportIssue(code=code, column=headers[index] or None, field=name, value=value)

    for index, name in columns.fields.items():
        cell = cells[index]
        if _is_blank(cell):
            continue
        try:
            if name in TEXT_FIELDS:
                text = _text(cell)
                limit = {"title": TITLE_MAX, "description": DESCRIPTION_MAX}.get(name)
                if limit is not None and len(text) > limit:
                    row.warnings.append(issue("value_truncated", index, name))
                    text = text[:limit].rstrip()
                row.values[name] = text
            elif name == "municipality":
                row.values[name] = _clean_place(cell)
            elif name in NUMBER_FIELDS:
                row.values[name] = NUMBER_FIELDS[name](cell)
            elif name == "contract":
                row.values[name] = parse_contract(cell)
            elif name == "property_type":
                kind, rooms = parse_type(cell)
                row.values[name] = kind
                if rooms is not None:
                    row.values["_rooms_from_type"] = rooms
                key = normalize(_text(cell))
                for word, accommodation in ACCOMMODATION_FROM_TYPE.items():
                    if word in key:
                        row.values["accommodation"] = accommodation
            elif name == "condition":
                row.values[name] = parse_condition(cell)
            elif name == "energy_class":
                energy = parse_energy_class(cell)
                if energy is not None:
                    row.values[name] = energy
            elif name == "floor":
                row.values[name] = parse_floor(cell)
            elif name == "available_from":
                row.values[name] = parse_date(cell)
            elif name == "is_featured":
                row.values[name] = parse_bool(cell)
            elif name == "features":
                row.values["_feature_list"] = parse_features(cell)
        except CellError as exc:
            if exc.code == "type_other":
                row.values[name] = PropertyType.OTHER
            target = row.warnings if exc.code in WARNING_CODES else row.errors
            target.append(issue(exc.code, index, name, cell))

    if columns.feature_columns or "_feature_list" in row.values:
        features: set[Feature] = set(row.values.pop("_feature_list", set()))
        for index, feature in columns.feature_columns.items():
            cell = cells[index]
            if _is_blank(cell):
                continue
            try:
                if parse_bool(cell):
                    features.add(feature)
            except CellError:
                row.warnings.append(issue("invalid_boolean", index, "features", cell))
        row.values["features"] = sorted(features)
    return row


def parse_sheet(sheet: Sheet) -> tuple[ColumnMap, list[ParsedRow]]:
    columns = map_columns(sheet.headers)
    rows = [parse_row(r.number, r.cells, columns, sheet.headers) for r in sheet.rows]
    return columns, rows


# Consistency checks ----------------------------------------------------------------------


def _validation_issues(exc: ValidationError) -> list[ImportIssue]:
    """Translates the model's own rules (ranges, rental-only fields...) into row errors."""
    issues: list[ImportIssue] = []
    for error in exc.errors():
        name = str(error["loc"][0]) if error["loc"] else None
        message = str(error.get("msg", ""))
        if error["type"] in {"greater_than_equal", "less_than_equal"}:
            code = "out_of_range"
        elif error["type"] == "missing":
            code = "missing_value"
        elif error["type"] == "string_too_short":
            code = "too_short"
        elif "only allowed for rentals" in message:
            code = "rental_fields_on_sale"
        elif "floor cannot be higher" in message:
            code = "floor_above_total"
        elif "latitude and longitude" in message:
            code = "coordinates_incomplete"
        else:
            code = "invalid_value"
        issues.append(ImportIssue(code=code, field=name))
    return issues


def _plausibility(
    fields: PropertyFields, today: date
) -> tuple[list[ImportIssue], list[ImportIssue]]:
    errors: list[ImportIssue] = []
    warnings: list[ImportIssue] = []
    if fields.rooms is not None and fields.bedrooms is not None and fields.bedrooms > fields.rooms:
        errors.append(ImportIssue(code="bedrooms_exceed_rooms", field="bedrooms"))
    if fields.year_built is not None and fields.year_built > today.year + 3:
        errors.append(ImportIssue(code="year_in_future", field="year_built"))
    if fields.price == 0:
        warnings.append(ImportIssue(code="price_zero", field="price"))
    elif fields.contract is Contract.RENT and fields.price > MAX_PLAUSIBLE_RENT:
        warnings.append(ImportIssue(code="price_unusual_rent", field="price"))
    elif fields.contract is Contract.SALE and fields.property_type not in {
        PropertyType.GARAGE,
        PropertyType.LAND,
    }:
        per_sqm = fields.price / fields.surface_sqm
        if fields.price < MIN_PLAUSIBLE_SALE:
            warnings.append(ImportIssue(code="price_unusual_sale", field="price"))
        elif not SALE_PRICE_PER_SQM[0] <= per_sqm <= SALE_PRICE_PER_SQM[1]:
            warnings.append(ImportIssue(code="price_per_sqm_unusual", field="price"))
    return errors, warnings


def _generated_title(values: dict[str, Any]) -> str | None:
    kind = values.get("property_type")
    place = values.get("municipality")
    if kind is None or place is None:
        return None
    zone = values.get("zone")
    return f"{TYPE_LABELS[kind]} a {place}" + (f", {zone}" if zone else "")


def plan_rows(
    rows: list[ParsedRow], existing: dict[str, Property], today: date
) -> list[PlannedRow]:
    """Decides, row by row, whether to create, update (same management code) or skip."""
    seen: dict[str, int] = {}
    plan: list[PlannedRow] = []
    for row in rows:
        values = dict(row.values)
        errors = list(row.errors)
        warnings = list(row.warnings)
        ref = values.get("external_ref")
        rooms_from_type = values.pop("_rooms_from_type", None)

        if ref is None:
            warnings.append(ImportIssue(code="no_external_ref", field="external_ref"))
        elif ref in seen:
            errors.append(
                ImportIssue(code="duplicate_in_file", field="external_ref", value=str(seen[ref]))
            )
        else:
            seen[ref] = row.number

        target = existing.get(ref) if ref is not None else None
        if target is None:
            # A field whose value could not be read already has its own error.
            unreadable = {issue.field for issue in errors}
            missing = [
                name for name in REQUIRED_FIELDS if name not in values and name not in unreadable
            ]
            errors.extend(ImportIssue(code="missing_value", field=name) for name in missing)
            if "rooms" not in values and rooms_from_type is not None:
                values["rooms"] = rooms_from_type
                warnings.append(ImportIssue(code="rooms_inferred", field="rooms"))
            if "title" not in values:
                title = _generated_title(values)
                if title is not None:
                    values["title"] = title
                    warnings.append(ImportIssue(code="title_generated", field="title"))

        planned = PlannedRow(
            number=row.number,
            action="invalid",
            external_ref=ref,
            title=values.get("title") or (target.title if target else None),
            municipality=values.get("municipality") or (target.municipality if target else None),
            contract=values.get("contract") or (target.contract if target else None),
            price=values.get("price", target.price if target else None),
            errors=errors,
            warnings=warnings,
        )
        plan.append(planned)
        if errors:
            continue

        try:
            if target is None:
                create = PropertyCreate.model_validate(values)
                fields: PropertyFields = create
            else:
                current = {name: getattr(target, name) for name in PropertyFields.model_fields}
                fields = PropertyFields.model_validate({**current, **values})
        except ValidationError as exc:
            planned.errors.extend(_validation_issues(exc))
            continue

        more_errors, more_warnings = _plausibility(fields, today)
        planned.errors.extend(more_errors)
        planned.warnings.extend(more_warnings)
        if planned.errors:
            continue
        if target is None:
            planned.action = "create"
            planned.create = create
        else:
            planned.action = "update"
            planned.update = (target, fields)
    return plan
