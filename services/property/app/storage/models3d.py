"""Validation of uploaded 3D models by their content, not by the declared type or file name."""

import struct

GLB_CONTENT_TYPE = "model/gltf-binary"
GLB_EXTENSION = "glb"

_GLB_MAGIC = b"glTF"
_GLB_VERSION = 2
_HEADER_SIZE = 12


def is_glb(data: bytes) -> bool:
    """True for a complete binary glTF 2.0 file (.glb).

    The 12-byte header holds the magic "glTF", the version and the total length: a file
    whose declared length differs from its real size is truncated or not a GLB at all.
    """
    if len(data) < _HEADER_SIZE or not data.startswith(_GLB_MAGIC):
        return False
    version, length = struct.unpack_from("<II", data, 4)
    return bool(version == _GLB_VERSION and length == len(data))
