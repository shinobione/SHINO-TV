"""SHINO // TV PC metrics bridge for Times-Z's existing DashboardManager.

Default interface: 127.0.0.1 only. Binding a LAN address is an explicit opt-in.
Only GET /metrics and GET /health are implemented. No upload or device writes.
"""
from __future__ import annotations

import argparse
import csv
import io
import ipaddress
import json
import math
import shutil
import subprocess
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


def bounded(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def parse_nvidia_row(text: str) -> dict | None:
    """Parse nvidia-smi's four-column first-GPU result, or return None."""
    rows = list(csv.reader(io.StringIO(text.strip())))
    if not rows or len(rows[0]) != 4:
        return None
    try:
        values = [float(v.strip()) for v in rows[0]]
    except ValueError:
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    return {
        "gpu_usage": bounded(values[0], 0, 100),
        "gpu_vram_mb": max(0.0, values[1]),  # nvidia-smi reports MiB; upstream displays /1024.
        "gpu_power": max(0.0, values[2]),
        "gpu_temp_c": bounded(values[3], -40, 130),
    }


def query_nvidia() -> dict | None:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "--id=0",
             "--query-gpu=utilization.gpu,memory.used,power.draw,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=1.5, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return parse_nvidia_row(result.stdout) if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def collect_metrics(psutil_module, gpu_supplier=query_nvidia) -> dict:
    """Returns the actual six fields expected by upstream DashboardManager."""
    usage = bounded(psutil_module.cpu_percent(interval=None), 0, 100)
    mem = psutil_module.virtual_memory()
    used_gb = bounded((mem.total - mem.available) / (1024 ** 3), 0, 65536)
    total_gb = bounded(mem.total / (1024 ** 3), 0, 65536)
    gpu = gpu_supplier()
    # Keep CPU/RAM available even when NVIDIA telemetry is temporarily absent.
    return {
        "ok": True,
        "gpu_usage": round(gpu["gpu_usage"], 1) if gpu else 0,
        "cpu_usage": round(usage, 1),
        "gpu_vram_mb": round(gpu["gpu_vram_mb"], 1) if gpu else 0,
        "memory_used_gb": round(used_gb, 2),
        "memory_total_gb": round(total_gb, 2),
        "gpu_power": round(gpu["gpu_power"], 1) if gpu else 0,
        "gpu_temp_c": round(gpu["gpu_temp_c"], 1) if gpu else 0,
        "gpu_available": gpu is not None,
    }


class MetricsSampler:
    """Poll sensors in the background so GET stays faster than device timeout."""
    def __init__(self, psutil_module, gpu_supplier=query_nvidia):
        self.psutil = psutil_module
        self.gpu_supplier = gpu_supplier
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.current = {"ok": False}

    def run(self):
        # Prime psutil's non-blocking CPU counter.
        self.psutil.cpu_percent(interval=None)
        while not self.stop_event.is_set():
            try:
                value = collect_metrics(self.psutil, self.gpu_supplier)
            except Exception:
                value = {"ok": False}
            with self.lock:
                self.current = value
            self.stop_event.wait(1)

    def snapshot(self):
        with self.lock:
            return dict(self.current)


# Explicit allowlist: no directory traversal, file upload or device proxy routes.
PREVIEW_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/scene.mjs": ("scene.mjs", "text/javascript; charset=utf-8"),
    "/live.mjs": ("live.mjs", "text/javascript; charset=utf-8"),
}


def make_handler(sampler, preview_root: Path | None = None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ("/health", "/metrics"):
                if path == "/health":
                    status, payload = 200, {"status": "running"}
                else:
                    status, payload = 200, sampler.snapshot()
                body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
                return self._send(status, body, "application/json; charset=utf-8")

            # Only the server explicitly bound to loopback can serve a browser UI.
            # A separate --bind PC_LAN_IP process exposes only metrics and health.
            if preview_root is not None and path in PREVIEW_FILES:
                try:
                    peer_is_local = ipaddress.ip_address(self.client_address[0]).is_loopback
                    listening_local = ipaddress.ip_address(self.server.server_address[0]).is_loopback
                except ValueError:
                    peer_is_local = listening_local = False
                if not (peer_is_local and listening_local):
                    return self._send(403, b"Forbidden", "text/plain; charset=utf-8")
                filename, content_type = PREVIEW_FILES[path]
                try:
                    body = (preview_root / filename).read_bytes()
                except OSError:
                    return self._send(404, b"Missing preview asset", "text/plain; charset=utf-8")
                if len(body) > 256_000:
                    return self._send(500, b"Preview asset exceeds limit", "text/plain; charset=utf-8")
                return self._send(200, body, content_type)

            return self._send(404, b'{"error":"not found"}', "application/json; charset=utf-8")

        def _send(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Read-only SHINO // TV telemetry bridge")
    parser.add_argument("--bind", default="127.0.0.1",
                        help="Default local-only. Set a specific PC LAN IPv4 explicitly for device use.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    try:
        addr = ipaddress.IPv4Address(args.bind)
    except ipaddress.AddressValueError:
        parser.error("--bind requires a literal IPv4 address")
    if not (addr.is_loopback or (addr.is_private and not addr.is_unspecified and not addr.is_link_local)):
        parser.error("--bind must specify localhost or a private PC LAN interface")
    import psutil  # third-party package intentionally loaded only by the running server
    sampler = MetricsSampler(psutil)
    worker = threading.Thread(target=sampler.run, daemon=True)
    worker.start()
    preview_root = Path(__file__).resolve().parent.parent / "simulator" if addr.is_loopback else None
    server = ThreadingHTTPServer((args.bind, args.port), make_handler(sampler, preview_root=preview_root))
    server.daemon_threads = True
    print(f"SHINO // TV read-only bridge: http://{args.bind}:{args.port}/metrics")
    if preview_root is not None:
        print(f"Local PC preview: http://{args.bind}:{args.port}/")
    if args.bind != "127.0.0.1":
        print("LAN bind enabled: restrict inbound TCP port to your SmallTV device in Windows Firewall.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        sampler.stop_event.set()
        worker.join(timeout=2)


if __name__ == "__main__":
    main()
