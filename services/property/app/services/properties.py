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
from app.schemas.bulk import BulkResult, BulkSkipped
from app.schemas.imports import (
    ImportColumn,
    ImportPreview,
    ImportResult,
    ImportRowOut,
    ImportTotals,
)
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
from app.services.importer import (
    REQUIRED_FIELDS,
    TEMPLATE_FEATURE_HEADERS,
    TEMPLATE_HEADERS,
    PlannedRow,
    parse_sheet,
    plan_rows,
)
from app.services.presenter import Presenter
from app.services.spreadsheet import Cell, read_spreadsheet, write_spreadsheet
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


# Bulk actions work on at most this many properties at a time.
BULK_LIMIT = 5000


def _published_event(item: Property) -> PropertyPublishedV1:
    return PropertyPublishedV1(
        property_id=item.id,
        contract=item.contract.value,
        property_type=item.property_type.value,
        municipality=item.municipality,
        zone=item.zone,
        price=item.price,
        surface_sqm=item.surface_sqm or 0,  # publishing requires it
        rooms=item.rooms,
        features=tuple(item.features),
    )


class PropertyService:
    def __init__(
        self,
        repository: PropertyRepository,
        storage: MediaStorage,
        publisher: EventPublisher,
        max_photo_bytes: int,
        max_photos: int,
        clock: Callable[[], datetime] = utcnow,
        max_import_rows: int = 2000,
    ) -> None:
        self._repo = repository
        self._storage = storage
        self._publisher = publisher
        self._max_photo_bytes = max_photo_bytes
        self._max_photos = max_photos
        self._clock = clock
        self._max_import_rows = max_import_rows
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
        await self._ensure_external_ref_free(data.external_ref, None)
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
        if item.status in PUBLIC_STATUSES and validated.surface_sqm is None:
            raise ConflictError("A published property needs its surface", code="surface_required")
        await self._ensure_external_ref_free(validated.external_ref, item.id)
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

    async def _ensure_external_ref_free(self, ref: str | None, owner: uuid.UUID | None) -> None:
        """The management software code identifies one listing: it cannot be used twice."""
        if ref is None:
            return
        existing = (await self._repo.find_by_external_refs([ref])).get(ref)
        if existing is not None and existing.id != owner:
            raise ConflictError(
                "Another property already has this management software code",
                code="external_ref_taken",
                details={"reference": existing.reference},
            )

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
        if new_status in PUBLIC_STATUSES and item.surface_sqm is None:
            raise ConflictError("Add the surface before publishing", code="surface_required")
        now = self._clock()
        item.status = new_status
        item.updated_at = now
        if old_status not in PUBLIC_STATUSES and new_status in PUBLIC_STATUSES:
            item.published_at = now
        if new_status in {PropertyStatus.SOLD, PropertyStatus.RENTED}:
            item.closed_at = now
        await self._repo.commit()

        if old_status not in PUBLIC_STATUSES and new_status in PUBLIC_STATUSES:
            await self._emit(_published_event(item))
        elif old_status in PUBLIC_STATUSES and new_status not in PUBLIC_STATUSES:
            status = cast(Literal["draft", "sold", "rented", "archived"], new_status.value)
            await self._emit(PropertyUnpublishedV1(property_id=item.id, status=status))
        return self._present.admin(item)

    async def delete(self, property_id: uuid.UUID) -> None:
        """Deletes a property in any status (the panel asks for confirmation)."""
        await self._delete_items([await self._get(property_id)])

    async def _delete_items(self, items: list[Property]) -> None:
        was_public = [item.id for item in items if item.status in PUBLIC_STATUSES]
        keys = [photo.storage_key for item in items for photo in item.photos]
        for item in items:
            await self._repo.delete(item)
        await self._repo.commit()
        # Listings visible in the app leave the catalog: saved searches and favorites follow.
        for property_id in was_public:
            await self._emit(PropertyUnpublishedV1(property_id=property_id, status="archived"))
        for key in keys:
            await self._delete_object(key)

    # Bulk actions on the properties matching the list filters -----------------------------

    async def _matching(self, filters: AdminFilters) -> list[Property]:
        items, total = await self._repo.list_admin(filters, 0, BULK_LIMIT)
        if total > BULK_LIMIT:
            raise AppError(
                f"Too many properties: at most {BULK_LIMIT} at a time",
                code="too_many_properties",
                details={"max": BULK_LIMIT},
            )
        return items

    async def bulk_publish(self, filters: AdminFilters) -> BulkResult:
        """Publishes the drafts that are ready (photo and surface); explains the others."""
        now = self._clock()
        published: list[Property] = []
        skipped: list[BulkSkipped] = []
        for item in await self._matching(filters):
            reason: str | None = None
            if item.status in PUBLIC_STATUSES:
                reason = "already_published"
            elif item.status is not PropertyStatus.DRAFT:
                reason = "invalid_status_transition"
            elif not item.photos:
                reason = "photo_required"
            elif item.surface_sqm is None:
                reason = "surface_required"
            if reason is not None:
                skipped.append(
                    BulkSkipped(
                        id=item.id, reference=item.reference, title=item.title, reason=reason
                    )
                )
                continue
            item.status = PropertyStatus.PUBLISHED
            item.published_at = now
            item.updated_at = now
            published.append(item)
        await self._repo.commit()
        for item in published:
            await self._emit(_published_event(item))
        return BulkResult(done=len(published), skipped=skipped)

    async def bulk_delete(self, filters: AdminFilters) -> BulkResult:
        items = await self._matching(filters)
        await self._delete_items(items)
        return BulkResult(done=len(items), skipped=[])

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

    # Excel import ---------------------------------------------------------------------------

    async def _plan_import(self, data: bytes) -> tuple[ImportPreview, list[PlannedRow]]:
        sheet = read_spreadsheet(data, self._max_import_rows)
        columns, rows = parse_sheet(sheet)
        refs = {row.values["external_ref"] for row in rows if "external_ref" in row.values}
        existing = await self._repo.find_by_external_refs(refs)
        plan = plan_rows(rows, existing, self._clock().date())
        recognized = [
            ImportColumn(header=sheet.headers[i], field=name) for i, name in columns.fields.items()
        ] + [
            ImportColumn(header=sheet.headers[i], field=f"features.{feature.value}")
            for i, feature in columns.feature_columns.items()
        ]
        preview = ImportPreview(
            columns=sorted(recognized, key=lambda c: sheet.headers.index(c.header)),
            ignored_columns=list(columns.ignored),
            missing_columns=[
                name for name in REQUIRED_FIELDS if name not in columns.fields.values()
            ],
            rows=[
                ImportRowOut(
                    row=p.number,
                    action=p.action,
                    external_ref=p.external_ref,
                    title=p.title,
                    municipality=p.municipality,
                    contract=p.contract,
                    price=p.price,
                    errors=p.errors,
                    warnings=p.warnings,
                )
                for p in plan
            ],
            totals=ImportTotals(
                create=sum(p.action == "create" for p in plan),
                update=sum(p.action == "update" for p in plan),
                invalid=sum(p.action == "invalid" for p in plan),
            ),
        )
        return preview, plan

    async def preview_import(self, data: bytes) -> ImportPreview:
        """Checks the file without changing anything: what would be created, updated, skipped."""
        preview, _ = await self._plan_import(data)
        return preview

    async def run_import(self, data: bytes) -> ImportResult:
        """Imports the valid rows in one transaction; rows with errors are skipped.

        New listings are drafts (photos are added in the panel before publishing); listings
        with the same management software code are updated and keep their status.
        """
        _, plan = await self._plan_import(data)
        now = self._clock()
        price_changes: list[PropertyPriceChangedV1] = []
        for row in plan:
            if row.create is not None:
                item = Property(
                    id=uuid.uuid4(),
                    status=PropertyStatus.DRAFT,
                    created_at=now,
                    updated_at=now,
                    **_column_values(row.create),
                )
                await self._repo.add(item)
            elif row.update is not None:
                item, fields = row.update
                old_price = item.price
                for name, value in _column_values(fields).items():
                    setattr(item, name, value)
                item.updated_at = now
                if item.status in PUBLIC_STATUSES and item.price != old_price:
                    price_changes.append(
                        PropertyPriceChangedV1(
                            property_id=item.id,
                            contract=item.contract.value,
                            old_price=old_price,
                            new_price=item.price,
                        )
                    )
        await self._repo.commit()
        for change in price_changes:
            await self._emit(change)
        created = sum(row.action == "create" for row in plan)
        updated = sum(row.action == "update" for row in plan)
        logger.info("import completed", extra={"rows_created": created, "rows_updated": updated})
        return ImportResult(created=created, updated=updated, skipped=len(plan) - created - updated)

    @staticmethod
    def import_template() -> bytes:
        """Excel template with the recognized columns and two fictional examples."""
        headers = list(TEMPLATE_HEADERS.values()) + list(TEMPLATE_FEATURE_HEADERS.values())
        examples: list[list[Cell]] = [
            ["RS-001", "Vendita", "Appartamento", "Trilocale luminoso con balcone",
             "Esempio: secondo piano con ascensore.", 139000, 80, 95, 3, 2, 1, 2, 4, 1990,
             "Buono", "C", "Chieti", "Centro", "Via di Esempio 1", None,
             "Sì", "No", "No", "No", "No", "Sì", "Sì", "No", "No", "Sì"],
            ["RS-002", "Affitto", "Bilocale", "", "", 450, None, 55, None, 1, 1, "Terra", 3, None,
             "Ristrutturato", "", "Chieti Scalo", "", "", "01/09/2026",
             "No", "Sì", "No", "No", "No", "No", "No", "Sì", "No", "Sì"],
        ]  # fmt: skip
        return write_spreadsheet(headers, examples)

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
