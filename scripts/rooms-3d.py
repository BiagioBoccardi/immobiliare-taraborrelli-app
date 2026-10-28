#!/usr/bin/env python3
"""Rebuilds the room in every listing photo as a 3D model (three.js) and uploads it.

    uv run --no-project --with onnxruntime --with numpy --with pillow scripts/rooms-3d.py [options]

For each photo two models read the picture: one measures the distance of every point in meters
(Depth Anything V2 Small, indoor, Apache-2.0) and one recognises the furniture (YOLOX-M,
Apache-2.0). From them the script works out the size of the room, the colours of walls and
floor, where the furniture stands, the cabinets along the walls and the windows. Then
scripts/room-builder.mjs draws the room with three.js (floor, walls, furniture as objects; the
photo is not used as texture) and the .glb is uploaded as the 3D version of the photo.
Photos that do not show a room (outside views, balconies, details) get no 3D version.

Options:
  --api URL            panel address (default http://localhost:5173, the local trial)
  --email / --password staff account (default: the test administrator of the local trial)
  --code 58 --code 59  only these properties (Reasoft code); default: all
  --replace            rebuild the photos that already have a 3D version
  --remove-property-models  also delete the property-level 3D models (e.g. old galleries)
  --keep DIR           also keep the layouts (.json) and rooms (.glb) in this folder

The two models (about 200 MB) are downloaded once into ~/.cache/taraborrelli. three.js comes
from the repository's npm packages (npm install, done by scripts/dev-local.sh up).
"""

import argparse
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "scripts" / "room-builder.mjs"
ADMIN = "/api/v1/property/admin/properties"
CACHE = Path.home() / ".cache" / "taraborrelli"
DEPTH_FILE = "depth_anything_v2_vits_indoor_dynamic.onnx"
DEPTH_RELEASE = (
    "https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/v2.0.0"
)
OBJECTS_RELEASE = (
    "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0"
)
MODELS = {
    "depth": (DEPTH_FILE, f"{DEPTH_RELEASE}/{DEPTH_FILE}"),
    "objects": ("yolox_m.onnx", f"{OBJECTS_RELEASE}/yolox_m.onnx"),
}

HFOV = np.radians(78)  # listing photos are taken with a wide lens
CAMERA_HEIGHT = (
    1.5  # photos are taken at about this height: it fixes the scale of the room
)
CEILING = 2.75
# COCO classes drawn as furniture (YOLOX numbering).
FURNITURE = {56: "chair", 57: "sofa", 58: "plant", 59: "bed", 60: "table", 61: "toilet",
             62: "tv", 68: "microwave", 69: "oven", 71: "sink", 72: "fridge"}  # fmt: skip
STANDING = {"bed", "sofa", "chair", "table", "fridge", "oven", "toilet", "plant"}
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)

Box = tuple[str, float, np.ndarray]


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
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=180) as answer:
        data = answer.read()
    if raw:
        return data
    return json.loads(data) if data else None


def login(api: str, email: str, password: str) -> str:
    body = json.dumps({"email": email, "password": password}).encode()
    return str(
        http(
            f"{api}/api/v1/auth/login",
            "POST",
            body=body,
            content_type="application/json",
        )["access_token"]
    )


class Session:
    """Staff session that logs in again when the short-lived access token expires."""

    def __init__(self, api: str, email: str, password: str) -> None:
        self.api, self.email, self.password = api, email, password
        self.token = login(api, email, password)

    def call(self, path: str, method: str = "GET", body: bytes | None = None,
             content_type: str | None = None) -> Any:  # fmt: skip
        try:
            return http(f"{self.api}{path}", method, self.token, body, content_type)
        except urllib.error.HTTPError as error:
            if error.code != 401:
                raise
            self.token = login(self.api, self.email, self.password)
            return http(f"{self.api}{path}", method, self.token, body, content_type)


def all_properties(session: Session) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        result = session.call(f"{ADMIN}?size=100&page={page}")
        items += result["items"]
        if not result["items"] or len(items) >= result["total"]:
            return items
        page += 1


def put_glb(session: Session, path: str, data: bytes, name: str) -> None:
    boundary = uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: model/gltf-binary\r\n\r\n"
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    session.call(path, "PUT", body, f"multipart/form-data; boundary={boundary}")


# --- Models -----------------------------------------------------------------------------


def load_model(kind: str) -> ort.InferenceSession:
    name, url = MODELS[kind]
    path = CACHE / name
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Scarico il modello {name} (circa 100 MB, una volta sola)…", flush=True)
        tmp = path.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(path)
    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])


def metric_depth(session: ort.InferenceSession, photo: Image.Image) -> np.ndarray:
    """Distance from the camera of every pixel, in meters."""
    w, h = photo.size
    th = max(14, round(518 * h / w / 14) * 14)
    x = np.asarray(photo.resize((518, th), Image.BICUBIC), np.float32) / 255
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)
    d = (
        session.run(None, {session.get_inputs()[0].name: x})[0]
        .squeeze()
        .astype(np.float32)
    )
    return np.asarray(Image.fromarray(d).resize(photo.size, Image.BILINEAR))


def furniture(
    session: ort.InferenceSession, photo: Image.Image, threshold: float = 0.35
) -> list[Box]:
    """Furniture recognised in the photo: (type, confidence, [x0, y0, x1, y1] in pixels)."""
    w, h = photo.size
    r = min(640 / w, 640 / h)
    canvas = np.full((640, 640, 3), 114, np.uint8)
    canvas[: round(h * r), : round(w * r)] = np.asarray(
        photo.resize((round(w * r), round(h * r)))
    )
    x = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32)
    out = session.run(None, {session.get_inputs()[0].name: x})[0][0]
    grids, strides = [], []
    for stride in (8, 16, 32):
        n = 640 // stride
        yy, xx = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        grids.append(np.stack((xx, yy), 2).reshape(-1, 2))
        strides.append(np.full((n * n, 1), stride))
    grid, step = np.concatenate(grids), np.concatenate(strides)
    out[:, :2] = (out[:, :2] + grid) * step
    out[:, 2:4] = np.exp(out[:, 2:4]) * step
    scores = out[:, 4:5] * out[:, 5:]
    classes, best = scores.argmax(1), scores.max(1)
    keep = (best > threshold) & np.isin(classes, list(FURNITURE))
    cx, cy, bw, bh = out[keep, :4].T
    boxes = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], 1) / r
    classes, best = classes[keep], best[keep]
    chosen: list[int] = []
    for i in best.argsort()[::-1]:
        a = boxes[i]
        duplicate = False
        for j in chosen:
            b = boxes[j]
            inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
                0, min(a[3], b[3]) - max(a[1], b[1])
            )
            union = (
                (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
            )
            iou = inter / max(union, 1e-6)
            duplicate |= iou > 0.8 or (iou > 0.5 and classes[i] == classes[j])
        if not duplicate:
            chosen.append(int(i))
    return [
        (FURNITURE[int(classes[i])], float(best[i]), np.clip(boxes[i], 0, [w, h, w, h]))
        for i in chosen
    ]


# --- Room layout ------------------------------------------------------------------------


def fit_floor(points: np.ndarray) -> tuple[np.ndarray, float, float] | None:
    """Floor plane (normal, offset, share of points on it) among the lower points of the photo."""
    rng = np.random.default_rng(0)
    best: tuple[np.ndarray, float, float] | None = None
    tolerance = 0.04 * float(np.median(points[:, 2]))
    for _ in range(300):
        a, b, c = points[rng.choice(len(points), 3, replace=False)]
        normal = np.cross(b - a, c - a)
        size = float(np.linalg.norm(normal))
        if size < 1e-9:
            continue
        normal /= size
        if normal[1] < 0:
            normal = -normal
        if (
            normal[1] < 0.8 or a @ normal > 0
        ):  # the floor is roughly level, below the camera
            continue
        share = float((np.abs((points - a) @ normal) < tolerance).mean())
        if best is None or share > best[2]:
            best = (normal, float(-(a @ normal)), share)
    return best


def colour(rgb: np.ndarray, mask: np.ndarray, default: list[float]) -> list[float]:
    if mask.sum() < 50:
        return default
    return [round(float(c), 3) for c in np.median(rgb[mask], 0)]


def analyse(photo: Image.Image, depth_model: ort.InferenceSession,
            object_model: ort.InferenceSession) -> dict[str, Any] | None:  # fmt: skip
    """Layout of the room in the photo, or None when the photo does not show a room."""
    photo = photo.copy()
    photo.thumbnail((960, 960))
    w, h = photo.size
    rgb = np.asarray(photo, np.float32) / 255

    z = metric_depth(depth_model, photo)
    # Outside views: greenery, sky at the top of the picture or points far away.
    hsv = np.asarray(photo.convert("HSV"), np.float32) / 255
    green = (
        (hsv[..., 0] > 0.17)
        & (hsv[..., 0] < 0.45)
        & (hsv[..., 1] > 0.25)
        & (hsv[..., 2] > 0.15)
    )
    top = rgb[: h // 3]
    sky = (
        (top[..., 2] > top[..., 0] + 0.04)
        & (top[..., 2] >= top[..., 1])
        & (top.mean(-1) > 0.5)
    )
    if (
        green.mean() > 0.15
        or np.percentile(z, 90) > 12.5
        or (sky.mean() > 0.2 and np.median(z) > 6.5)
    ):
        return None
    tx = np.tan(HFOV / 2)
    ty = tx * h / w
    u, v = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)
    camera = np.stack([(u - 0.5) * 2 * tx * z, -(v - 0.5) * 2 * ty * z, z], -1)

    floor = fit_floor(camera[int(h * 0.66) :, ::4].reshape(-1, 3))
    if floor is None or floor[2] < 0.15:
        return None
    normal, offset, _ = floor
    # The depth model gets the shape right but not always the scale: the camera height does.
    scale = CAMERA_HEIGHT / offset
    camera *= scale
    z = z * scale
    camera_height = CAMERA_HEIGHT

    # Turn the photo so that the floor is level (y up)…
    across = np.array([1.0, 0, 0]) - normal[0] * normal
    across /= np.linalg.norm(across)
    rotation = np.stack([across, normal, np.cross(across, normal)])
    world = camera.reshape(-1, 3) @ rotation.T
    world[:, 1] += camera_height
    world = world.reshape(h, w, 3)
    # …and square with the walls: most common direction of the vertical surfaces.
    sample = world[::4, ::4]
    normals = np.cross(
        sample[1:-1, 2:] - sample[1:-1, :-2], sample[2:, 1:-1] - sample[:-2, 1:-1]
    )
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True) + 1e-9
    angles = np.degrees(np.arctan2(normals[..., 0], normals[..., 2]))[
        np.abs(normals[..., 1]) < 0.25
    ]
    hist, edges = np.histogram((angles + 45) % 90 - 45, bins=90, range=(-45, 45))
    hist = np.convolve(np.r_[hist[-3:], hist, hist[:3]], np.ones(5), "same")[3:-3]
    yaw = np.radians((edges[hist.argmax()] + edges[hist.argmax() + 1]) / 2)
    turn = np.array(
        [[np.cos(yaw), 0, -np.sin(yaw)], [0, 1, 0], [np.sin(yaw), 0, np.cos(yaw)]]
    )
    world = world @ turn.T
    rotation = turn @ rotation

    height = world[..., 1]
    band = (height > 0.3) & (height < 2.3)
    if band.sum() < 500:
        return None
    back = float(np.percentile(world[band][:, 2], 95))
    left = float(np.percentile(world[band][:, 0], 2))
    right = float(np.percentile(world[band][:, 0], 98))
    on_floor = np.abs(height) < 0.06
    front = (
        float(np.percentile(world[on_floor][:, 2], 3)) - 0.3
        if on_floor.sum() > 50
        else 0.0
    )
    front = min(front, back - 1.5)
    if not (1.2 < right - left < 14 and 1.2 < back - front < 14):
        return None
    near_walls = band & (
        (world[..., 2] > back - 0.3)
        | (world[..., 0] < left + 0.3)
        | (world[..., 0] > right - 0.3)
    )

    def to_room(px: float, py: float, distance: float) -> np.ndarray:
        point = rotation @ np.array(
            [
                (px / w - 0.5) * 2 * tx * distance,
                -(py / h - 0.5) * 2 * ty * distance,
                distance,
            ]
        )
        point[1] += camera_height
        return point

    # Furniture: position and size from the box and the distance of its central part.
    items = []
    detections = furniture(object_model, photo)
    taken = np.zeros((h, w), bool)
    for kind, score, (x0, y0, x1, y1) in detections:
        if (
            kind == "fridge" and score < 0.6
        ):  # white doors and wardrobes often look like one
            continue
        taken[int(y0) : int(y1), int(x0) : int(x1)] = True
        cx0, cx1 = int(x0 + (x1 - x0) * 0.25), int(x1 - (x1 - x0) * 0.25)
        cy0, cy1 = int(y0 + (y1 - y0) * 0.25), int(y1 - (y1 - y0) * 0.25)
        centre = (slice(cy0, max(cy0 + 1, cy1)), slice(cx0, max(cx0 + 1, cx1)))
        distance = float(np.percentile(z[centre], 35))
        a, b = to_room(x0, y1, distance), to_room(x1, y1, distance)
        bottom = float(to_room((x0 + x1) / 2, y1, distance)[1])
        if (
            kind in STANDING and bottom > 0.35
        ):  # beds, sofas, tables… stand on the floor
            continue
        items.append({
            "type": kind, "score": round(score, 2),
            "x": float((a[0] + b[0]) / 2), "z": float((a[2] + b[2]) / 2), "width": float(abs(b[0] - a[0])),
            "bottom": max(0.0, bottom),
            "top": float(to_room((x0 + x1) / 2, y0, distance)[1]),
            "color": [round(float(c), 3) for c in np.median(rgb[centre].reshape(-1, 3), 0)],
        })  # fmt: skip

    # Cabinets (what stands out from a wall) and windows (bright areas on a wall), wall by wall,
    # in 10 cm strips.
    bright = (rgb.mean(-1) > 0.86) & (rgb.max(-1) - rgb.min(-1) < 0.12)
    walls = {
        "back": (world[..., 0], back - world[..., 2], left, right),
        "left": (world[..., 2], world[..., 0] - left, front, back),
        "right": (world[..., 2], right - world[..., 0], front, back),
    }
    fixtures: list[dict[str, Any]] = []
    for wall, (along, off_wall, lo, hi) in walls.items():
        edges = np.arange(lo, hi + 0.1, 0.1)
        strip = np.digitize(along, edges) - 1
        usable = (
            (height > 0.05)
            & (height < 2.4)
            & (along > lo)
            & (along < hi)
            & (off_wall > -0.5)
            & ~taken
        )
        strips: list[tuple[int, float, float, np.ndarray] | None] = []
        for s in range(len(edges) - 1):
            here = usable & (strip == s)
            out = here & (off_wall > 0.3) & (off_wall < 0.9)
            # A cabinet stands on the floor and hides most of the wall below 90 cm (kitchen
            # units, chests of drawers) or all of it (wardrobes).
            low = height < 0.9
            low_out = (out & low).sum()
            low_flat = (here & low & (off_wall < 0.3)).sum()
            needed = 0.6 if wall == "back" else 0.7
            if (
                low_out > 30
                and low_out > needed * (low_out + low_flat)
                and np.percentile(height[out], 10) < 0.35
                and np.percentile(height[out], 90) > 0.6
            ):
                strips.append((s, float(np.percentile(height[out], 92)), float(np.median(off_wall[out])),
                               np.median(rgb[out], 0)))  # fmt: skip
            else:
                strips.append(None)
        run: list[tuple[int, float, float, np.ndarray]] = []
        for entry in [*strips, None]:
            if entry is not None and (not run or abs(entry[1] - run[-1][1]) < 0.4):
                run.append(entry)
                continue
            if len(run) >= 5:
                top_height = float(np.median([r[1] for r in run]))
                if top_height > 0.45:
                    fixtures.append({
                        "type": "cabinet", "wall": wall,
                        "from": float(edges[run[0][0]]), "to": float(edges[run[-1][0] + 1]),
                        "height": min(top_height, 2.4),
                        "depth": float(min(0.7, max(0.35, np.median([r[2] for r in run]) + 0.15))),
                        "color": [round(float(c), 3) for c in np.median([r[3] for r in run], 0)],
                    })  # fmt: skip
            run = [entry] if entry is not None else []

        light = (
            bright
            & (height > 0.2)
            & (height < 2.6)
            & (off_wall < 0.35)
            & (along > lo)
            & (along < hi)
        )
        lit = [bool((light & (strip == s)).sum() > 60) for s in range(len(edges) - 1)]
        s = 0
        while s < len(lit):
            if not lit[s]:
                s += 1
                continue
            e = s
            while e + 1 < len(lit) and lit[e + 1]:
                e += 1
            if e - s + 1 >= 5:
                area = light & (strip >= s) & (strip <= e)
                bottom, top_edge = np.percentile(height[area], [3, 97])
                if top_edge - bottom > 0.6:
                    fixtures.append({
                        "type": "window", "wall": wall, "from": float(edges[s]), "to": float(edges[e + 1]),
                        "bottom": float(max(0.0, bottom)), "top": float(min(CEILING - 0.1, top_edge)),
                    })  # fmt: skip
            s = e + 1

    return {
        "room": {
            "left": left, "right": right, "front": front, "back": back, "height": CEILING,
            "wall": colour(rgb, near_walls, [0.93, 0.92, 0.9]),
            "floor": colour(rgb, on_floor, [0.8, 0.75, 0.68]),
        },
        "items": items,
        "fixtures": fixtures,
    }  # fmt: skip


def build(layouts: list[Path]) -> None:
    """Draws the rooms with three.js (scripts/room-builder.mjs): one .glb next to each layout."""
    subprocess.run(["node", str(BUILDER), *map(str, layouts)], check=True, cwd=ROOT)


# --- Main -------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:5173")
    parser.add_argument("--email", default="admin@taraborrelli.test")
    parser.add_argument("--password", default="Admin-di-prova-1")
    parser.add_argument("--code", action="append", default=[])
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--remove-property-models", action="store_true")
    parser.add_argument("--keep", type=Path)
    args = parser.parse_args()
    api = args.api.rstrip("/")

    if shutil.which("node") is None or not (ROOT / "node_modules" / "three").is_dir():
        print(
            "Serve three.js: esegui prima scripts/dev-local.sh up (oppure npm install) nel progetto."
        )
        return 1
    try:
        session = Session(api, args.email, args.password)
        properties = all_properties(session)
    except urllib.error.URLError as error:
        print(
            f"Impossibile contattare il pannello su {api}: {error}. L'ambiente è avviato?"
        )
        return 1
    if args.code:
        properties = [p for p in properties if p["external_ref"] in set(args.code)]
    properties.sort(
        key=lambda p: (len(p["external_ref"] or ""), p["external_ref"] or "")
    )
    depth_model, object_model = load_model("depth"), load_model("objects")

    done = skipped = no_room = failed = removed = 0
    started = time.time()
    for item in properties:
        code = item["external_ref"] or item["reference"]
        if args.remove_property_models and item.get("three_d_model"):
            try:
                session.call(f"{ADMIN}/{item['id']}/model-3d", "DELETE")
                removed += 1
            except urllib.error.URLError as error:
                failed += 1
                print(f"{code} modello dell'immobile: errore {error}")
        with tempfile.TemporaryDirectory() as tmp:
            todo: list[tuple[int, dict[str, Any], Path]] = []
            for number, photo in enumerate(item["photos"], start=1):
                if photo.get("three_d_url") and not args.replace:
                    skipped += 1
                    continue
                try:
                    # The photo is read from this computer, even when the app uses a tunnel.
                    url = photo["url"]
                    if "localhost" in api and "/property-media/" in url:
                        url = f"http://localhost:9100/property-media/{url.split('/property-media/', 1)[1]}"
                    image = Image.open(io.BytesIO(http(url, raw=True))).convert("RGB")
                    layout = analyse(image, depth_model, object_model)
                    if layout is None:
                        no_room += 1
                        if photo.get("three_d_url"):
                            session.call(
                                f"{ADMIN}/{item['id']}/photos/{photo['id']}/model-3d",
                                "DELETE",
                            )
                        continue
                    path = Path(tmp) / f"{code}-{number:02d}.json"
                    path.write_text(json.dumps(layout))
                    todo.append((number, photo, path))
                except (urllib.error.URLError, OSError, ValueError) as error:
                    failed += 1
                    print(f"{code} foto {number}: errore {error}")
            if todo:
                try:
                    build([path for _, _, path in todo])
                except (subprocess.CalledProcessError, OSError) as error:
                    failed += len(todo)
                    print(f"{code}: errore nella costruzione delle stanze ({error})")
                    todo = []
            for number, photo, path in todo:
                glb = path.with_suffix(".glb")
                try:
                    put_glb(session, f"{ADMIN}/{item['id']}/photos/{photo['id']}/model-3d", glb.read_bytes(),
                            glb.name)  # fmt: skip
                    done += 1
                except (urllib.error.URLError, OSError) as error:
                    failed += 1
                    print(f"{code} foto {number}: errore {error}")
            if args.keep:
                args.keep.mkdir(parents=True, exist_ok=True)
                for _, _, path in todo:
                    shutil.copy(path, args.keep)
                    shutil.copy(path.with_suffix(".glb"), args.keep)
        print(
            f"{code}: fatto ({len(item['photos'])} foto) · {round(time.time() - started)} s",
            flush=True,
        )

    print(f"\nStanze 3D create: {done} · già presenti: {skipped} · foto senza stanza: {no_room}"
          f" · errori: {failed}", end="")  # fmt: skip
    print(
        f" · modelli dell'immobile rimossi: {removed}"
        if args.remove_property_models
        else ""
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
