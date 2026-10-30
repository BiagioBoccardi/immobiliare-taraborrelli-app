import pytest

from app.models.enums import OmiState, OmiType
from app.services.omi_files import (
    OmiFileError,
    bounding_box,
    contains,
    parse_perimeters,
    parse_quotes,
    parse_zone_descriptions,
    semester_of,
)
from tests.factories import omi_kml, omi_kmz, omi_values_csv, omi_zones_csv


def test_parse_quotes_keeps_only_residential_types() -> None:
    parsed = parse_quotes(omi_values_csv(), "QI_1_1_20261_VALORI.csv")

    assert parsed.semester == "2026/1"
    assert len(parsed.quotes) == 5
    assert {q.omi_type for q in parsed.quotes} == set(OmiType) - {OmiType.LUXURY}


def test_parse_quotes_reads_state_prevalence_and_values() -> None:
    first = parse_quotes(omi_values_csv(), "valori.csv").quotes[0]

    assert (first.municipality_code, first.municipality, first.zone_code) == (
        "C632",
        "Chieti",
        "B1",
    )
    assert (first.omi_type, first.state, first.prevalent) == (OmiType.CIVIL, OmiState.NORMAL, True)
    assert (first.sale_min, first.sale_max) == (1100, 1500)


def test_parse_quotes_with_decimal_comma_reads_the_number() -> None:
    rows = [("B1", "Abitazioni civili", "NORMALE", "P", "1.100,5", "1.500")]

    quote = parse_quotes(omi_values_csv(rows), "valori.csv").quotes[0]

    assert (quote.sale_min, quote.sale_max) == (1100.5, 1500)


def test_parse_quotes_skips_unreadable_rows() -> None:
    rows = [
        ("B1", "Abitazioni civili", "NORMALE", "P", "n.d.", "1500"),
        ("B1", "Abitazioni civili", "NORMALE", "P", "1600", "1500"),
        ("B1", "Abitazioni civili", "SCONOSCIUTO", "P", "1000", "1500"),
    ]

    parsed = parse_quotes(omi_values_csv(rows), "valori.csv")

    assert parsed.quotes == []
    assert parsed.skipped_rows == 3


def test_parse_quotes_of_another_file_raises() -> None:
    with pytest.raises(OmiFileError) as error:
        parse_quotes(b"Riferimento;Prezzo\n1;100000\n", "immobili.csv")

    assert error.value.code == "omi_invalid_file"
    assert error.value.file_name == "immobili.csv"


def test_parse_zone_descriptions_removes_quotes() -> None:
    descriptions = parse_zone_descriptions(omi_zones_csv(), "zone.csv")

    assert descriptions == {("C632", "B1"): "CENTRO STORICO", ("C632", "D1"): "SCALO"}


def test_parse_perimeters_reads_kml_placemarks() -> None:
    semester, zones = parse_perimeters(omi_kml(), "Comune di CHIETI 2026-1.kml")

    assert semester == "2026/1"
    assert [(z.municipality_code, z.zone_code) for z in zones] == [("C632", "B1"), ("C632", "D1")]
    assert zones[0].polygons[0][0][0] == [14.15, 42.34]


def test_parse_perimeters_reads_every_kml_in_a_kmz() -> None:
    _, zones = parse_perimeters(omi_kmz(), "Provincia di CHIETI 2026-1.kmz")

    assert len(zones) == 2


def test_parse_perimeters_of_broken_file_raises() -> None:
    with pytest.raises(OmiFileError):
        parse_perimeters(b"<kml><Document>", "rotto.kml")


def test_parse_perimeters_rejects_entity_expansion() -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE k [<!ENTITY a "aaaa">]><kml>&a;</kml>'

    with pytest.raises(OmiFileError):
        parse_perimeters(bomb, "bomba.kml")


def test_contains_is_false_inside_a_hole() -> None:
    outer = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]
    hole = [[4.0, 4.0], [6.0, 4.0], [6.0, 6.0], [4.0, 6.0]]
    polygons = [[outer, hole]]

    assert contains(polygons, 2, 2)
    assert not contains(polygons, 5, 5)
    assert not contains(polygons, 11, 5)


def test_bounding_box_spans_every_polygon() -> None:
    polygons = [[[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]]], [[[5.0, 5.0], [6.0, 5.0], [6.0, 7.0]]]]

    assert bounding_box(polygons) == (0.0, 0.0, 6.0, 7.0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Quotazioni - Semestre 2025/2", "2025/2"),
        ("QI_123_1_20252_VALORI.csv", "2025/2"),
        ("senza semestre", None),
    ],
)
def test_semester_of_finds_year_and_half(text: str, expected: str | None) -> None:
    assert semester_of(text) == expected
