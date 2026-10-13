"""Validation of uploaded photos by their content, not by the declared type or file name."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageFormat:
    content_type: str
    extension: str


JPEG = ImageFormat("image/jpeg", "jpg")
PNG = ImageFormat("image/png", "png")
WEBP = ImageFormat("image/webp", "webp")


def detect_image_format(data: bytes) -> ImageFormat | None:
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return WEBP
    return None
