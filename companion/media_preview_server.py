"""Opt-in, local-only Windows GSMTC -> 240x240 browser lab (NO SMALLTV).

One transient Python process owns a loopback-only static preview and a
read-only, header-gated music feed. No disk cache, no external LAN binding,
no Wi-Fi/device connection, no firmware/OTA and NO V0.1 metrics-tray changes.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit, parse_qs

from media_sessions import MediaCapture, MediaSnapshot, MAX_PREVIEW_JPEG, capture

BIND_IP = "127.0.0.1"
DEFAULT_PORT = 8765
POLL_SECONDS = 3.0
CAPTURE_TIMEOUT_SECONDS = 7.0
STALE_SECONDS = 13.0
PREVIEW_HEADER = "X-Shino-Preview"
PREVIEW_HEADER_VALUE = "1"
ROOT = Path(__file__).resolve().parents[1] / "simulator"
ASSETS = {
    "/now-playing-live.html": ("now-playing-live.html", "text/html; charset=utf-8"),
    "/now-playing-live.mjs": ("now-playing-live.mjs", "text/javascript; charset=utf-8"),
    "/now_playing.mjs": ("now_playing.mjs", "text/javascript; charset=utf-8"),
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "connect-src 'self'; img-src 'self' blob: data:; object-src 'none'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
NO_MEDIA = MediaSnapshot(state="UNAVAILABLE")


@dataclass(frozen=True)
class StoredMedia:
    media: MediaSnapshot
    image: bytes | None
    revision: str | None
    observed_at: float


class MediaCache:
    """Bounded latest-snapshot handoff between independent media worker and HTTP."""
    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._stored: StoredMedia | None = None

    def set_capture(self, result: MediaCapture) -> None:
        image = result.preview_jpeg
        if (not isinstance(image, bytes) or len(image) > MAX_PREVIEW_JPEG
                or not image.startswith(b"\xff\xd8")):
            image = None
        revision = hashlib.sha256(image).hexdigest() if image else None
        with self._lock:
            self._stored = StoredMedia(result.snapshot, image, revision, self._clock())

    def set_unavailable(self) -> None:
        self.set_capture(MediaCapture(NO_MEDIA, None))

    def get_state(self) -> dict:
        with self._lock:
            stored = self._stored
        if stored is None:
            return {
                "status": "WAITING", "media": NO_MEDIA.public_data(),
                "cover_revision": None,
            }
        age = max(0, self._clock() - stored.observed_at)
        if age > STALE_SECONDS:
            return {
                "status": "STALE", "media": NO_MEDIA.public_data(),
                "cover_revision": None,
            }
        return {
            "status": "READY" if stored.media.state not in ("UNAVAILABLE", "NO_SESSION")
                      else stored.media.state,
            "media": stored.media.public_data(),
            "cover_revision": stored.revision,
        }

    def get_cover(self, revision: str) -> bytes | None:
        with self._lock:
            stored = self._stored
        if stored is None or self._clock()-stored.observed_at > STALE_SECONDS:
            return None
        return stored.image if stored.revision == revision else None


def build_handler(cache: MediaCache, root: Path):
    # Allowlist only three known static files: no directory listing, traversal,
    # source repository browsing or arbitrary paths under the checkout.
    class PreviewHandler(BaseHTTPRequestHandler):
        server_version = "SHINO-Preview"
        sys_version = ""
        protocol_version = "HTTP/1.0"

        def log_message(self, fmt, *args):
            # Don't log track names, query strings, filesystem paths or headers.
            pass

        def _allowed(self) -> bool:
            expected_host = BIND_IP + ":" + str(self.server.server_port)
            if self.headers.get("Host", "") != expected_host:
                return False
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + expected_host:
                return False
            return True

        def _send(self, code, payload=b"", kind="text/plain; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store, private")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def _api_allowed(self) -> bool:
            # Foreign websites cannot attach this custom header in no-cors
            # mode, and our service never provides CORS preflight permission.
            site = self.headers.get("Sec-Fetch-Site")
            return self.headers.get(PREVIEW_HEADER) == PREVIEW_HEADER_VALUE and (
                site is None or site in ("same-origin", "none")
            )

        def do_GET(self):
            if not self._allowed():
                return self._send(403)
            route = urlsplit(self.path)
            if route.path in ASSETS and not route.query:
                filename, content_type = ASSETS[route.path]
                try:
                    resource = (root / filename).read_bytes()
                except OSError:
                    return self._send(404)
                if len(resource) > 131072:
                    return self._send(413)
                return self._send(200, resource, content_type)
            if route.path == "/api/v1/media/state" and not route.query:
                if not self._api_allowed():
                    return self._send(403)
                data = json.dumps(cache.get_state(), ensure_ascii=False,
                                  separators=(",", ":")).encode("utf-8")
                return self._send(200, data, "application/json; charset=utf-8")
            if route.path == "/api/v1/media/cover":
                if not self._api_allowed():
                    return self._send(403)
                params = parse_qs(route.query, keep_blank_values=True)
                if set(params) != {"revision"} or len(params["revision"]) != 1:
                    return self._send(400)
                revision = params["revision"][0]
                if len(revision) != 64 or any(x not in "0123456789abcdef" for x in revision):
                    return self._send(400)
                jpeg = cache.get_cover(revision)
                return self._send(200, jpeg, "image/jpeg") if jpeg else self._send(404)
            return self._send(404)

        def do_OPTIONS(self):
            self._send(405)

        def do_POST(self):
            self._send(405)

        def do_PUT(self):
            self._send(405)

    return PreviewHandler


def create_server(cache: MediaCache, *, root: Path = ROOT, port: int = DEFAULT_PORT):
    if type(port) is not int or not (port == 0 or 1024 <= port <= 65535):
        raise ValueError("Invalid preview port")
    return ThreadingHTTPServer((BIND_IP, port), build_handler(cache, root))


def run_media_worker(cache: MediaCache, stop: threading.Event,
                     collector=capture) -> None:
    """The only GSMTC reader; never shares the PC metric sender's event loop."""
    while not stop.is_set():
        try:
            result = asyncio.run(asyncio.wait_for(
                collector(include_cover=True), timeout=CAPTURE_TIMEOUT_SECONDS))
            cache.set_capture(result)
        except Exception:
            cache.set_unavailable()  # scrub stale track and image, no exception data
        stop.wait(POLL_SECONDS)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="Loopback-only browser preview port, default 8765")
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("Live GSMTC preview requires Windows; tests use fake collectors")
    cache = MediaCache()
    stop = threading.Event()
    try:
        server = create_server(cache, port=args.port)
    except OSError:
        print("Could not bind loopback preview port. Stop the older preview server first.")
        return 2
    reader = threading.Thread(target=run_media_worker, args=(cache, stop),
                              daemon=True, name="shino-pc-media-only")
    reader.start()
    print("SHINO // TV V0.4 — PC-only. No connection to the SmallTV.")
    print("Open http://" + BIND_IP + ":" + str(server.server_port) +
          "/now-playing-live.html")
    print("Stop THIS preview with Ctrl+C; the existing metrics tray is separate.")
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        reader.join(timeout=2.0)
        print("PC media preview stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
