import uuid
from datetime import UTC, datetime

import pytest
from py_common.errors import AppError, ConflictError, NotFoundError
from py_common.events import InMemoryEventPublisher
from py_common.pagination import PageParams

from app.models.enums import PropertyStatus
from app.models.property import Property
from app.schemas.property import PhotoOrder, PhotoUpdate, PropertyCreate, PropertyUpdate
from app.services.properties import PropertyService
from tests.factories import (
    JPEG_BYTES,
    PNG_BYTES,
    make_property,
    property_payload,
)
from tests.unit.fakes import FakePropertyRepository, InMemoryStorage

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)


def build(
    items: list[Property] | None = None,
    storage: InMemoryStorage | None = None,
) -> tuple[PropertyService, FakePropertyRepository, InMemoryStorage, InMemoryEventPublisher]:
    repo = FakePropertyRepository(items)
    storage = storage or InMemoryStorage()
    publisher = InMemoryEventPublisher()
    service = PropertyService(
        repo, storage, publisher, max_photo_bytes=1024, max_photos=3, clock=lambda: NOW
    )
    return service, repo, storage, publisher


async def test_create_stores_draft_with_reference() -> None:
    service, repo, _, publisher = build()

    out = await service.create(PropertyCreate.model_validate(property_payload()))

    assert out.status is PropertyStatus.DRAFT
    assert out.reference == "TR00101"
    assert repo.items[out.id].features == ["balcony", "elevator"]
    assert publisher.events == []


async def test_publish_without_photos_raises_photo_required() -> None:
    item = make_property(photos=0, status=PropertyStatus.DRAFT)
    service, _, _, _ = build([item])

    with pytest.raises(ConflictError) as exc_info:
        await service.change_status(item.id, PropertyStatus.PUBLISHED)

    assert exc_info.value.code == "photo_required"


async def test_publish_emits_published_event_and_sets_date() -> None:
    item = make_property(status=PropertyStatus.DRAFT, published_at=None, features=["garden"])
    service, _, _, publisher = build([item])

    out = await service.change_status(item.id, PropertyStatus.PUBLISHED)

    [event] = publisher.events
    assert out.published_at == NOW
    assert event.event_type == "property.published"
    assert event.payload.features == ("garden",)
    assert "Via di Prova" not in event.model_dump_json()


async def test_reserving_a_published_property_emits_nothing() -> None:
    item = make_property()
    service, _, _, publisher = build([item])

    await service.change_status(item.id, PropertyStatus.RESERVED)

    assert publisher.events == []


async def test_selling_emits_unpublished_and_sets_closed_date() -> None:
    item = make_property()
    service, _, _, publisher = build([item])

    out = await service.change_status(item.id, PropertyStatus.SOLD)

    [event] = publisher.events
    assert event.event_type == "property.unpublished"
    assert event.payload.status == "sold"
    assert out.closed_at == NOW


async def test_invalid_transition_raises_with_allowed_statuses() -> None:
    item = make_property(status=PropertyStatus.SOLD)
    service, _, _, _ = build([item])

    with pytest.raises(ConflictError) as exc_info:
        await service.change_status(item.id, PropertyStatus.PUBLISHED)

    assert exc_info.value.code == "invalid_status_transition"
    assert exc_info.value.details == {"allowed": ["archived"]}


async def test_same_status_is_a_no_op() -> None:
    item = make_property()
    service, repo, _, _ = build([item])

    await service.change_status(item.id, PropertyStatus.PUBLISHED)

    assert repo.commits == 0


async def test_price_change_on_published_property_emits_event() -> None:
    item = make_property(price=120_000)
    service, _, _, publisher = build([item])

    await service.update(item.id, PropertyUpdate(price=110_000))

    [event] = publisher.events
    assert event.event_type == "property.price_changed"
    assert (event.payload.old_price, event.payload.new_price) == (120_000, 110_000)


async def test_price_change_on_draft_emits_nothing() -> None:
    item = make_property(status=PropertyStatus.DRAFT)
    service, _, _, publisher = build([item])

    await service.update(item.id, PropertyUpdate(price=99_000))

    assert publisher.events == []


async def test_update_making_data_inconsistent_raises_invalid_property() -> None:
    item = make_property()
    service, _, _, _ = build([item])

    with pytest.raises(AppError) as exc_info:
        await service.update(
            item.id, PropertyUpdate.model_validate({"accommodation": "single_room"})
        )

    assert exc_info.value.code == "invalid_property"


async def test_update_can_clear_optional_field() -> None:
    item = make_property(zone="Centro")
    service, _, _, _ = build([item])

    out = await service.update(item.id, PropertyUpdate.model_validate({"zone": None}))

    assert out.zone is None


async def test_get_public_of_draft_raises_not_found() -> None:
    item = make_property(status=PropertyStatus.DRAFT)
    service, _, _, _ = build([item])

    with pytest.raises(NotFoundError):
        await service.get_public(item.id)


async def test_delete_published_property_raises_conflict() -> None:
    item = make_property()
    service, _, _, _ = build([item])

    with pytest.raises(ConflictError) as exc_info:
        await service.delete(item.id)

    assert exc_info.value.code == "property_not_deletable"


async def test_delete_draft_removes_stored_photos() -> None:
    item = make_property(status=PropertyStatus.DRAFT, photos=2)
    storage = InMemoryStorage()
    for photo in item.photos:
        storage.objects[photo.storage_key] = (JPEG_BYTES, "image/jpeg")
    service, repo, _, _ = build([item], storage)

    await service.delete(item.id)

    assert item.id not in repo.items
    assert storage.objects == {}


async def test_add_photo_stores_file_with_detected_type() -> None:
    item = make_property(photos=0, status=PropertyStatus.DRAFT)
    service, _, storage, _ = build([item])

    out = await service.add_photo(item.id, PNG_BYTES, caption="Soggiorno")

    [(key, (_, content_type))] = storage.objects.items()
    assert key.startswith(f"properties/{item.id}/") and key.endswith(".png")
    assert content_type == "image/png"
    assert out.photos[0].caption == "Soggiorno"


async def test_add_photo_with_fake_image_raises_invalid_photo() -> None:
    item = make_property(photos=0)
    service, _, storage, _ = build([item])

    with pytest.raises(AppError) as exc_info:
        await service.add_photo(item.id, b"<script>alert(1)</script>")

    assert exc_info.value.code == "invalid_photo"
    assert storage.objects == {}


async def test_add_photo_too_large_raises_photo_too_large() -> None:
    item = make_property(photos=0)
    service, _, _, _ = build([item])

    with pytest.raises(AppError) as exc_info:
        await service.add_photo(item.id, JPEG_BYTES + b"\x00" * 2000)

    assert exc_info.value.code == "photo_too_large"


async def test_add_photo_over_limit_raises_too_many_photos() -> None:
    item = make_property(photos=3)
    service, _, _, _ = build([item])

    with pytest.raises(ConflictError) as exc_info:
        await service.add_photo(item.id, JPEG_BYTES)

    assert exc_info.value.code == "too_many_photos"


async def test_add_photo_when_database_fails_removes_stored_file() -> None:
    item = make_property(photos=0)
    service, repo, storage, _ = build([item])
    repo.fail_on_commit = True

    with pytest.raises(RuntimeError):
        await service.add_photo(item.id, JPEG_BYTES)

    assert storage.objects == {}


async def test_reorder_photos_changes_cover() -> None:
    item = make_property(photos=3)
    service, _, _, _ = build([item])
    new_order = [item.photos[2].id, item.photos[0].id, item.photos[1].id]

    out = await service.reorder_photos(item.id, PhotoOrder(photo_ids=new_order))

    assert [photo.id for photo in out.photos] == new_order
    assert [photo.position for photo in out.photos] == [0, 1, 2]


async def test_reorder_with_missing_photo_raises_invalid_order() -> None:
    item = make_property(photos=2)
    service, _, _, _ = build([item])

    with pytest.raises(AppError) as exc_info:
        await service.reorder_photos(item.id, PhotoOrder(photo_ids=[item.photos[0].id]))

    assert exc_info.value.code == "invalid_photo_order"


async def test_delete_last_photo_of_published_property_raises_photo_required() -> None:
    item = make_property(photos=1)
    service, _, _, _ = build([item])

    with pytest.raises(ConflictError) as exc_info:
        await service.delete_photo(item.id, item.photos[0].id)

    assert exc_info.value.code == "photo_required"


async def test_delete_photo_renumbers_and_removes_file() -> None:
    item = make_property(photos=2, status=PropertyStatus.DRAFT)
    first, second = item.photos
    storage = InMemoryStorage()
    storage.objects[first.storage_key] = (JPEG_BYTES, "image/jpeg")
    service, _, _, _ = build([item], storage)

    out = await service.delete_photo(item.id, first.id)

    assert [(p.id, p.position) for p in out.photos] == [(second.id, 0)]
    assert storage.objects == {}


async def test_update_photo_authorizes_it_for_sold_section() -> None:
    item = make_property(photos=1)
    service, _, _, _ = build([item])

    out = await service.update_photo(item.id, item.photos[0].id, PhotoUpdate(show_when_sold=True))

    assert out.photos[0].show_when_sold is True


async def test_update_unknown_photo_raises_not_found() -> None:
    item = make_property(photos=1)
    service, _, _, _ = build([item])

    with pytest.raises(NotFoundError):
        await service.update_photo(item.id, uuid.uuid4(), PhotoUpdate(caption="x"))


async def test_list_sold_returns_only_sold() -> None:
    service, _, _, _ = build([make_property(status=PropertyStatus.SOLD), make_property()])

    page = await service.list_sold(PageParams())

    assert page.total == 1
