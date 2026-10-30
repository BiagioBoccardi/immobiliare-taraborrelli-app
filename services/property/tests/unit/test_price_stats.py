import pytest

from app.models.enums import PropertyType
from app.services.price_stats import Sample, price_stats

A, H, V = PropertyType.APARTMENT, PropertyType.HOUSE, PropertyType.VILLA


def _sample(place: str, kind: PropertyType, per_sqm: int, surface: int = 100) -> Sample:
    return Sample(place, kind, per_sqm * surface, surface)


def test_price_stats_uses_same_municipality_and_kind_first() -> None:
    samples = [_sample("Chieti", A, v) for v in (1000, 1200, 1400, 1600)] + [
        _sample("Chieti", H, 3000)
    ]

    stats = price_stats(samples, " chieti ", A)

    assert stats is not None
    assert (stats.scope, stats.listings) == ("municipality_type", 4)
    assert stats.median_per_sqm == 1300
    assert stats.low_per_sqm < stats.median_per_sqm < stats.high_per_sqm


def test_price_stats_treats_attics_like_apartments() -> None:
    samples = [_sample("Chieti", A, 1000), _sample("Chieti", A, 1100)]
    samples.append(_sample("Chieti", PropertyType.ATTIC, 1500))

    stats = price_stats(samples, "Chieti", PropertyType.ATTIC)

    assert stats is not None and (stats.scope, stats.listings) == ("municipality_type", 3)


def test_price_stats_with_few_of_the_kind_uses_the_whole_municipality() -> None:
    samples = [_sample("Chieti", A, 1000), _sample("Chieti", A, 1100), _sample("Chieti", V, 1800)]

    stats = price_stats(samples, "Chieti", V)

    assert stats is not None and (stats.scope, stats.listings) == ("municipality", 3)


def test_price_stats_of_unknown_municipality_uses_the_agency() -> None:
    samples = [_sample("Chieti", H, v) for v in (900, 1000, 1100)]

    stats = price_stats(samples, "Pescara", H)

    assert stats is not None and stats.scope == "agency_type"


def test_price_stats_with_few_listings_spreads_ten_percent_around_the_median() -> None:
    samples = [_sample("Chieti", A, 1000), _sample("Chieti", A, 1200)]

    stats = price_stats(samples, "Chieti", A)

    assert stats is not None
    assert (stats.low_per_sqm, stats.median_per_sqm, stats.high_per_sqm) == (990, 1100, 1210)


def test_price_stats_ignores_garages_land_and_implausible_values() -> None:
    samples = [
        _sample("Chieti", PropertyType.GARAGE, 1000),
        _sample("Chieti", PropertyType.LAND, 50),
        _sample("Chieti", A, 50_000),
    ]

    assert price_stats(samples, "Chieti", A) is None


@pytest.mark.parametrize("kind", [None, PropertyType.COMMERCIAL])
def test_price_stats_without_residential_kind_uses_all_homes(kind: PropertyType | None) -> None:
    samples = [_sample("Chieti", A, 1000), _sample("Chieti", H, 1100), _sample("Chieti", V, 1200)]

    stats = price_stats(samples, "Chieti", kind)

    assert stats is not None and stats.scope == "municipality"
