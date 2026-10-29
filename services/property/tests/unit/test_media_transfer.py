import hashlib

import pytest
from py_common.errors import ConflictError

from app.schemas.media import TransferSignatureRequest
from app.services.media_transfer import MediaTransferService
from app.storage.cloudinary import CloudinaryCredentials, CloudinaryMediaStorage
from tests.unit.fakes import InMemoryStorage

CREDENTIALS = CloudinaryCredentials(cloud_name="agenzia", api_key="123", api_secret="segreto")


def _cloudinary() -> CloudinaryMediaStorage:
    def no_http(url: str, body: bytes, content_type: str, timeout: float) -> tuple[int, bytes]:
        raise AssertionError("signing must not call Cloudinary")

    return CloudinaryMediaStorage(CREDENTIALS, http_post=no_http, clock=lambda: 1_800_000_000.0)


def test_signatures_for_upload_sign_each_public_id() -> None:
    service = MediaTransferService(_cloudinary())
    request = TransferSignatureRequest(action="upload", public_ids=["trasferimento/TR1/0.jpg"])

    result = service.signatures(request)

    item = result.items[0]
    expected = hashlib.sha1(  # noqa: S324 - Cloudinary's signature
        b"public_id=trasferimento/TR1/0&timestamp=1800000000segreto"
    ).hexdigest()
    assert item.signature == expected
    assert item.url == "https://api.cloudinary.com/v1_1/agenzia/image/upload"
    assert item.delivery_url.endswith("/agenzia/image/upload/trasferimento/TR1/0.jpg")
    assert "segreto" not in item.model_dump_json()


def test_signatures_without_cloudinary_raise_conflict() -> None:
    service = MediaTransferService(InMemoryStorage())
    request = TransferSignatureRequest(action="destroy", public_ids=["trasferimento/TR1/0.jpg"])

    with pytest.raises(ConflictError):
        service.signatures(request)


def test_request_outside_the_transfer_folder_is_invalid() -> None:
    with pytest.raises(ValueError):
        TransferSignatureRequest(action="upload", public_ids=["properties/p1/f1.jpg"])
