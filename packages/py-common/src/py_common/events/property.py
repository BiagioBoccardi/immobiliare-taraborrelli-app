"""Events emitted by the property service.

Payloads carry the attributes other services need to match saved searches and update
favorites. They never contain personal data (the catalog has none).
"""

import uuid
from typing import Literal

from py_common.events.base import EventPayload

ContractName = Literal["sale", "rent"]


class PropertyPublishedV1(EventPayload):
    event_type = "property.published"
    version = 1

    property_id: uuid.UUID
    contract: ContractName
    property_type: str
    municipality: str
    zone: str | None
    price: int
    surface_sqm: int
    rooms: int | None
    features: tuple[str, ...]


class PropertyPriceChangedV1(EventPayload):
    event_type = "property.price_changed"
    version = 1

    property_id: uuid.UUID
    contract: ContractName
    old_price: int
    new_price: int


class PropertyUnpublishedV1(EventPayload):
    """The property left the public catalog (sold, rented, withdrawn or archived)."""

    event_type = "property.unpublished"
    version = 1

    property_id: uuid.UUID
    status: Literal["draft", "sold", "rented", "archived"]
