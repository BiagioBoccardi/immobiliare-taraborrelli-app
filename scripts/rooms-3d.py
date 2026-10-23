#!/usr/bin/env python3
"""Creates the 3D version of the room in every listing photo and uploads it.

    uv run --with onnxruntime --with numpy --with pillow scripts/rooms-3d.py [options]

For each photo a depth model (Depth Anything V2 Small, Apache-2.0) estimates how far every
point of the room is from the camera; the photo is then laid on that relief and saved as a
binary glTF (.glb), viewed in the app from the photo's point of view with a small rotation.
A single photo shows only what the camera saw: hidden parts of the room are not invented.

Options:
  --api URL            panel address (default http://localhost:5173, the local trial)
  --email / --password staff account (default: the test administrator of the local trial)
  --code 58 --code 59  only these properties (Reasoft code); default: all
  --replace            recreate the photos that already have a 3D version
  --remove-property-models  also delete the property-level 3D models (e.g. old galleries)

The model (about 100 MB) is downloaded once into ~/.cache/taraborrelli.
"""

import argparse
import io
import json
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageFilter

ADMIN = "/api/v1/property/admin/properties"
MODEL_URL = (
    "https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/v2.0.0/"
    "depth_anything_v2_vits.onnx"
)
MODEL_PATH = Path.home() / ".cache" / "taraborrelli" / "depth_anything_v2_vits.onnx"

# Geometry of the relief, in meters. The viewer puts its camera MID meters in front of the
# origin (apps/mobile/src/components/viewerOptions.ts): the first view is the photo itself.
NEAR, FAR, MID = 1.0, 5.0, 3.0
HFOV = np.radians(70)
COLS = 160
MAX_TEXTURE = 1600
JUMP = 1.3  # triangles across a depth jump larger than this ratio are left open


# --- HTTP -------------------------------------------------------------------------------


def http(url: str, method: str = "GET", token: str | None = None, body: bytes | None = None,
         content_type: str | None = None, raw: bool = False) -> Any:  # fmt: skip
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Not an HTTP address: {url}")
    headers = {"Accept": "*/*"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, method=method, headers=headers)  # noqa: S310
    with urllib.request.urlopen(req, timeout=180) as answer:  # noqa: S310
        data = answer.read()
    if raw:
        return data
    return json.loads(data) if data else None


def login(api: str, email: str, password: str) -> str:
    body = json.dumps({"email": email, "password": password}).encode()
    return str(
        http(f"{api}/api/v1/auth/login", "POST", body=body, content_type="application/json")[
            "access_token"
        ]
    )


def all_properties(api: str, token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        result = http(f"{api}{ADMIN}?size=100&page={page}", token=token)
        items += result["items"]
        if not result["items"] or len(items) >= result["total"]:
            return items
        page += 1


def put_glb(url: str, token: str, data: bytes, name: str) -> None:
    boundary = uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: model/gltf-binary\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    http(url, "PUT", token, body, f"multipart/form-data; boundary={boundary}")


# --- Depth ------------------------------------------------------------------------------


def depth_session() -> ort.InferenceSession:
    if not MODEL_PATH.is_file():
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print("Scarico il modello di profondità (circa 100 MB, una volta sola)…", flush=True)
        tmp = MODEL_PATH.with_suffix(".part")
        urllib.request.urlretrieve(MODEL_URL, tmp)
        tmp.rename(MODEL_PATH)
    return ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])


MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def estimate_depth(session: ort.InferenceSession, photo: Image.Image) -> np.ndarray:
    """Relative closeness of every point, from 0 (far) to 1 (near), at 518x518."""
    x = np.asarray(photo.resize((518, 518), Image.BICUBIC), np.float32) / 255
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    d = session.run(None, {session.get_inputs()[0].name: x})[0].squeeze()
    return (d - d.min()) / max(1e-6, float(d.max() - d.min()))


# --- Mesh and GLB -----------------------------------------------------------------------


def room_glb(photo: Image.Image, closeness: np.ndarray) -> bytes:
    width, height = photo.size
    cols, rows = COLS, max(2, round(COLS * height / width))
    grid = Image.fromarray((closeness * 255).astype(np.uint8)).resize((cols, rows), Image.BILINEAR)
    d = np.asarray(grid.filter(ImageFilter.GaussianBlur(1)), np.float32) / 255
    z = 1 / (d * (1 / NEAR - 1 / FAR) + 1 / FAR)
    z *= MID / float(np.median(z))
    tan_x = np.tan(HFOV / 2)
    tan_y = tan_x * height / width
    u, v = np.meshgrid(np.linspace(0, 1, cols), np.linspace(0, 1, rows))
    pos = np.stack([(u - 0.5) * 2 * tan_x * z, -(v - 0.5) * 2 * tan_y * z, MID - z], -1)
    pos = pos.reshape(-1, 3).astype(np.float32)
    uv = np.stack([u, v], -1).reshape(-1, 2).astype(np.float32)
    nrm = np.tile(np.array([0, 0, 1], np.float32), (cols * rows, 1))
    zf = z.reshape(-1)
    r, q = np.meshgrid(np.arange(rows - 1), np.arange(cols - 1), indexing="ij")
    a = (r * cols + q).reshape(-1)
    b, c, e = a + 1, a + cols, a + cols + 1
    tris = np.concatenate([np.stack([a, c, b], -1), np.stack([b, c, e], -1)])
    tz = zf[tris]
    tris = tris[tz.max(1) / tz.min(1) < JUMP].astype(np.uint16)

    scale = min(1.0, MAX_TEXTURE / width)
    texture = photo.resize((round(width * scale), round(height * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    texture.save(buf, "JPEG", quality=85, optimize=True)
    parts: list[bytes] = []
    views: list[dict[str, int]] = []
    offset = 0

    def view(data: bytes, target: int | None = None) -> int:
        nonlocal offset
        pad = (-offset) % 4
        if pad:
            parts.append(b"\0" * pad)
            offset += pad
        entry = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target:
            entry["target"] = target
        parts.append(data)
        offset += len(data)
        views.append(entry)
        return len(views) - 1

    count = cols * rows
    accessors = [
        {"bufferView": view(pos.tobytes(), 34962), "componentType": 5126, "count": count,
         "type": "VEC3", "min": pos.min(0).tolist(), "max": pos.max(0).tolist()},
        {"bufferView": view(nrm.tobytes(), 34962), "componentType": 5126, "count": count,
         "type": "VEC3"},
        {"bufferView": view(uv.tobytes(), 34962), "componentType": 5126, "count": count,
         "type": "VEC2"},
        {"bufferView": view(tris.tobytes(), 34963), "componentType": 5123,
         "count": int(tris.size), "type": "SCALAR"},
    ]  # fmt: skip
    image = view(buf.getvalue())
    offset += (-offset) % 4
    gltf = {
        "asset": {"version": "2.0", "generator": "Immobiliare Taraborrelli - stanza 3D dalla foto"},
        "extensionsUsed": ["KHR_materials_unlit"],
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                                    "indices": 3, "material": 0}]}],
        "materials": [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                                "metallicFactor": 0, "roughnessFactor": 1},
                       "doubleSided": True, "extensions": {"KHR_materials_unlit": {}}}],
        "textures": [{"source": 0, "sampler": 0}],
        "images": [{"bufferView": image, "mimeType": "image/jpeg"}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "buffers": [{"byteLength": offset}],
        "bufferViews": views,
        "accessors": accessors,
    }  # fmt: skip
    binary = b"".join(parts)
    binary += b"\0" * (offset - len(binary))
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((-len(js)) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (
        b"glTF" + struct.pack("<II", 2, total)
        + struct.pack("<I", len(js)) + b"JSON" + js
        + struct.pack("<I", len(binary)) + b"BIN\0" + binary
    )  # fmt: skip


# --- Main -------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:5173")
    parser.add_argument("--email", default="admin@taraborrelli.test")
    parser.add_argument("--password", default="Admin-di-prova-1")
    parser.add_argument("--code", action="append", default=[])
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--remove-property-models", action="store_true")
    args = parser.parse_args()
    api = args.api.rstrip("/")

    try:
        token = login(api, args.email, args.password)
        properties = all_properties(api, token)
    except urllib.error.URLError as error:
        print(f"Impossibile contattare il pannello su {api}: {error}. L'ambiente è avviato?")
        return 1
    if args.code:
        properties = [p for p in properties if p["external_ref"] in set(args.code)]
    properties.sort(key=lambda p: (len(p["external_ref"] or ""), p["external_ref"] or ""))
    session = depth_session()

    done = skipped = failed = removed = 0
    started = time.time()
    for item in properties:
        code = item["external_ref"] or item["reference"]
        if args.remove_property_models and item.get("three_d_model"):
            http(f"{api}{ADMIN}/{item['id']}/model-3d", "DELETE", token)
            removed += 1
        for number, photo in enumerate(item["photos"], start=1):
            if photo.get("three_d_url") and not args.replace:
                skipped += 1
                continue
            try:
                # The photo is read from this computer, even when the app uses a tunnel.
                url = photo["url"]
                if "localhost" in api and "/property-media/" in url:
                    path = url.split("/property-media/", 1)[1]
                    url = f"http://localhost:9100/property-media/{path}"
                image = Image.open(io.BytesIO(http(url, raw=True))).convert("RGB")
                glb = room_glb(image, estimate_depth(session, image))
                put_glb(f"{api}{ADMIN}/{item['id']}/photos/{photo['id']}/model-3d", token, glb,
                        f"{code}-{number:02d}.glb")  # fmt: skip
                done += 1
            except (urllib.error.URLError, OSError, ValueError) as error:
                failed += 1
                print(f"{code} foto {number}: errore {error}")
        print(
            f"{code}: fatto ({len(item['photos'])} foto) · {round(time.time() - started)} s",
            flush=True,
        )

    print(f"\nStanze 3D create: {done} · già presenti: {skipped} · errori: {failed}", end="")
    print(f" · modelli dell'immobile rimossi: {removed}" if args.remove_property_models else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
