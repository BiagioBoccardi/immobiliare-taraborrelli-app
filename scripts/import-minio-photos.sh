#!/usr/bin/env bash
# One-off: copies the photos of the old local trial (MinIO, Docker volume
# "taraborrelli-dev-s3data") into .dev/media, where scripts/dev-s3.py serves them now.
#
#   scripts/import-minio-photos.sh
#
# Run it with the trial stopped (scripts/dev-local.sh down). Files already in .dev/media
# are kept; the MinIO volume is left untouched, so the script can be run again.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VOLUME="taraborrelli-dev-s3data"
CONTAINER="taraborrelli-minio-export"
PORT="${MINIO_EXPORT_PORT:-9300}"
IMAGE="${MINIO_IMAGE:-cgr.dev/chainguard/minio:latest}"
TARGET="$ROOT/.dev/media"

info() { printf '› %s\n' "$*"; }
fail() { printf '✗ %s\n' "$*" >&2; exit 1; }

docker volume inspect "$VOLUME" >/dev/null 2>&1 || fail "Volume $VOLUME non trovato: non ci sono foto da copiare."

info "Avvio temporaneo di MinIO con le foto del vecchio ambiente…"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d --rm --name "$CONTAINER" \
  -e MINIO_ROOT_USER=taraborrelli -e MINIO_ROOT_PASSWORD=taraborrelli-minio \
  -v "$VOLUME:/data" -p "127.0.0.1:$PORT:9000" "$IMAGE" server /data >/dev/null
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true' EXIT

for _ in $(seq 1 60); do
  curl -fsS "http://localhost:$PORT/minio/health/live" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://localhost:$PORT/minio/health/live" >/dev/null 2>&1 || fail "MinIO non è partito."

info "Copia delle foto in .dev/media…"
cd "$ROOT/services/property"
EXPORT_ENDPOINT="http://localhost:$PORT" EXPORT_TARGET="$TARGET" uv run --quiet python - <<'PY'
import asyncio
import json
import os
from pathlib import Path

from aiobotocore.session import get_session

ENDPOINT = os.environ["EXPORT_ENDPOINT"]
TARGET = Path(os.environ["EXPORT_TARGET"])


async def main() -> None:
    session = get_session()
    async with session.create_client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="taraborrelli",
        aws_secret_access_key="taraborrelli-minio",
    ) as client:
        buckets = [b["Name"] for b in (await client.list_buckets()).get("Buckets", [])]
        copied = skipped = 0
        for bucket in buckets:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=bucket):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    path = TARGET / bucket / key
                    if path.is_file():
                        skipped += 1
                        continue
                    answer = await client.get_object(Bucket=bucket, Key=key)
                    async with answer["Body"] as stream:
                        data = await stream.read()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    # Same metadata file that scripts/dev-s3.py writes on upload.
                    content_type = answer.get("ContentType") or "application/octet-stream"
                    path.with_name(path.name + ".meta.json").write_text(
                        json.dumps({"content_type": content_type})
                    )
                    copied += 1
        print(f"Bucket: {', '.join(buckets) or 'nessuno'}")
        print(f"Foto copiate: {copied}, già presenti: {skipped}")


asyncio.run(main())
PY

info "Fatto. Avvia di nuovo l'ambiente: scripts/dev-local.sh up (oppure up --tunnel)."
