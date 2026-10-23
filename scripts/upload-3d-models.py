#!/usr/bin/env python3
"""Uploads the 3D models (.glb) of many properties at once, matched by the management code.

    python3 scripts/upload-3d-models.py <folder> [--replace]

The folder contains one file per property named with its Reasoft code (e.g. 58.glb). Uses
the admin API of the local trial with the test administrator; another server and account can
be given with --api, --email and --password. Properties that already have a model are skipped
unless --replace is given. Only Python's standard library is used.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ADMIN = "/api/v1/property/admin/properties"


def request(
    url: str,
    method: str = "GET",
    token: str | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
) -> Any:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Not an HTTP address: {url}")
    req = urllib.request.Request(url, data=body, method=method, headers=headers)  # noqa: S310
    with urllib.request.urlopen(req, timeout=120) as answer:  # noqa: S310
        data = answer.read()
    return json.loads(data) if data else None


def login(api: str, email: str, password: str) -> str:
    body = json.dumps({"email": email, "password": password}).encode()
    tokens = request(f"{api}/api/v1/auth/login", "POST", body=body, content_type="application/json")
    return str(tokens["access_token"])


def all_properties(api: str, token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        result = request(f"{api}{ADMIN}?size=100&page={page}", token=token)
        items += result["items"]
        if not result["items"] or len(items) >= result["total"]:
            return items
        page += 1


def upload(api: str, token: str, property_id: str, path: Path) -> None:
    boundary = uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            "Content-Type: model/gltf-binary\r\n\r\n"
        ).encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request(
        f"{api}{ADMIN}/{property_id}/model-3d",
        "PUT",
        token=token,
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--api", default="http://localhost:5173")
    parser.add_argument("--email", default="admin@taraborrelli.test")
    parser.add_argument("--password", default="Admin-di-prova-1")
    parser.add_argument("--replace", action="store_true", help="replace existing models")
    args = parser.parse_args()

    files = sorted(args.folder.glob("*.glb"), key=lambda p: (len(p.stem), p.stem))
    if not files:
        print(f"Nessun file .glb in {args.folder}")
        return 1
    api = args.api.rstrip("/")
    try:
        token = login(api, args.email, args.password)
        by_code = {p["external_ref"]: p for p in all_properties(api, token) if p["external_ref"]}
    except urllib.error.URLError as error:
        print(f"Impossibile contattare il pannello su {api}: {error}. L'ambiente è avviato?")
        return 1

    uploaded = skipped = missing = failed = 0
    for path in files:
        item = by_code.get(path.stem)
        if item is None:
            print(f"{path.stem}: nessun immobile con questo codice, saltato")
            missing += 1
        elif item.get("three_d_model") and not args.replace:
            print(f"{path.stem}: ha già un modello 3D, saltato (usa --replace per sostituirlo)")
            skipped += 1
        else:
            try:
                upload(api, token, item["id"], path)
                uploaded += 1
                print(f"{path.stem}: caricato ({item['reference']})")
            except urllib.error.HTTPError as error:
                failed += 1
                detail = error.read().decode(errors="replace")[:200]
                print(f"{path.stem}: errore {error.code} {detail}")
    print(f"\nCaricati: {uploaded} · già presenti: {skipped}", end="")
    print(f" · senza immobile: {missing} · errori: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
