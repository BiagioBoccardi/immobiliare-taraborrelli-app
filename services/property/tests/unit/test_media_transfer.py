import hashlib
import json

import pytest
from py_common.errors import ConflictError

from app.services.media_transfer import MediaTransferService
from app.storage.cloudinary import CloudinaryCredentials, CloudinaryError, CloudinaryMediaStorage
from tests.unit.fakes import InMemoryStorage

CREDENTIALS = CloudinaryCredentials(cloud_name="agenzia", api_key="123", api_secret="segreto")


def _no_post(url: str, body: bytes, content_type: str, timeout: float) -> tuple[int, bytes]:
    raise AssertionError("not expected")


class FakeAdminApi:
    def __init__(self, answers: list[tuple[int, dict[str, object]]]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    def __call__(self, method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append((method, url, headers))
        status, body = self.answers.pop(0)
        return status, json.dumps(body).encode()


def _service(admin: FakeAdminApi | None = None) -> MediaTransferService:
    storage = CloudinaryMediaStorage(
        CREDENTIALS,
        http_post=_no_post,
        clock=lambda: 1_800_000_000.0,
        http_request=admin or FakeAdminApi([]),
    )
    return MediaTransferService(storage)


def test_signature_allows_uploads_into_the_transfer_folder_only() -> None:
    service = _service()

    result = service.signature()

    expected = hashlib.sha1(  # noqa: S324 - Cloudinary's signature
        b"folder=trasferimento&timestamp=1800000000segreto"
    ).hexdigest()
    assert (result.folder, result.signature) == ("trasferimento", expected)
    assert result.url == "https://api.cloudinary.com/v1_1/agenzia/image/upload"
    assert "segreto" not in result.model_dump_json()


def test_signature_without_cloudinary_raises_conflict() -> None:
    service = MediaTransferService(InMemoryStorage())

    with pytest.raises(ConflictError):
        service.signature()


async def test_cleanup_deletes_the_folder_until_nothing_is_left() -> None:
    admin = FakeAdminApi(
        [
            (200, {"deleted": {"trasferimento/a": "deleted"}, "partial": True}),
            (200, {"deleted": {"trasferimento/b": "deleted"}, "partial": False}),
        ]
    )
    service = _service(admin)

    result = await service.cleanup()

    method, url, _ = admin.calls[0]
    assert result.deleted == 2
    assert method == "DELETE"
    assert url.endswith("/agenzia/resources/image/upload?prefix=trasferimento%2F")


async def test_cleanup_refused_by_cloudinary_raises() -> None:
    service = _service(FakeAdminApi([(401, {"error": {"message": "no"}})]))

    with pytest.raises(CloudinaryError):
        await service.cleanup()
