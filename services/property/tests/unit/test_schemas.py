import pytest
from pydantic import ValidationError

from app.models.enums import Feature
from app.schemas.property import PropertyCreate, SearchFilters
from tests.factories import property_payload, rental_payload


def test_create_sorts_and_deduplicates_features() -> None:
    data = PropertyCreate.model_validate(property_payload(features=["garden", "balcony", "garden"]))

    assert data.features == [Feature.BALCONY, Feature.GARDEN]


def test_sale_with_rental_fields_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PropertyCreate.model_validate(property_payload(tenant_types=["students"]))


def test_rental_with_tenant_fields_is_accepted() -> None:
    data = PropertyCreate.model_validate(rental_payload())

    assert data.accommodation is not None


def test_latitude_without_longitude_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PropertyCreate.model_validate(property_payload(longitude=None))


def test_floor_above_total_floors_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PropertyCreate.model_validate(property_payload(floor=5, total_floors=3))


def test_unknown_feature_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PropertyCreate.model_validate(property_payload(features=["swimming_pool"]))


def test_search_with_partial_viewport_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchFilters.model_validate({"min_lat": "42.3"})


def test_search_with_inverted_price_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchFilters(price_min=200_000, price_max=100_000)
