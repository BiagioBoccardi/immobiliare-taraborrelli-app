"""Cloudinary storage for listing media, through its HTTPS upload API.

Chosen for hosting at zero cost without a payment card (October 2026). Uses the standard
library only: uploads are a signed multipart POST, so no SDK is needed.
"""

import asyncio
import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

API_BASE = "https://api.cloudinary.com/v1_1"
DELIVERY_BASE = "https://res.cloudinary.com"
# Photos are served in the best format and quality for each browser, which also keeps
# the bandwidth of the free plan low.
IMAGE_DELIVERY = "f_auto,q_auto"
IMAGE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp", "gif", "avif"})
TIMEOUT_SECONDS = 60.0

# (url, body, content type, timeout) -> (status, response body)
HttpPost = Callable[[str, bytes, str, float], tuple[int, bytes]]
# (method, url, headers) -> (status, response body)
HttpRequest = Callable[[str, str, dict[str, str]], tuple[int, bytes]]


class CloudinaryError(RuntimeError):
    """Cloudinary refused a request; the message never contains the credentials."""


@dataclass(frozen=True)
class CloudinaryCredentials:
    cloud_name: str
    api_key: str
    api_secret: str

    @classmethod
    def from_url(cls, url: str) -> "CloudinaryCredentials":
        """Reads `cloudinary://<api_key>:<api_secret>@<cloud_name>`, as shown in the console."""
        parts = urlsplit(url.strip())
        if (
            parts.scheme != "cloudinary"
            or not parts.username
            or not parts.password
            or not parts.hostname
        ):
            raise ValueError(
                "CLOUDINARY_URL must look like cloudinary://<api_key>:<api_secret>@<cloud_name>"
            )
        # The cloud name keeps its case: urlsplit lowers `hostname`.
        cloud_name = parts.netloc.rsplit("@", 1)[1]
        return cls(cloud_name=cloud_name, api_key=parts.username, api_secret=parts.password)


def _http_post(url: str, body: bytes, content_type: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(  # noqa: S310 - fixed https API address
        url, data=body, method="POST", headers={"Content-Type": content_type}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()


def _http_request(method: str, url: str, headers: dict[str, str]) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method=method, headers=headers)  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), error.read()


def _json_object(raw: bytes) -> dict[str, object]:
    try:
        answer = json.loads(raw or b"{}")
    except ValueError:
        return {}
    return answer if isinstance(answer, dict) else {}


def _multipart(fields: dict[str, str], file_bytes: bytes | None) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    if file_bytes is not None:
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="upload"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n".encode()
        )
        chunks.append(file_bytes)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _split_key(key: str) -> tuple[str, str]:
    """Returns (resource type, public id). Images drop the extension, other files keep it."""
    extension = key.rsplit(".", 1)[-1].lower() if "." in key else ""
    if extension in IMAGE_EXTENSIONS:
        return "image", key.rsplit(".", 1)[0]
    return "raw", key


class CloudinaryMediaStorage:
    """Stores each object under its key as Cloudinary public id; URLs are predictable."""

    def __init__(
        self,
        credentials: CloudinaryCredentials,
        http_post: HttpPost = _http_post,
        clock: Callable[[], float] = time.time,
        http_request: HttpRequest | None = None,
    ) -> None:
        self._credentials = credentials
        self._http_post = http_post
        self._http_request = http_request or _http_request
        self._clock = clock

    def _signed(self, params: dict[str, str]) -> dict[str, str]:
        to_sign = "&".join(f"{name}={params[name]}" for name in sorted(params))
        signature = hashlib.sha1(  # noqa: S324 - the algorithm Cloudinary requires
            (to_sign + self._credentials.api_secret).encode()
        ).hexdigest()
        return {**params, "api_key": self._credentials.api_key, "signature": signature}

    def folder_upload_signature(self, folder: str) -> dict[str, str]:
        """Signs browser uploads into one folder, with ids chosen by Cloudinary.

        Used to move photos in from another installation. Cloudinary accepts the signature
        for an hour; it allows uploads into `folder` only.
        """
        params = self._signed({"folder": folder, "timestamp": str(int(self._clock()))})
        return {**params, "url": f"{API_BASE}/{self._credentials.cloud_name}/image/upload"}

    async def delete_folder(self, folder: str) -> int:
        """Deletes every image under `folder/` (Admin API, up to 1000 per request)."""
        url = (
            f"{API_BASE}/{self._credentials.cloud_name}/resources/image/upload"
            f"?prefix={quote(folder.rstrip('/') + '/', safe='')}"
        )
        token = base64.b64encode(
            f"{self._credentials.api_key}:{self._credentials.api_secret}".encode()
        ).decode()
        deleted = 0
        for _ in range(20):
            status, raw = await asyncio.to_thread(
                self._http_request, "DELETE", url, {"Authorization": f"Basic {token}"}
            )
            answer = _json_object(raw)
            if status >= 400:
                raise CloudinaryError(f"Cloudinary delete failed ({status})")
            done = answer.get("deleted", {})
            deleted += len(done) if isinstance(done, dict) else 0
            if not answer.get("partial"):
                break
        return deleted

    async def _call(
        self, action: str, resource_type: str, fields: dict[str, str], data: bytes | None
    ) -> dict[str, object]:
        url = f"{API_BASE}/{self._credentials.cloud_name}/{resource_type}/{action}"
        body, content_type = _multipart(self._signed(fields), data)
        status, raw = await asyncio.to_thread(
            self._http_post, url, body, content_type, TIMEOUT_SECONDS
        )
        try:
            answer = json.loads(raw or b"{}")
        except ValueError:
            answer = {}
        if status >= 400 or not isinstance(answer, dict) or "error" in answer:
            message = answer.get("error", {}) if isinstance(answer, dict) else {}
            detail = message.get("message") if isinstance(message, dict) else None
            raise CloudinaryError(f"Cloudinary {action} failed ({status}): {detail or 'no detail'}")
        return answer

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        resource_type, public_id = _split_key(key)
        fields = {
            "overwrite": "true",
            "public_id": public_id,
            "timestamp": str(int(self._clock())),
        }
        await self._call("upload", resource_type, fields, data)

    async def delete(self, key: str) -> None:
        resource_type, public_id = _split_key(key)
        fields = {
            "invalidate": "true",
            "public_id": public_id,
            "timestamp": str(int(self._clock())),
        }
        await self._call("destroy", resource_type, fields, None)

    def public_url(self, key: str) -> str:
        resource_type, _ = _split_key(key)
        base = f"{DELIVERY_BASE}/{self._credentials.cloud_name}/{resource_type}/upload"
        path = quote(key, safe="/.-_")
        if resource_type == "image":
            return f"{base}/{IMAGE_DELIVERY}/{path}"
        return f"{base}/{path}"
