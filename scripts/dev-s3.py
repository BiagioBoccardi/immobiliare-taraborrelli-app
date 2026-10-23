"""Minimal S3-compatible server for the local trial: photos are saved in a folder on disk.

Only what the property service and the clients use: list and create buckets, bucket
policy (accepted and ignored: everything is readable), put, get, head and delete objects.
No authentication. Never use it outside the local trial.

    python3 scripts/dev-s3.py <data folder> <port> [bind address]
"""

import json
import mimetypes
import sys
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(sys.argv[1]).resolve()
XMLNS = "http://s3.amazonaws.com/doc/2006-03-01/"


def _dechunk(body: bytes) -> bytes:
    """Decodes an 'aws-chunked' body: '<size hex>[;signature]\\r\\n<data>\\r\\n' ... '0\\r\\n'."""
    data, pos = bytearray(), 0
    while pos < len(body):
        end = body.index(b"\r\n", pos)
        size = int(body[pos:end].split(b";")[0], 16)
        if size == 0:
            break
        data += body[end + 2 : end + 2 + size]
        pos = end + 2 + size + 2
    return bytes(data)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _target(self) -> tuple[str, str, str]:
        parts = urlsplit(self.path)
        bucket, _, key = unquote(parts.path).lstrip("/").partition("/")
        return bucket, key, parts.query

    def _file(self, bucket: str, key: str) -> Path | None:
        path = (ROOT / bucket / key).resolve()
        return path if path.is_relative_to(ROOT / bucket) and bucket else None

    def _reply(
        self, status: int, body: bytes = b"", content_type: str = "application/xml"
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _not_found(self) -> None:
        self._reply(404, b'<?xml version="1.0"?><Error><Code>NoSuchKey</Code></Error>')

    def _read_body(self) -> bytes:
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        encoding = self.headers.get("Content-Encoding", "")
        sha = self.headers.get("x-amz-content-sha256", "")
        if "aws-chunked" in encoding or sha.startswith("STREAMING-"):
            body = _dechunk(body)
        return body

    def do_GET(self) -> None:
        bucket, key, _ = self._target()
        if not bucket:
            names = sorted(p.name for p in ROOT.iterdir() if p.is_dir())
            items = "".join(f"<Bucket><Name>{n}</Name></Bucket>" for n in names)
            xml = f'<ListAllMyBucketsResult xmlns="{XMLNS}"><Buckets>{items}</Buckets></ListAllMyBucketsResult>'
            self._reply(200, xml.encode())
            return
        path = self._file(bucket, key)
        if not key:
            self._reply(200 if (ROOT / bucket).is_dir() else 404)
            return
        if path is None or not path.is_file():
            self._not_found()
            return
        meta = path.with_name(path.name + ".meta.json")
        content_type = (
            json.loads(meta.read_text())["content_type"]
            if meta.is_file()
            else mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        )
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        # The 3D viewer downloads models with fetch(): let the app's pages read them.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Last-Modified", formatdate(path.stat().st_mtime, usegmt=True))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    do_HEAD = do_GET

    def do_PUT(self) -> None:
        bucket, key, query = self._target()
        body = self._read_body()
        if not bucket:
            self._reply(400)
        elif not key:
            if "policy" not in query:
                (ROOT / bucket).mkdir(parents=True, exist_ok=True)
            self._reply(204 if "policy" in query else 200)
        elif (path := self._file(bucket, key)) is None:
            self._reply(400)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            content_type = self.headers.get("Content-Type", "application/octet-stream")
            path.with_name(path.name + ".meta.json").write_text(
                json.dumps({"content_type": content_type})
            )
            self.send_response(200)
            self.send_header("ETag", '"0"')
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_DELETE(self) -> None:
        bucket, key, _ = self._target()
        path = self._file(bucket, key) if key else None
        if path is not None:
            path.unlink(missing_ok=True)
            path.with_name(path.name + ".meta.json").unlink(missing_ok=True)
        self._reply(204)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(
            f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n"
        )


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    port = int(sys.argv[2])
    bind = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1"
    ThreadingHTTPServer((bind, port), Handler).serve_forever()
