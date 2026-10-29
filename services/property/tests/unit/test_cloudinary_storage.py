import hashlib
import json

import pytest

from app.core.config import Settings
from app.main import build_storage
from app.storage.cloudinary import (
    CloudinaryCredentials,
    CloudinaryError,
    CloudinaryMediaStorage,
)
from app.storage.s3 import S3MediaStorage

CREDENTIALS = CloudinaryCredentials(cloud_name="Agenzia", api_key="123", api_secret="segreto")
NOW = 1_800_000_000.0


class FakeHttp:
    def __init__(self, status: int = 200, answer: dict[str, object] | None = None) -> None:
        self.status = status
        self.answer = answer if answer is not None else {"public_id": "x"}
        self.calls: list[tuple[str, bytes, str]] = []

    def __call__(
        self, url: str, body: bytes, content_type: str, timeout: float
    ) -> tuple[int, bytes]:
        self.calls.append((url, body, content_type))
        return self.status, json.dumps(self.answer).encode()


def _field(body: bytes, name: str) -> str:
    marker = f'name="{name}"\r\n\r\n'.encode()
    start = body.index(marker) + len(marker)
    return body[start : body.index(b"\r\n", start)].decode()


def test_credentials_from_url_keep_the_cloud_name_case() -> None:
    credentials = CloudinaryCredentials.from_url(" cloudinary://123:segreto@Agenzia \n")

    assert credentials == CREDENTIALS


def test_credentials_from_malformed_url_raise_without_the_secret() -> None:
    with pytest.raises(ValueError) as error:
        CloudinaryCredentials.from_url("https://123:segreto@Agenzia")

    assert "segreto" not in str(error.value)


async def test_put_photo_uploads_a_signed_image_without_extension() -> None:
    http = FakeHttp()
    storage = CloudinaryMediaStorage(CREDENTIALS, http_post=http, clock=lambda: NOW)

    await storage.put("properties/p1/f1.jpg", b"jpeg-bytes", "image/jpeg")

    url, body, _ = http.calls[0]
    expected = hashlib.sha1(  # noqa: S324 - Cloudinary's signature
        f"overwrite=true&public_id=properties/p1/f1&timestamp={int(NOW)}segreto".encode()
    ).hexdigest()
    assert url == "https://api.cloudinary.com/v1_1/Agenzia/image/upload"
    assert _field(body, "public_id") == "properties/p1/f1"
    assert _field(body, "signature") == expected
    assert b"jpeg-bytes" in body


async def test_put_model_uploads_a_raw_file_with_extension() -> None:
    http = FakeHttp()
    storage = CloudinaryMediaStorage(CREDENTIALS, http_post=http, clock=lambda: NOW)

    await storage.put("properties/p1/models/m.glb", b"glb", "model/gltf-binary")

    url, body, _ = http.calls[0]
    assert url == "https://api.cloudinary.com/v1_1/Agenzia/raw/upload"
    assert _field(body, "public_id") == "properties/p1/models/m.glb"


async def test_put_refused_by_cloudinary_raises_without_the_secret() -> None:
    http = FakeHttp(status=401, answer={"error": {"message": "Invalid Signature"}})
    storage = CloudinaryMediaStorage(CREDENTIALS, http_post=http, clock=lambda: NOW)

    with pytest.raises(CloudinaryError) as error:
        await storage.put("properties/p1/f1.jpg", b"x", "image/jpeg")

    assert "Invalid Signature" in str(error.value)
    assert "segreto" not in str(error.value)


async def test_delete_destroys_the_image() -> None:
    http = FakeHttp(answer={"result": "ok"})
    storage = CloudinaryMediaStorage(CREDENTIALS, http_post=http, clock=lambda: NOW)

    await storage.delete("properties/p1/f1.webp")

    url, body, _ = http.calls[0]
    assert url == "https://api.cloudinary.com/v1_1/Agenzia/image/destroy"
    assert _field(body, "public_id") == "properties/p1/f1"


def test_public_url_of_photo_asks_for_automatic_format_and_quality() -> None:
    storage = CloudinaryMediaStorage(CREDENTIALS, http_post=FakeHttp())

    url = storage.public_url("properties/p1/f1.jpg")

    assert (
        url == "https://res.cloudinary.com/Agenzia/image/upload/f_auto,q_auto/properties/p1/f1.jpg"
    )


def test_build_storage_with_cloudinary_url_uses_cloudinary() -> None:
    settings = Settings(cloudinary_url="cloudinary://123:segreto@Agenzia")

    storage = build_storage(settings)

    assert isinstance(storage, CloudinaryMediaStorage)


def test_build_storage_without_cloudinary_url_uses_s3() -> None:
    settings = Settings(cloudinary_url="")

    storage = build_storage(settings)

    assert isinstance(storage, S3MediaStorage)
