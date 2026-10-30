"""Automatic estimate of a home from the OMI quotations of its zone.

Always indicative: it is shown as a range and leads to the free professional valuation.
The cadastral category chooses the OMI building type, the condition chooses the OMI
maintenance state, and the works on the building and the floor adjust the range.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil, floor

from app.models.enums import (
    BuildingWorks,
    CadastralCategory,
    OmiState,
    OmiType,
    PropertyCondition,
    PropertyType,
)
from app.models.omi import OmiQuote

SUPPORTED_TYPES = {
    PropertyType.APARTMENT,
    PropertyType.ATTIC,
    PropertyType.HOUSE,
    PropertyType.VILLA,
}
FLAT_TYPES = {PropertyType.APARTMENT, PropertyType.ATTIC}

# Building types to try, best match first.
TYPES_BY_CATEGORY: dict[CadastralCategory, tuple[OmiType, ...]] = {
    CadastralCategory.A1: (OmiType.LUXURY, OmiType.CIVIL),
    CadastralCategory.A2: (OmiType.CIVIL, OmiType.ECONOMIC),
    CadastralCategory.A3: (OmiType.ECONOMIC, OmiType.CIVIL),
    CadastralCategory.A4: (OmiType.ECONOMIC, OmiType.CIVIL),
    CadastralCategory.A5: (OmiType.ECONOMIC, OmiType.CIVIL),
    CadastralCategory.A6: (OmiType.ECONOMIC, OmiType.CIVIL),
    CadastralCategory.A7: (OmiType.VILLA, OmiType.CIVIL),
    CadastralCategory.A8: (OmiType.VILLA, OmiType.LUXURY, OmiType.CIVIL),
}
TYPES_BY_PROPERTY: dict[PropertyType, tuple[OmiType, ...]] = {
    PropertyType.VILLA: (OmiType.VILLA, OmiType.CIVIL),
    PropertyType.HOUSE: (OmiType.CIVIL, OmiType.VILLA, OmiType.ECONOMIC),
    PropertyType.APARTMENT: (OmiType.CIVIL, OmiType.ECONOMIC),
    PropertyType.ATTIC: (OmiType.CIVIL, OmiType.ECONOMIC),
}

# Maintenance state matching the owner's answer, with an extra adjustment.
STATE_BY_CONDITION: dict[PropertyCondition, tuple[OmiState, float]] = {
    PropertyCondition.TO_RENOVATE: (OmiState.POOR, 1.0),
    PropertyCondition.GOOD: (OmiState.NORMAL, 1.0),
    PropertyCondition.RENOVATED: (OmiState.EXCELLENT, 1.0),
    PropertyCondition.NEW: (OmiState.EXCELLENT, 1.05),
}
# Typical ratio between states, used when the zone has no quotation for the wanted state.
STATE_LEVEL = {OmiState.POOR: 0.80, OmiState.NORMAL: 1.0, OmiState.EXCELLENT: 1.15}

WORKS_FACTOR = {
    # Apartments: works on the building (facade, roof, insulation, common systems).
    True: {BuildingWorks.YES: 1.03, BuildingWorks.NO: 0.98, BuildingWorks.UNKNOWN: 1.0},
    # Detached houses and villas: the works are on the house itself.
    False: {BuildingWorks.YES: 1.05, BuildingWorks.NO: 0.97, BuildingWorks.UNKNOWN: 1.0},
}


@dataclass(frozen=True)
class EstimateInput:
    property_type: PropertyType
    surface_sqm: int
    condition: PropertyCondition
    cadastral_category: CadastralCategory = CadastralCategory.UNKNOWN
    building_works: BuildingWorks = BuildingWorks.UNKNOWN
    floor: int | None = None
    has_elevator: bool | None = None


@dataclass(frozen=True)
class Estimate:
    min_value: int
    max_value: int
    min_per_sqm: int
    max_per_sqm: int
    omi_type: OmiType
    omi_state: OmiState
    factor: float


def floor_factor(data: EstimateInput) -> float:
    if data.property_type not in FLAT_TYPES or data.floor is None:
        return 1.0
    if data.floor <= 0:
        return 0.95  # ground floor and basements
    if data.floor >= 3 and data.has_elevator is False:
        return 0.92  # many stairs
    if data.floor >= 2 and data.has_elevator:
        return 1.02  # high floor, bright, with elevator
    return 1.0


def _quote_for(quotes: Sequence[OmiQuote], data: EstimateInput) -> tuple[OmiQuote, float] | None:
    """The quotation to start from and the adjustment for a missing maintenance state."""
    preferred = (
        TYPES_BY_PROPERTY[data.property_type]
        if data.cadastral_category is CadastralCategory.UNKNOWN
        else TYPES_BY_CATEGORY[data.cadastral_category]
    )
    target, extra = STATE_BY_CONDITION[data.condition]
    for omi_type in preferred:
        rows = [q for q in quotes if q.omi_type is omi_type]
        if not rows:
            continue
        exact = next((q for q in rows if q.state is target), None)
        if exact is not None:
            return exact, extra
        base = next((q for q in rows if q.state is OmiState.NORMAL), None) or next(
            (q for q in rows if q.prevalent), rows[0]
        )
        return base, extra * STATE_LEVEL[target] / STATE_LEVEL[base.state]
    return None


def estimate_value(data: EstimateInput, quotes: Sequence[OmiQuote]) -> Estimate | None:
    """The indicative value range, or None when the zone has no suitable quotation."""
    if data.property_type not in SUPPORTED_TYPES:
        return None
    found = _quote_for(quotes, data)
    if found is None:
        return None
    quote, state_factor = found
    factor = (
        state_factor
        * WORKS_FACTOR[data.property_type in FLAT_TYPES][data.building_works]
        * floor_factor(data)
    )
    min_per_sqm = quote.sale_min * factor
    max_per_sqm = quote.sale_max * factor
    return Estimate(
        # Rounded to the thousand, outwards: a range, never a precise price.
        min_value=floor(min_per_sqm * data.surface_sqm / 1000) * 1000,
        max_value=ceil(max_per_sqm * data.surface_sqm / 1000) * 1000,
        min_per_sqm=round(min_per_sqm),
        max_per_sqm=round(max_per_sqm),
        omi_type=quote.omi_type,
        omi_state=quote.state,
        factor=round(factor, 4),
    )
