from datetime import date

import pytest

from app.models.enums import (
    Accommodation,
    Contract,
    EnergyClass,
    Feature,
    PropertyCondition,
    PropertyStatus,
    PropertyType,
)
from app.services.importer import (
    CellError,
    PlannedRow,
    map_columns,
    parse_bool,
    parse_contract,
    parse_date,
    parse_energy_class,
    parse_floor,
    parse_number,
    parse_sheet,
    parse_type,
    plan_rows,
)
from app.services.spreadsheet import Cell, read_spreadsheet
from tests.factories import import_row, make_property, spreadsheet_bytes

TODAY = date(2026, 10, 21)


def plan(
    rows: list[dict[str, Cell]], existing: dict[str, object] | None = None
) -> list[PlannedRow]:
    sheet = read_spreadsheet(spreadsheet_bytes(rows), max_rows=100)
    _, parsed = parse_sheet(sheet)
    return plan_rows(parsed, existing or {}, TODAY)  # type: ignore[arg-type]


def codes(issues: list[object]) -> list[str]:
    return [issue.code for issue in issues]  # type: ignore[attr-defined]


# Columns ---------------------------------------------------------------------------------


def test_map_columns_recognizes_aliases_ignoring_case_accents_and_punctuation() -> None:
    columns = map_columns(["Rif.", "CITTÀ", "Prezzo (€)", "Mq", "Colore preferito", "Box auto"])

    assert columns.fields == {0: "external_ref", 1: "municipality", 2: "price", 3: "surface_sqm"}
    assert columns.feature_columns == {5: Feature.GARAGE}
    assert columns.ignored == ("Colore preferito",)


def test_map_columns_keeps_the_first_column_for_a_field() -> None:
    columns = map_columns(["Comune", "Località"])

    assert columns.fields == {0: "municipality"}
    assert columns.ignored == ("Località",)


# Values ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("120.000 €", 120_000),
        ("1.234,50", 1234.5),
        ("95 mq", 95),
        ("95,5", 95.5),
        (139000, 139_000),
        ("€ 450", 450),
    ],
)
def test_parse_number_reads_italian_formats(cell: Cell, expected: float) -> None:
    assert parse_number(cell) == expected


@pytest.mark.parametrize("cell", ["trattativa riservata", "", True])
def test_parse_number_rejects_text(cell: Cell) -> None:
    with pytest.raises(CellError):
        parse_number(cell)


@pytest.mark.parametrize(
    ("cell", "expected"),
    [("Vendita", Contract.SALE), ("AFFITTO", Contract.RENT), ("Locazione 4+4", Contract.RENT)],
)
def test_parse_contract_reads_italian_words(cell: str, expected: Contract) -> None:
    assert parse_contract(cell) is expected


def test_parse_type_maps_trilocale_to_apartment_with_three_rooms() -> None:
    assert parse_type("Trilocale") == (PropertyType.APARTMENT, 3)


@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("Villa a schiera", PropertyType.VILLA),
        ("Casa indipendente", PropertyType.HOUSE),
        ("Negozio", PropertyType.COMMERCIAL),
        ("Box auto", PropertyType.GARAGE),
        ("Terreno edificabile", PropertyType.LAND),
        ("Mansarda", PropertyType.ATTIC),
    ],
)
def test_parse_type_reads_common_types(cell: str, expected: PropertyType) -> None:
    assert parse_type(cell)[0] is expected


def test_parse_type_unknown_raises_type_other() -> None:
    with pytest.raises(CellError) as exc_info:
        parse_type("Castello")

    assert exc_info.value.code == "type_other"


@pytest.mark.parametrize(
    ("cell", "expected"),
    [("Classe G", EnergyClass.G), ("a4", EnergyClass.A4), ("In fase di rilascio", None)],
)
def test_parse_energy_class(cell: str, expected: EnergyClass | None) -> None:
    assert parse_energy_class(cell) is expected


@pytest.mark.parametrize(("cell", "expected"), [("Terra", 0), ("Rialzato", 0), ("3°", 3), (2, 2)])
def test_parse_floor(cell: Cell, expected: int) -> None:
    assert parse_floor(cell) == expected


@pytest.mark.parametrize(("cell", "expected"), [("Sì", True), ("x", True), ("No", False)])
def test_parse_bool(cell: str, expected: bool) -> None:
    assert parse_bool(cell) is expected


def test_parse_date_reads_italian_day_first() -> None:
    assert parse_date("01/09/2026") == date(2026, 9, 1)


def test_parse_date_rejects_impossible_dates() -> None:
    with pytest.raises(CellError):
        parse_date("31/02/2026")


# Plan ------------------------------------------------------------------------------------


def test_plan_valid_row_creates_listing_with_parsed_values() -> None:
    (row,) = plan([import_row(Riferimento="RS-1", Classe="C", Stato="Ristrutturato")])

    assert row.action == "create"
    assert row.errors == []
    assert row.create is not None
    assert row.create.external_ref == "RS-1"
    assert row.create.price == 139_000
    assert row.create.surface_sqm == 95
    assert row.create.energy_class is EnergyClass.C
    assert row.create.condition is PropertyCondition.RENOVATED
    assert row.create.features == [Feature.ELEVATOR]


def test_plan_row_without_required_values_is_invalid() -> None:
    (row,) = plan([import_row(Prezzo=None, Comune="")])

    assert row.action == "invalid"
    assert codes(row.errors) == ["missing_value", "missing_value"]
    assert [issue.field for issue in row.errors] == ["price", "municipality"]


def test_plan_unreadable_number_reports_column_and_value() -> None:
    (row,) = plan([import_row(Prezzo="trattativa riservata")])

    assert row.action == "invalid"
    error = row.errors[0]
    assert (error.code, error.column, error.value) == (
        "invalid_number",
        "Prezzo",
        "trattativa riservata",
    )


def test_plan_same_reference_twice_in_file_rejects_the_second_row() -> None:
    first, second = plan([import_row(Riferimento="RS-9"), import_row(Riferimento="RS-9")])

    assert first.action == "create"
    assert second.action == "invalid"
    assert codes(second.errors) == ["duplicate_in_file"]
    assert second.errors[0].value == "2"


def test_plan_existing_reference_updates_only_the_columns_in_the_file() -> None:
    existing = make_property(
        external_ref="RS-5", status=PropertyStatus.PUBLISHED, description="Testo originale."
    )

    (row,) = plan([{"Riferimento": "RS-5", "Prezzo": "125.000"}], {"RS-5": existing})

    assert row.action == "update"
    assert row.update is not None
    target, fields = row.update
    assert target is existing
    assert fields.price == 125_000
    assert fields.description == "Testo originale."


def test_plan_more_bedrooms_than_rooms_is_invalid() -> None:
    (row,) = plan([import_row(Locali=2, Camere=3)])

    assert row.action == "invalid"
    assert codes(row.errors) == ["bedrooms_exceed_rooms"]


def test_plan_floor_above_total_floors_is_invalid() -> None:
    (row,) = plan([import_row(Piano=5, **{"Piani totali": 3})])

    assert codes(row.errors) == ["floor_above_total"]


def test_plan_sale_with_rental_fields_is_invalid() -> None:
    (row,) = plan([import_row(**{"Disponibile dal": "01/09/2026"})])

    assert codes(row.errors) == ["rental_fields_on_sale"]


def test_plan_year_built_in_the_future_is_invalid() -> None:
    (row,) = plan([import_row(**{"Anno costruzione": 2040})])

    assert codes(row.errors) == ["year_in_future"]


def test_plan_negative_price_is_out_of_range() -> None:
    (row,) = plan([import_row(Prezzo=-10)])

    assert codes(row.errors) == ["out_of_range"]


def test_plan_without_title_generates_one_with_warning() -> None:
    (row,) = plan([import_row(Titolo=None, Tipologia="Villa", Zona="Brecciarola")])

    assert row.action == "create"
    assert row.create is not None
    assert row.create.title == "Villa a Chieti, Brecciarola"
    assert "title_generated" in codes(row.warnings)


def test_plan_bilocale_without_rooms_infers_two_rooms() -> None:
    (row,) = plan([import_row(Tipologia="Bilocale", Locali=None, Camere=1)])

    assert row.create is not None
    assert row.create.rooms == 2
    assert "rooms_inferred" in codes(row.warnings)


def test_plan_without_reference_warns_that_reimport_would_duplicate() -> None:
    (row,) = plan([import_row(Riferimento=None)])

    assert row.action == "create"
    assert codes(row.warnings) == ["no_external_ref"]


@pytest.mark.parametrize(
    ("overrides", "warning"),
    [
        ({"Contratto": "Affitto", "Prezzo": 150_000}, "price_unusual_rent"),
        ({"Prezzo": 1_500}, "price_unusual_sale"),
        ({"Prezzo": 2_000_000}, "price_per_sqm_unusual"),
        ({"Prezzo": 0}, "price_zero"),
    ],
)
def test_plan_implausible_prices_are_imported_with_warning(
    overrides: dict[str, Cell], warning: str
) -> None:
    (row,) = plan([import_row(**overrides)])

    assert row.action == "create"
    assert codes(row.warnings) == [warning]


def test_plan_unknown_type_becomes_other_with_warning() -> None:
    (row,) = plan([import_row(Tipologia="Castello")])

    assert row.action == "create"
    assert row.create is not None
    assert row.create.property_type is PropertyType.OTHER
    assert codes(row.warnings) == ["type_other"]


def test_plan_long_title_is_truncated_with_warning() -> None:
    (row,) = plan([import_row(Titolo="A" * 200)])

    assert row.create is not None
    assert len(row.create.title) == 120
    assert codes(row.warnings) == ["value_truncated"]


def test_plan_feature_list_column_is_read() -> None:
    (row,) = plan([import_row(Ascensore=None, Caratteristiche="Giardino, posto auto, cantina")])

    assert row.create is not None
    assert row.create.features == [Feature.CELLAR, Feature.GARDEN, Feature.PARKING]


def test_plan_place_written_in_capitals_is_tidied() -> None:
    (row,) = plan([import_row(Comune="CHIETI SCALO")])

    assert row.create is not None
    assert row.create.municipality == "Chieti Scalo"


def test_plan_unreadable_required_value_is_reported_once() -> None:
    (row,) = plan([import_row(Prezzo="trattativa riservata")])

    assert codes(row.errors) == ["invalid_number"]


def test_plan_room_for_students_is_a_single_room_rental() -> None:
    (row,) = plan([import_row(Contratto="Affitto", Tipologia="Stanza singola", Prezzo=280)])

    assert row.create is not None
    assert row.create.property_type is PropertyType.APARTMENT
    assert row.create.accommodation is Accommodation.SINGLE_ROOM


def test_plan_room_for_sale_is_invalid() -> None:
    (row,) = plan([import_row(Tipologia="Posto letto")])

    assert codes(row.errors) == ["rental_fields_on_sale"]
