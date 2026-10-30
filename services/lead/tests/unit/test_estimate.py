import pytest

from app.models.enums import (
    BuildingWorks,
    CadastralCategory,
    OmiState,
    OmiType,
    PropertyCondition,
    PropertyType,
)
from app.models.omi import OmiQuote
from app.services.estimate import EstimateInput, estimate_value, floor_factor


def _quote(omi_type: OmiType, state: OmiState, low: float, high: float) -> OmiQuote:
    return OmiQuote(
        municipality_code="C632",
        municipality="Chieti",
        zone_code="B1",
        omi_type=omi_type,
        state=state,
        prevalent=state is OmiState.NORMAL,
        sale_min=low,
        sale_max=high,
    )


QUOTES = [
    _quote(OmiType.CIVIL, OmiState.NORMAL, 1000, 1400),
    _quote(OmiType.CIVIL, OmiState.EXCELLENT, 1400, 1800),
    _quote(OmiType.ECONOMIC, OmiState.NORMAL, 800, 1100),
    _quote(OmiType.VILLA, OmiState.NORMAL, 1200, 1700),
]


def _input(**overrides: object) -> EstimateInput:
    values: dict[str, object] = {
        "property_type": PropertyType.APARTMENT,
        "surface_sqm": 100,
        "condition": PropertyCondition.GOOD,
    }
    values.update(overrides)
    return EstimateInput(**values)  # type: ignore[arg-type]


def test_estimate_value_of_civil_home_in_normal_state_uses_the_omi_range() -> None:
    estimate = estimate_value(_input(cadastral_category=CadastralCategory.A2), QUOTES)

    assert estimate is not None
    assert (estimate.min_value, estimate.max_value) == (100_000, 140_000)
    assert (estimate.min_per_sqm, estimate.max_per_sqm) == (1000, 1400)
    assert (estimate.omi_type, estimate.omi_state) == (OmiType.CIVIL, OmiState.NORMAL)


@pytest.mark.parametrize(
    ("category", "omi_type"),
    [
        (CadastralCategory.A3, OmiType.ECONOMIC),
        (CadastralCategory.A4, OmiType.ECONOMIC),
        (CadastralCategory.A7, OmiType.VILLA),
        (CadastralCategory.A1, OmiType.CIVIL),  # no luxury quotation in the zone: next best
    ],
)
def test_estimate_value_chooses_the_omi_type_from_the_cadastral_category(
    category: CadastralCategory, omi_type: OmiType
) -> None:
    estimate = estimate_value(_input(cadastral_category=category), QUOTES)

    assert estimate is not None and estimate.omi_type is omi_type


def test_estimate_value_of_unknown_category_uses_the_property_type() -> None:
    estimate = estimate_value(_input(property_type=PropertyType.VILLA), QUOTES)

    assert estimate is not None and estimate.omi_type is OmiType.VILLA


def test_estimate_value_of_renovated_home_uses_the_excellent_quotation() -> None:
    estimate = estimate_value(_input(condition=PropertyCondition.RENOVATED), QUOTES)

    assert estimate is not None
    assert estimate.omi_state is OmiState.EXCELLENT
    assert (estimate.min_value, estimate.max_value) == (140_000, 180_000)


def test_estimate_value_without_poor_quotation_lowers_the_normal_one() -> None:
    estimate = estimate_value(_input(condition=PropertyCondition.TO_RENOVATE), QUOTES)

    assert estimate is not None
    assert (estimate.omi_state, estimate.factor) == (OmiState.NORMAL, 0.8)
    assert (estimate.min_value, estimate.max_value) == (80_000, 112_000)


def test_estimate_value_with_recent_works_on_a_house_raises_the_range() -> None:
    house = _input(property_type=PropertyType.HOUSE, building_works=BuildingWorks.YES)
    flat = _input(building_works=BuildingWorks.YES)

    house_estimate = estimate_value(house, QUOTES)
    flat_estimate = estimate_value(flat, QUOTES)

    assert house_estimate is not None and house_estimate.factor == 1.05
    assert flat_estimate is not None and flat_estimate.factor == 1.03


def test_estimate_value_rounds_outwards_to_the_thousand() -> None:
    estimate = estimate_value(_input(surface_sqm=87), QUOTES)

    assert estimate is not None
    assert (estimate.min_value, estimate.max_value) == (87_000, 122_000)


@pytest.mark.parametrize("kind", [PropertyType.COMMERCIAL, PropertyType.LAND, PropertyType.OTHER])
def test_estimate_value_of_non_residential_type_returns_none(kind: PropertyType) -> None:
    assert estimate_value(_input(property_type=kind), QUOTES) is None


def test_estimate_value_without_matching_quotation_returns_none() -> None:
    only_villas = [_quote(OmiType.VILLA, OmiState.NORMAL, 1200, 1700)]

    assert estimate_value(_input(cadastral_category=CadastralCategory.A3), only_villas) is None


@pytest.mark.parametrize(
    ("floor", "elevator", "expected"),
    [(0, None, 0.95), (4, False, 0.92), (3, True, 1.02), (1, False, 1.0), (None, None, 1.0)],
)
def test_floor_factor_for_apartments(
    floor: int | None, elevator: bool | None, expected: float
) -> None:
    assert floor_factor(_input(floor=floor, has_elevator=elevator)) == expected


def test_floor_factor_ignores_floor_of_houses() -> None:
    assert floor_factor(_input(property_type=PropertyType.HOUSE, floor=0)) == 1.0
