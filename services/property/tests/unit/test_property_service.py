import uuid
from datetime import UTC, datetime

import pytest
from py_common.errors import AppError, ConflictError, NotFoundError
from py_common.events import InMemoryEventPublisher
from py_common.pagination import PageParams

from app.models.enums import PropertyStatus
from app.models.property import Property
from app.schemas.property import (
    AdminFilters,
    PhotoOrder,
    PhotoUpdate,
    PropertyCreate,
    PropertyUpdate,
)
from app.services.importer import parse_sheet, plan_rows
from app.services.properties import PropertyService
from app.services.spreadsheet import read_spreadsheet
from tests.factories import (
    GLB_BYTES,
    JPEG_BYTES,
    PNG_BYTES,
    import_row,
    make_property,
    property_payload,
    spreadsheet_bytes,
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
        repo,
        storage,
        publisher,
        max_photo_bytes=1024,
        max_photos=3,
        clock=lambda: NOW,
        max_model_bytes=2048,
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


async def test_delete_published_property_removes_it_and_emits_unpublished() -> None:
    item = make_property()
    service, repo, _, publisher = build([item])

    await service.delete(item.id)

    assert item.id not in repo.items
    (event,) = publisher.events
    assert event.event_type == "property.unpublished"
    assert event.payload.status == "archived"


async def test_delete_draft_emits_nothing() -> None:
    item = make_property(status=PropertyStatus.DRAFT)
    service, _, _, publisher = build([item])

    await service.delete(item.id)

    assert publisher.events == []


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


# Excel import ------------------------------------------------------------------------------


async def test_run_import_creates_drafts_and_updates_by_management_code() -> None:
    existing = make_property(external_ref="RS-1", price=150_000)
    service, repo, _, _ = build([existing])
    data = spreadsheet_bytes(
        [
            import_row(Riferimento="RS-1", Prezzo="145.000"),
            import_row(Riferimento="RS-2"),
            import_row(Riferimento="RS-3", Prezzo="non so"),
        ]
    )

    result = await service.run_import(data)

    assert (result.created, result.updated, result.skipped) == (1, 1, 1)
    assert existing.price == 145_000
    assert existing.status is PropertyStatus.PUBLISHED
    created = next(i for i in repo.items.values() if i.external_ref == "RS-2")
    assert created.status is PropertyStatus.DRAFT
    assert created.features == ["elevator"]
    assert repo.commits == 1


async def test_run_import_price_change_of_published_listing_emits_event() -> None:
    existing = make_property(external_ref="RS-1", price=150_000)
    service, _, _, publisher = build([existing])

    await service.run_import(spreadsheet_bytes([{"Riferimento": "RS-1", "Prezzo": 140_000}]))

    (event,) = publisher.events
    assert event.event_type == "property.price_changed"
    assert event.payload.new_price == 140_000


async def test_run_import_failed_commit_emits_nothing() -> None:
    existing = make_property(external_ref="RS-1", price=150_000)
    service, repo, _, publisher = build([existing])
    repo.fail_on_commit = True

    with pytest.raises(RuntimeError):
        await service.run_import(spreadsheet_bytes([{"Riferimento": "RS-1", "Prezzo": 1}]))

    assert publisher.events == []


async def test_preview_import_reports_rows_without_saving() -> None:
    service, repo, _, _ = build()
    data = spreadsheet_bytes([import_row(Riferimento="RS-1"), import_row(Superficie="tanta")])

    preview = await service.preview_import(data)

    assert (preview.totals.create, preview.totals.update, preview.totals.invalid) == (1, 0, 1)
    assert preview.rows[1].errors[0].code == "invalid_number"
    assert preview.missing_columns == []
    assert {c.field for c in preview.columns} >= {"external_ref", "price", "features.elevator"}
    assert repo.items == {}
    assert repo.commits == 0


async def test_preview_import_lists_missing_and_ignored_columns() -> None:
    service, _, _, _ = build()

    preview = await service.preview_import(
        spreadsheet_bytes([{"Comune": "Chieti", "Note interne": "x"}])
    )

    assert preview.missing_columns == ["property_type", "price"]
    assert preview.ignored_columns == ["Note interne"]


def test_import_template_is_an_excel_file_that_imports_cleanly() -> None:
    data = PropertyService.import_template()

    sheet = read_spreadsheet(data, max_rows=10)
    _, rows = parse_sheet(sheet)
    planned = plan_rows(rows, {}, NOW.date())

    assert [row.action for row in planned] == ["create", "create"]


async def test_create_with_management_code_of_another_property_raises_conflict() -> None:
    service, _, _, _ = build([make_property(external_ref="RS-1")])

    with pytest.raises(ConflictError) as exc_info:
        await service.create(PropertyCreate.model_validate(property_payload(external_ref="RS-1")))

    assert exc_info.value.code == "external_ref_taken"


async def test_update_keeping_own_management_code_succeeds() -> None:
    item = make_property(external_ref="RS-1")
    service, _, _, _ = build([item])

    out = await service.update(item.id, PropertyUpdate(external_ref="RS-1", price=99_000))

    assert out.external_ref == "RS-1"
    assert out.price == 99_000


async def test_publish_without_surface_raises_surface_required() -> None:
    item = make_property(status=PropertyStatus.DRAFT, surface_sqm=None)
    service, _, _, _ = build([item])

    with pytest.raises(ConflictError) as exc_info:
        await service.change_status(item.id, PropertyStatus.PUBLISHED)

    assert exc_info.value.code == "surface_required"


async def test_removing_surface_of_published_listing_raises_surface_required() -> None:
    item = make_property(status=PropertyStatus.PUBLISHED)
    service, _, _, _ = build([item])

    with pytest.raises(ConflictError) as exc_info:
        await service.update(item.id, PropertyUpdate(surface_sqm=None))

    assert exc_info.value.code == "surface_required"


async def test_run_import_without_surface_creates_draft_to_complete() -> None:
    service, repo, _, _ = build()

    result = await service.run_import(spreadsheet_bytes([import_row(Superficie=None)]))

    (item,) = repo.items.values()
    assert result.created == 1
    assert item.surface_sqm is None
    assert item.status is PropertyStatus.DRAFT


# Bulk actions ---------------------------------------------------------------------------


async def test_bulk_publish_publishes_ready_drafts_and_explains_the_others() -> None:
    ready = make_property(status=PropertyStatus.DRAFT, published_at=None)
    no_photo = make_property(status=PropertyStatus.DRAFT, photos=0)
    no_surface = make_property(status=PropertyStatus.DRAFT, surface_sqm=None)
    public = make_property(status=PropertyStatus.PUBLISHED)
    sold = make_property(status=PropertyStatus.SOLD)
    service, repo, _, publisher = build([ready, no_photo, no_surface, public, sold])

    result = await service.bulk_publish(AdminFilters())

    assert result.done == 1
    assert ready.status is PropertyStatus.PUBLISHED
    assert ready.published_at == NOW
    assert {s.id: s.reason for s in result.skipped} == {
        no_photo.id: "photo_required",
        no_surface.id: "surface_required",
        public.id: "already_published",
        sold.id: "invalid_status_transition",
    }
    assert [e.event_type for e in publisher.events] == ["property.published"]
    assert repo.commits == 1


async def test_bulk_delete_removes_all_with_photos_and_unpublishes_public_ones() -> None:
    draft = make_property(status=PropertyStatus.DRAFT, photos=1)
    public = make_property(status=PropertyStatus.PUBLISHED, photos=1)
    storage = InMemoryStorage()
    for item in (draft, public):
        storage.objects[item.photos[0].storage_key] = (JPEG_BYTES, "image/jpeg")
    service, repo, _, publisher = build([draft, public], storage)

    result = await service.bulk_delete(AdminFilters())

    assert result.done == 2
    assert repo.items == {}
    assert storage.objects == {}
    (event,) = publisher.events
    assert event.payload.property_id == public.id


async def test_bulk_action_on_too_many_properties_raises() -> None:
    service, repo, _, _ = build()
    original = repo.list_admin

    async def huge(filters: AdminFilters, offset: int, limit: int) -> tuple[list[Property], int]:
        items, _ = await original(filters, offset, limit)
        return items, 10_000

    repo.list_admin = huge  # type: ignore[method-assign]

    with pytest.raises(AppError) as exc_info:
        await service.bulk_delete(AdminFilters())

    assert exc_info.value.code == "too_many_properties"


# 3D model -------------------------------------------------------------------------------


async def test_set_three_d_model_stores_glb_and_returns_its_url() -> None:
    item = make_property()
    service, _, storage, _ = build([item])

    out = await service.set_three_d_model(item.id, GLB_BYTES)

    [(key, (data, content_type))] = storage.objects.items()
    assert key.startswith(f"properties/{item.id}/models/") and key.endswith(".glb")
    assert (data, content_type) == (GLB_BYTES, "model/gltf-binary")
    assert out.three_d_model is not None
    assert out.three_d_model.url == f"https://media.test/{key}"
    assert out.three_d_model.size_bytes == len(GLB_BYTES)


async def test_set_three_d_model_replaces_previous_file() -> None:
    item = make_property()
    service, _, storage, _ = build([item])
    await service.set_three_d_model(item.id, GLB_BYTES)
    [old_key] = storage.objects

    await service.set_three_d_model(item.id, GLB_BYTES)

    assert old_key not in storage.objects
    assert list(storage.objects) == [item.three_d_model_key]


async def test_set_three_d_model_with_other_file_raises_invalid_model() -> None:
    item = make_property()
    service, _, storage, _ = build([item])

    with pytest.raises(AppError) as exc_info:
        await service.set_three_d_model(item.id, JPEG_BYTES)

    assert exc_info.value.code == "invalid_model"
    assert storage.objects == {}


async def test_set_three_d_model_too_large_raises_model_too_large() -> None:
    item = make_property()
    service, _, _, _ = build([item])

    with pytest.raises(AppError) as exc_info:
        await service.set_three_d_model(item.id, b"\x00" * 3000)

    assert exc_info.value.code == "model_too_large"


async def test_set_three_d_model_when_database_fails_removes_stored_file() -> None:
    item = make_property()
    service, repo, storage, _ = build([item])
    repo.fail_on_commit = True

    with pytest.raises(RuntimeError):
        await service.set_three_d_model(item.id, GLB_BYTES)

    assert storage.objects == {}


async def test_delete_three_d_model_removes_file() -> None:
    item = make_property()
    service, _, storage, _ = build([item])
    await service.set_three_d_model(item.id, GLB_BYTES)

    out = await service.delete_three_d_model(item.id)

    assert out.three_d_model is None
    assert storage.objects == {}


async def test_delete_three_d_model_without_model_raises_not_found() -> None:
    item = make_property()
    service, _, _, _ = build([item])

    with pytest.raises(NotFoundError):
        await service.delete_three_d_model(item.id)


async def test_delete_property_removes_its_three_d_model() -> None:
    item = make_property(photos=0, status=PropertyStatus.DRAFT)
    service, _, storage, _ = build([item])
    await service.set_three_d_model(item.id, GLB_BYTES)

    await service.delete(item.id)

    assert storage.objects == {}
