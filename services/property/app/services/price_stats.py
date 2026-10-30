"""€/m² of the agency's own sale listings, for the indicative estimate of the lead service.

The most specific group with enough listings wins: same municipality and kind of home, same
municipality, whole agency and kind of home, whole agency.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median, quantiles
from typing import Literal

from app.models.enums import PropertyType

Scope = Literal["municipality_type", "municipality", "agency_type", "agency"]

MIN_LISTINGS = 3
# Values outside this range are typing mistakes (e.g. the price of a garage as a flat).
PLAUSIBLE_PER_SQM = (200.0, 10_000.0)

# Kinds of home compared with each other.
GROUPS: dict[PropertyType, frozenset[PropertyType]] = {
    PropertyType.APARTMENT: frozenset({PropertyType.APARTMENT, PropertyType.ATTIC}),
    PropertyType.ATTIC: frozenset({PropertyType.APARTMENT, PropertyType.ATTIC}),
    PropertyType.HOUSE: frozenset({PropertyType.HOUSE, PropertyType.VILLA}),
    PropertyType.VILLA: frozenset({PropertyType.HOUSE, PropertyType.VILLA}),
}
RESIDENTIAL = frozenset(GROUPS)


@dataclass(frozen=True)
class Sample:
    municipality: str
    property_type: PropertyType
    price: int
    surface_sqm: int

    @property
    def per_sqm(self) -> float:
        return self.price / self.surface_sqm


@dataclass(frozen=True)
class PriceStats:
    scope: Scope
    listings: int
    low_per_sqm: int
    median_per_sqm: int
    high_per_sqm: int


def _same_place(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def _summary(scope: Scope, values: list[float]) -> PriceStats:
    middle = median(values)
    if len(values) >= 4:
        low, _, high = quantiles(values, n=4)  # middle half of the listings
    else:
        low, high = middle * 0.9, middle * 1.1
    return PriceStats(scope, len(values), round(low), round(middle), round(high))


def price_stats(
    samples: Sequence[Sample], municipality: str | None, property_type: PropertyType | None
) -> PriceStats | None:
    usable = [
        s
        for s in samples
        if s.property_type in RESIDENTIAL
        and s.surface_sqm > 0
        and PLAUSIBLE_PER_SQM[0] <= s.per_sqm <= PLAUSIBLE_PER_SQM[1]
    ]
    group = GROUPS.get(property_type) if property_type is not None else None
    in_place = (
        [s for s in usable if _same_place(s.municipality, municipality)] if municipality else []
    )
    candidates: list[tuple[Scope, list[Sample]]] = [
        ("municipality_type", [s for s in in_place if group and s.property_type in group]),
        ("municipality", in_place),
        ("agency_type", [s for s in usable if group and s.property_type in group]),
        ("agency", usable),
    ]
    for scope, chosen in candidates:
        if len(chosen) >= MIN_LISTINGS:
            return _summary(scope, [s.per_sqm for s in chosen])
    # A very small catalog: whatever there is, rather than no estimate at all.
    return _summary("agency", [s.per_sqm for s in usable]) if usable else None
