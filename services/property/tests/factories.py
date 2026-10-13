"""Valid test data for the catalog."""

import itertools
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.models.enums import Contract, PropertyStatus, PropertyType
from app.models.property import Photo, Property

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64

_numbers = itertools.count(1)


def property_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "contract": "sale",
        "property_type": "apartment",
        "title": "Trilocale luminoso in centro",
        "description": "Appartamento al secondo piano con balcone.",
        "price": 120_000,
        "surface_sqm": 95,
        "rooms": 3,
        "bedrooms": 2,
        "bathrooms": 1,
        "floor": 2,
        "total_floors": 4,
        "energy_class": "C",
        "features": ["balcony", "elevator"],
        "municipality": "Chieti",
        "zone": "Centro",
        "address": "Via di Prova 1",
        "latitude": "42.351234",
        "longitude": "14.167891",
    }
    data.update(overrides)
    return data


def rental_payload(**overrides: Any) -> dict[str, Any]:
    data = property_payload(
        contract="rent",
        title="Stanza singola per studenti",
        price=280,
        tenant_types=["students"],
        accommodation="single_room",
        available_from="2026-11-01",
        municipality="Chieti Scalo",
        zone=None,
    )
    data.update(overrides)
    return data


def make_photo(position: int = 0, **overrides: Any) -> Photo:
    photo_id = uuid.uuid4()
    values: dict[str, Any] = {
        "id": photo_id,
        "storage_key": f"properties/test/{photo_id}.jpg",
        "content_type": "image/jpeg",
        "size_bytes": len(JPEG_BYTES),
        "position": position,
        "caption": None,
        "show_when_sold": False,
        "created_at": datetime.now(UTC),
    }
    values.update(overrides)
    return Photo(**values)


def make_property(photos: int = 1, **overrides: Any) -> Property:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "number": next(_numbers),
        "status": PropertyStatus.PUBLISHED,
        "contract": Contract.SALE,
        "property_type": PropertyType.APARTMENT,
        "is_featured": False,
        "title": "Trilocale luminoso in centro",
        "description": "Descrizione di prova.",
        "price": 120_000,
        "surface_sqm": 95,
        "rooms": 3,
        "bedrooms": 2,
        "bathrooms": 1,
        "features": [],
        "tenant_types": [],
        "municipality": "Chieti",
        "zone": "Centro",
        "address": "Via di Prova 1",
        "latitude": Decimal("42.351234"),
        "longitude": Decimal("14.167891"),
        "show_exact_location": False,
        "published_at": now,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    item = Property(**values)
    item.photos = [make_photo(position=i) for i in range(photos)]
    return item
