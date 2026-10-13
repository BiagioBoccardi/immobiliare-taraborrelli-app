from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.enums import PropertyStatus
from app.services.presenter import Presenter
from app.storage.images import JPEG, PNG, WEBP, ImageFormat, detect_image_format
from tests.factories import JPEG_BYTES, PNG_BYTES, WEBP_BYTES, make_photo, make_property
from tests.unit.fakes import InMemoryStorage

presenter = Presenter(InMemoryStorage())


@pytest.mark.parametrize(
    ("data", "expected"), [(JPEG_BYTES, JPEG), (PNG_BYTES, PNG), (WEBP_BYTES, WEBP)]
)
def test_detect_image_format_recognizes_supported_types(data: bytes, expected: ImageFormat) -> None:
    result = detect_image_format(data)

    assert result == expected


@pytest.mark.parametrize("data", [b"GIF89a....", b"%PDF-1.7", b"", b"RIFF1234WAVE"])
def test_detect_image_format_rejects_other_files(data: bytes) -> None:
    result = detect_image_format(data)

    assert result is None


def test_coordinates_are_rounded_when_location_is_not_exact() -> None:
    item = make_property(latitude=Decimal("42.351678"), longitude=Decimal("14.167234"))

    coordinates = presenter.coordinates(item)

    assert coordinates is not None
    assert (coordinates.latitude, coordinates.longitude) == (Decimal("42.352"), Decimal("14.167"))
    assert coordinates.exact is False


def test_coordinates_are_exact_when_agency_allows_it() -> None:
    item = make_property(show_exact_location=True)

    coordinates = presenter.coordinates(item)

    assert coordinates is not None
    assert coordinates.latitude == Decimal("42.351234")
    assert coordinates.exact is True


def test_coordinates_missing_returns_none() -> None:
    item = make_property(latitude=None, longitude=None)

    assert presenter.coordinates(item) is None


def test_public_detail_does_not_expose_address() -> None:
    item = make_property()

    detail = presenter.detail(item)

    assert "address" not in detail.model_dump()
    assert "Via di Prova" not in detail.model_dump_json()


def test_card_uses_first_photo_as_cover() -> None:
    item = make_property(photos=2)

    card = presenter.card(item)

    assert card.cover_photo is not None
    assert card.cover_photo.id == item.photos[0].id
    assert card.cover_photo.url.startswith("https://media.test/properties/")


def test_sold_card_shows_only_area_type_and_authorized_photos() -> None:
    item = make_property(
        photos=0, status=PropertyStatus.SOLD, closed_at=datetime(2026, 9, 1, tzinfo=UTC)
    )
    authorized = make_photo(0, show_when_sold=True)
    item.photos = [authorized, make_photo(1)]

    card = presenter.sold(item)

    dumped = card.model_dump()
    assert [photo.id for photo in card.photos] == [authorized.id]
    assert "price" not in dumped
    assert "address" not in dumped
    assert "title" not in dumped
    assert card.closed_on is not None
    assert card.closed_on.isoformat() == "2026-09-01"


def test_admin_output_includes_address_and_photo_flags() -> None:
    item = make_property()

    out = presenter.admin(item)

    assert out.address == "Via di Prova 1"
    assert out.reference.startswith("TR")
    assert out.photos[0].show_when_sold is False
