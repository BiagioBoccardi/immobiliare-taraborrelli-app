import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, cast

from py_common.errors import AppError, ConflictError, NotFoundError
from py_common.events import Event, EventPublisher
from py_common.events.property import (
    PropertyPriceChangedV1,
    PropertyPublishedV1,
    PropertyUnpublishedV1,
)
from py_common.pagination import Page, PageParams
from pydantic import ValidationError

from app.models.enums import (
    PUBLIC_STATUSES,
    STATUS_TRANSITIONS,
    PropertyStatus,
)
from app.models.property import Photo, Property
from app.repositories.properties import PropertyRepository
from app.schemas.property import (
    AdminFilters,
    AdminPropertyOut,
    PhotoOrder,
    PhotoUpdate,
    PropertyCard,
    PropertyCreate,
    PropertyDetail,
    PropertyFields,
    PropertyUpdate,
    SearchFilters,
    SoldCard,
)
from app.services.presenter import Presenter
from app.storage.base import MediaStorage
from app.storage.images import detect_image_format

logger = logging.getLogger(__name__)

PRODUCER = "property"
# Listing photos are stored under this prefix, which is publicly readable.
PUBLIC_MEDIA_PREFIX = "properties/"
EDITABLE_FIELDS = tuple(PropertyFields.model_fields)


def utcnow() -> datetime:
    return datetime.now(UTC)


def _column_values(fields: PropertyFields) -> dict[str, Any]:
    """Field values ready for the model: enum lists are stored as plain strings."""
    values = fields.model_dump()
    values["features"] = [feature.value for feature in fields.features]
    values["tenant_types"] = [tenant.value for tenant in fields.tenant_types]
    return values


class PropertyService:
    def __init__(
        self,
        repository: PropertyRepository,
        storage: MediaStorage,
        publisher: EventPublisher,
        max_photo_bytes: int,
        max_photos: int,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._repo = repository
        self._storage = storage
        self._publisher = publisher
        self._max_photo_bytes = max_photo_bytes
        self._max_photos = max_photos
        self._clock = clock
        self._present = Presenter(storage)

    # Public catalog -----------------------------------------------------------------------

    async def search(self, filters: SearchFilters, params: PageParams) -> Page[PropertyCard]:
        items, total = await self._repo.search(filters, params.offset, params.size)
        return Page[PropertyCard](
            items=[self._present.card(item) for item in items],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def get_public(self, property_id: uuid.UUID) -> PropertyDetail:
        item = await self._repo.get(property_id)
        if item is None or item.status not in PUBLIC_STATUSES:
            raise NotFoundError("Property not found")
        return self._present.detail(item)

    async def list_sold(self, params: PageParams) -> Page[SoldCard]:
        items, total = await self._repo.list_sold(params.offset, params.size)
        return Page[SoldCard](
            items=[self._present.sold(item) for item in items],
            total=total,
            page=params.page,
            size=params.size,
        )

    # Admin panel --------------------------------------------------------------------------

    async def list_admin(self, filters: AdminFilters, params: PageParams) -> Page[AdminPropertyOut]:
        items, total = await self._repo.list_admin(filters, params.offset, params.size)
        return Page[AdminPropertyOut](
            items=[self._present.admin(item) for item in items],
            total=total,
            page=params.page,
            size=params.size,
        )

    async def get_admin(self, property_id: uuid.UUID) -> AdminPropertyOut:
        return self._present.admin(await self._get(property_id))

    async def create(self, data: PropertyCreate) -> AdminPropertyOut:
        now = self._clock()
        item = Property(
            id=uuid.uuid4(),
            status=PropertyStatus.DRAFT,
            created_at=now,
            updated_at=now,
            **_column_values(data),
        )
        item = await self._repo.add(item)
        await self._repo.commit()
        return self._present.admin(item)

    async def update(self, property_id: uuid.UUID, changes: PropertyUpdate) -> AdminPropertyOut:
        item = await self._get(property_id)
        current = {name: getattr(item, name) for name in EDITABLE_FIELDS}
        merged = {**current, **changes.model_dump(exclude_unset=True)}
        try:
            validated = PropertyFields.model_validate(merged)
        except ValidationError as exc:
            raise AppError(
                "The property data is not consistent",
                code="invalid_property",
                details={"errors": [e["msg"] for e in exc.errors()]},
            ) from exc
        old_price = item.price
        for name, value in _column_values(validated).items():
            setattr(item, name, value)
        item.updated_at = self._clock()
        await self._repo.commit()
        if item.status in PUBLIC_STATUSES and item.price != old_price:
            await self._emit(
                PropertyPriceChangedV1(
                    property_id=item.id,
                    contract=item.contract.value,
                    old_price=old_price,
                    new_price=item.price,
                )
            )
        return self._present.admin(item)

    async def change_status(
        self, property_id: uuid.UUID, new_status: PropertyStatus
    ) -> AdminPropertyOut:
        item = await self._get(property_id)
        old_status = item.status
        if new_status is old_status:
            return self._present.admin(item)
        if new_status not in STATUS_TRANSITIONS[old_status]:
            raise ConflictError(
                f"A property cannot go from {old_status.value} to {new_status.value}",
                code="invalid_status_transition",
                details={"allowed": sorted(s.value for s in STATUS_TRANSITIONS[old_status])},
            )
        if new_status in PUBLIC_STATUSES and not item.photos:
            raise ConflictError("Add at least one photo before publishing", code="photo_required")
        now = self._clock()
        item.status = new_status
        item.updated_at = now
        if old_status not in PUBLIC_STATUSES and new_status in PUBLIC_STATUSES:
            item.published_at = now
        if new_status in {PropertyStatus.SOLD, PropertyStatus.RENTED}:
            item.closed_at = now
        await self._repo.commit()

        if old_status not in PUBLIC_STATUSES and new_status in PUBLIC_STATUSES:
            await self._emit(
                PropertyPublishedV1(
                    property_id=item.id,
                    contract=item.contract.value,
                    property_type=item.property_type.value,
                    municipality=item.municipality,
                    zone=item.zone,
                    price=item.price,
                    surface_sqm=item.surface_sqm,
                    rooms=item.rooms,
                    features=tuple(item.features),
                )
            )
        elif old_status in PUBLIC_STATUSES and new_status not in PUBLIC_STATUSES:
            status = cast(Literal["draft", "sold", "rented", "archived"], new_status.value)
            await self._emit(PropertyUnpublishedV1(property_id=item.id, status=status))
        return self._present.admin(item)

    async def delete(self, property_id: uuid.UUID) -> None:
        item = await self._get(property_id)
        if item.status not in {PropertyStatus.DRAFT, PropertyStatus.ARCHIVED}:
            raise ConflictError(
                "Only draft or archived properties can be deleted", code="property_not_deletable"
            )
        keys = [photo.storage_key for photo in item.photos]
        await self._repo.delete(item)
        await self._repo.commit()
        for key in keys:
            await self._delete_object(key)

    # Photos -------------------------------------------------------------------------------

    async def add_photo(
        self, property_id: uuid.UUID, data: bytes, caption: str | None = None
    ) -> AdminPropertyOut:
        item = await self._get(property_id)
        if len(data) > self._max_photo_bytes:
            raise AppError(
                "The photo is too large",
                code="photo_too_large",
                details={"max_bytes": self._max_photo_bytes},
            )
        image = detect_image_format(data)
        if image is None:
            raise AppError("Only JPEG, PNG and WebP photos are accepted", code="invalid_photo")
        if len(item.photos) >= self._max_photos:
            raise ConflictError(
                "Too many photos for this property",
                code="too_many_photos",
                details={"max_photos": self._max_photos},
            )
        photo_id = uuid.uuid4()
        key = f"{PUBLIC_MEDIA_PREFIX}{item.id}/{photo_id}.{image.extension}"
        await self._storage.put(key, data, image.content_type)
        item.photos.append(
            Photo(
                id=photo_id,
                storage_key=key,
                content_type=image.content_type,
                size_bytes=len(data),
                position=len(item.photos),
                caption=caption,
                show_when_sold=False,
                created_at=self._clock(),
            )
        )
        item.updated_at = self._clock()
        try:
            await self._repo.commit()
        except Exception:
            await self._delete_object(key)  # do not leave orphan files in the bucket
            raise
        return self._present.admin(item)

    async def update_photo(
        self, property_id: uuid.UUID, photo_id: uuid.UUID, changes: PhotoUpdate
    ) -> AdminPropertyOut:
        item = await self._get(property_id)
        photo = self._find_photo(item, photo_id)
        for name, value in changes.model_dump(exclude_unset=True).items():
            if name == "show_when_sold" and value is None:
                continue
            setattr(photo, name, value)
        item.updated_at = self._clock()
        await self._repo.commit()
        return self._present.admin(item)

    async def reorder_photos(self, property_id: uuid.UUID, order: PhotoOrder) -> AdminPropertyOut:
        item = await self._get(property_id)
        current = {photo.id: photo for photo in item.photos}
        if sorted(order.photo_ids) != sorted(current):
            raise AppError(
                "The new order must list every photo exactly once", code="invalid_photo_order"
            )
        for position, photo_id in enumerate(order.photo_ids):
            current[photo_id].position = position
        item.photos.sort(key=lambda photo: photo.position)
        item.updated_at = self._clock()
        await self._repo.commit()
        return self._present.admin(item)

    async def delete_photo(self, property_id: uuid.UUID, photo_id: uuid.UUID) -> AdminPropertyOut:
        item = await self._get(property_id)
        photo = self._find_photo(item, photo_id)
        if item.status in PUBLIC_STATUSES and len(item.photos) == 1:
            raise ConflictError(
                "A published property needs at least one photo", code="photo_required"
            )
        key = photo.storage_key
        item.photos.remove(photo)
        for position, remaining in enumerate(item.photos):
            remaining.position = position
        item.updated_at = self._clock()
        await self._repo.commit()
        await self._delete_object(key)
        return self._present.admin(item)

    # Helpers ------------------------------------------------------------------------------

    async def _get(self, property_id: uuid.UUID) -> Property:
        item = await self._repo.get(property_id)
        if item is None:
            raise NotFoundError("Property not found")
        return item

    @staticmethod
    def _find_photo(item: Property, photo_id: uuid.UUID) -> Photo:
        for photo in item.photos:
            if photo.id == photo_id:
                return photo
        raise NotFoundError("Photo not found")

    async def _delete_object(self, key: str) -> None:
        try:
            await self._storage.delete(key)
        except Exception:
            logger.exception("failed to delete a stored photo")

    async def _emit(self, payload: Any) -> None:
        try:
            await self._publisher.publish(Event.wrap(payload, producer=PRODUCER))
        except Exception:
            logger.exception("failed to publish %s", payload.event_type)
