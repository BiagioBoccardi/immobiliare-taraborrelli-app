import uuid
from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.models.enums import PropertyStatus
from app.models.property import Property
from tests.factories import JPEG_BYTES, PNG_BYTES, property_payload, rental_payload
from tests.unit.fakes import InMemoryStorage

Store = Callable[..., Awaitable[Property]]
BASE = "/api/v1/property/admin/properties"


async def test_create_property_as_staff_returns_draft(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(BASE, json=property_payload(), headers=staff_headers)

    body = response.json()
    assert response.status_code == 201
    assert body["status"] == "draft"
    assert body["reference"].startswith("TR")
    assert body["address"] == "Via di Prova 1"


async def test_create_student_rental_returns_201(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(BASE, json=rental_payload(), headers=staff_headers)

    assert response.status_code == 201
    assert response.json()["tenant_types"] == ["students"]


async def test_create_sale_with_rental_fields_returns_422(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.post(
        BASE, json=property_payload(accommodation="single_room"), headers=staff_headers
    )

    assert response.status_code == 422


async def test_create_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(BASE, json=property_payload())

    assert response.status_code == 401


async def test_create_with_user_role_returns_403(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    response = await client.post(BASE, json=property_payload(), headers=user_headers)

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", ""),
        ("get", "/{id}"),
        ("patch", "/{id}"),
        ("delete", "/{id}"),
        ("post", "/{id}/status"),
    ],
)
async def test_admin_endpoints_with_user_role_return_403(
    client: AsyncClient, user_headers: dict[str, str], method: str, path: str
) -> None:
    url = BASE + path.format(id=uuid.uuid4())

    response = await client.request(method, url, headers=user_headers, json={})

    assert response.status_code == 403


async def test_list_admin_includes_drafts_and_filters_by_status(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    draft = await store(status=PropertyStatus.DRAFT)
    await store()

    response = await client.get(BASE, params={"status": "draft"}, headers=staff_headers)

    assert [i["id"] for i in response.json()["items"]] == [str(draft.id)]


async def test_get_admin_unknown_returns_404(
    client: AsyncClient, staff_headers: dict[str, str]
) -> None:
    response = await client.get(f"{BASE}/{uuid.uuid4()}", headers=staff_headers)

    assert response.status_code == 404


async def test_update_price_returns_new_price(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store(price=150_000)

    response = await client.patch(
        f"{BASE}/{item.id}", json={"price": 139_000}, headers=staff_headers
    )

    assert response.status_code == 200
    assert response.json()["price"] == 139_000


async def test_update_with_negative_price_returns_422(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store()

    response = await client.patch(f"{BASE}/{item.id}", json={"price": -1}, headers=staff_headers)

    assert response.status_code == 422


async def test_update_making_data_inconsistent_returns_400(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store()

    response = await client.patch(
        f"{BASE}/{item.id}", json={"tenant_types": ["students"]}, headers=staff_headers
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_property"


async def test_full_publication_flow(
    client: AsyncClient, staff_headers: dict[str, str], storage: InMemoryStorage
) -> None:
    created = (await client.post(BASE, json=property_payload(), headers=staff_headers)).json()
    await client.post(
        f"{BASE}/{created['id']}/photos",
        files={"file": ("foto.jpg", JPEG_BYTES, "image/jpeg")},
        data={"caption": "Facciata"},
        headers=staff_headers,
    )

    response = await client.post(
        f"{BASE}/{created['id']}/status", json={"status": "published"}, headers=staff_headers
    )

    public = await client.get(f"/api/v1/property/properties/{created['id']}")
    assert response.status_code == 200
    assert response.json()["published_at"] is not None
    assert public.status_code == 200
    assert public.json()["photos"][0]["caption"] == "Facciata"
    assert len(storage.objects) == 1


async def test_publish_without_photos_returns_409(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store(photos=0, status=PropertyStatus.DRAFT)

    response = await client.post(
        f"{BASE}/{item.id}/status", json={"status": "published"}, headers=staff_headers
    )

    assert response.status_code == 409
    assert response.json()["code"] == "photo_required"


async def test_change_status_with_unknown_status_returns_422(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store()

    response = await client.post(
        f"{BASE}/{item.id}/status", json={"status": "deleted"}, headers=staff_headers
    )

    assert response.status_code == 422


async def test_upload_disguised_file_returns_400(
    client: AsyncClient, store: Store, staff_headers: dict[str, str], storage: InMemoryStorage
) -> None:
    item = await store(photos=0, status=PropertyStatus.DRAFT)

    response = await client.post(
        f"{BASE}/{item.id}/photos",
        files={"file": ("foto.jpg", b"<?php echo 1; ?>", "image/jpeg")},
        headers=staff_headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_photo"
    assert storage.objects == {}


async def test_upload_too_large_returns_400(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store(photos=0, status=PropertyStatus.DRAFT)

    response = await client.post(
        f"{BASE}/{item.id}/photos",
        files={"file": ("foto.jpg", JPEG_BYTES + b"\x00" * 2048, "image/jpeg")},
        headers=staff_headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "photo_too_large"


async def test_upload_without_file_returns_422(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store()

    response = await client.post(f"{BASE}/{item.id}/photos", headers=staff_headers)

    assert response.status_code == 422


async def test_upload_without_token_returns_401(client: AsyncClient, store: Store) -> None:
    item = await store()

    response = await client.post(
        f"{BASE}/{item.id}/photos", files={"file": ("a.png", PNG_BYTES, "image/png")}
    )

    assert response.status_code == 401


async def test_reorder_photos_changes_public_cover(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store(photos=2)
    first, second = (str(p.id) for p in item.photos)

    response = await client.put(
        f"{BASE}/{item.id}/photos/order", json={"photo_ids": [second, first]}, headers=staff_headers
    )

    public = await client.get(f"/api/v1/property/properties/{item.id}")
    assert response.status_code == 200
    assert [p["id"] for p in public.json()["photos"]] == [second, first]


async def test_authorize_photo_for_sold_section(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store(photos=1)

    response = await client.patch(
        f"{BASE}/{item.id}/photos/{item.photos[0].id}",
        json={"show_when_sold": True},
        headers=staff_headers,
    )

    assert response.json()["photos"][0]["show_when_sold"] is True


async def test_delete_photo_returns_remaining_photos(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store(photos=2)

    response = await client.delete(
        f"{BASE}/{item.id}/photos/{item.photos[0].id}", headers=staff_headers
    )

    assert response.status_code == 200
    assert len(response.json()["photos"]) == 1


async def test_delete_draft_returns_204(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store(status=PropertyStatus.DRAFT)

    response = await client.delete(f"{BASE}/{item.id}", headers=staff_headers)

    assert response.status_code == 204


async def test_delete_published_returns_409(
    client: AsyncClient, store: Store, staff_headers: dict[str, str]
) -> None:
    item = await store()

    response = await client.delete(f"{BASE}/{item.id}", headers=staff_headers)

    assert response.status_code == 409
