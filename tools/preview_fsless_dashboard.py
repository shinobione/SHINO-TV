#!/usr/bin/env python3
"""PC-only browser preview of EXACT PROGMEM HTML/JS bundled in FS-less C++.

Serves only 127.0.0.1 and never contacts a TV, reads firmware credentials,
accepts POST, flashes firmware or generates any LittleFS image.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "companion"))
from metrics_server import MetricsSampler, query_nvidia  # noqa: E402

CXX = ROOT / "firmware" / "src" / "boot" / "FslessWebUI.cpp"
SOURCE = re.compile(r'const char (PAGE|SCRIPT)\[\] PROGMEM = R"SHINO\((.*?)\)SHINO";', re.S)


def assets(path: Path = CXX) -> dict[str, bytes]:
    source = path.read_text(encoding="utf-8")
    pairs = SOURCE.findall(source)
    result = {key: value.encode("utf-8") for key, value in pairs}
    if set(result) != {"PAGE", "SCRIPT"} or len(pairs) != 2:
        raise ValueError("Could not independently extract both exact flash-resident UI strings")
    return result


def make_handler(static: dict[str, bytes], sampler):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            route = self.path.split("?", 1)[0]
            if route == "/":
                code, content_type, body = 200, "text/html; charset=utf-8", static["PAGE"]
            elif route == "/ui.js":
                code, content_type, body = 200, "application/javascript; charset=utf-8", static["SCRIPT"]
            elif route == "/api/v1/bridge/metrics":
                sample = sampler.snapshot()
                good = bool(sample.get("ok") is True)
                result = {
                    "mode": "PC_ONLY_PREVIEW_NOT_DEVICE",
                    "received": good,
                    "stale": not good,
                    "gpu_available": bool(sample.get("gpu_available", False)),
                }
                for key in ("cpu_usage", "gpu_usage", "memory_used_gb", "memory_total_gb",
                            "gpu_vram_mb", "gpu_temp_c", "gpu_power"):
                    result[key] = sample.get(key, 0)
                result["schema_version"] = 2
                code, content_type = 200, "application/json; charset=utf-8"
                body = json.dumps(result, allow_nan=False).encode()
            elif route in ("/api/v1/bridge/status", "/api/v1/bridge/fs-plan",
                           "/api/v1/bridge/factory-return"):
                code, content_type = 200, "application/json; charset=utf-8"
                body = b'{"mode":"PC_ONLY_PREVIEW","device_connected":false,"flash_permission":false}'
            else:
                code, content_type, body = 404, "text/plain; charset=utf-8", b"Not found"
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if route == "/":
                self.send_header("Content-Security-Policy",
                    "default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.send_response(405)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_):
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--open-browser", action="store_true", help="Open localhost UI only after local preview is listening")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose an unprivileged local TCP port")
    import psutil
    view = assets()
    sampler = MetricsSampler(psutil, query_nvidia)
    import threading
    worker = threading.Thread(target=sampler.run, daemon=True)
    worker.start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(view, sampler))
    print(f"PC-only preview: http://127.0.0.1:{args.port}/")
    print("Shows the exact C++ embedded HTML and JS with PC metrics. No TV, flash or FS upload.")
    if args.open_browser:
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{args.port}/")
    try:
        server.serve_forever(0.4)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        sampler.stop_event.set()
        worker.join(timeout=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
