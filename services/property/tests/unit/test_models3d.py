import pytest

from app.storage.models3d import is_glb
from tests.factories import GLB_BYTES, JPEG_BYTES, glb_bytes


def test_is_glb_accepts_binary_gltf_2() -> None:
    result = is_glb(GLB_BYTES)

    assert result is True


@pytest.mark.parametrize(
    "data",
    [
        b"",
        JPEG_BYTES,
        b'{"asset": {"version": "2.0"}}',  # text glTF: only the binary format is accepted
        b"glTF" + (1).to_bytes(4, "little") + (64).to_bytes(4, "little") + b"\x00" * 52,
        glb_bytes()[:-10],  # truncated: declared length larger than the file
    ],
)
def test_is_glb_rejects_other_or_damaged_files(data: bytes) -> None:
    result = is_glb(data)

    assert result is False
