"""Source-executed legacy HTTP -> true FslessMetrics.cpp HOST-only integration.

Real TCP localhost, disposable Digest MD5 fixtures, one listener, exact
ArduinoJson 7.4.3 + actual unchanged FslessMetrics.cpp. NO device or Wi-Fi.
The server buffers <=384 metric bytes BEFORE Digest: PREBODY AUTH IS HOLD.
"""
import hashlib
import json
import os
import re
import socket
import subprocess
import unittest
from pathlib import Path

HOST = "127.0.0.1"
HTTP_HOST = "192.168.4.1"  # Virtual Host header; NEVER a connection target.
USERNAME = "shino"
PASSWORD = "disposable-only-never-owner-password"
NONCE = "0123456789abcdef0123456789abcdef"
REALM = "SHINO-FirstBoot"

VALID = {
    "ok": True,
    "gpu_available": True,
    "cpu_usage": 22.5,
    "gpu_usage": 34.5,
    "memory_used_gb": 8.0,
    "memory_total_gb": 16.0,
    "gpu_vram_mb": 2048.0,
    "gpu_temp_c": 56.0,
    "gpu_power": 120.0,
}


def md5(text: str) -> str:
    return hashlib.md5(text.encode("ascii")).hexdigest()


def digest(method: str, path: str, *, invalid=False) -> str:
    ha1 = md5(f"{USERNAME}:{REALM}:{PASSWORD}")
    ha2 = md5(f"{method}:{path}")
    cnonce = "abcDEF0123456789"
    response = md5(f"{ha1}:{NONCE}:00000001:{cnonce}:auth:{ha2}")
    if invalid:
        response = "0" * 32
    parts = (
        f'username="{USERNAME}"',
        f'realm="{REALM}"',
        f'nonce="{NONCE}"',
        f'uri="{path}"',
        'algorithm=MD5',
        'qop=auth',
        'nc=00000001',
        f'cnonce="{cnonce}"',
        f'response="{response}"',
    )
    return "Digest " + ", ".join(parts)


def req(method, path, body=b"", *, auth=None, cookie=None):
    rows = [f"{method} {path} HTTP/1.1", f"Host: {HTTP_HOST}"]
    if auth is not None:
        rows.append("Authorization: " + auth)
    if cookie is not None:
        rows.append("Cookie: " + cookie)
    if method == "POST" and path == "/api/v1/bridge/metrics":
        rows.extend((
            "Content-Type: application/json",
            f"Content-Length: {len(body)}",
        ))
    rows.append("Connection: close")
    return ("\r\n".join(rows)+"\r\n\r\n").encode("ascii")+body


def post_body(data):
    return json.dumps(data, separators=(",", ":"), allow_nan=False).encode("utf-8")


def status(raw):
    split = raw.split(b"\r\n\r\n", 1)
    assert len(split) == 2, f"missing headers in {raw[:90]!r}"
    first = split[0].split(b"\r\n", 1)[0]
    return int(first.split()[1]), split[0].decode("latin1"), split[1]


class M3GRealLegacyParity(unittest.TestCase):
    def test_real_metric_updates_only_after_true_fixture_digest(self):
        binary = Path(os.environ["M3G_REAL_METRICS_BIN"])
        self.assertTrue(binary.is_file())
        server = subprocess.Popen(
            [str(binary), "20"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            bufsize=1,
        )
        try:
            line = server.stdout.readline().strip()
            self.assertTrue(line.startswith("INTEGRATED_FIXTURE_PORT "), line)
            port = int(line.rsplit(" ", 1)[1])
            requests = 0

            def call(method, path, body=b"", **kw):
                nonlocal requests
                requests += 1
                wire = req(method, path, body, **kw)
                with socket.create_connection((HOST, port), timeout=4) as s:
                    s.settimeout(4)
                    s.sendall(wire)
                    pieces = []
                    while True:
                        chunk = s.recv(8192)
                        if not chunk:
                            break
                        pieces.append(chunk)
                code, headers, payload = status(b"".join(pieces))
                self.assertIn("Connection: close", headers)
                self.assertIn("real-unmodified-metrics-host-ram-only", headers)
                self.assertNotIn('"applied":true', payload.decode("utf-8", errors="replace"))
                return code, headers, payload

            path = "/api/v1/bridge/metrics"
            code, head, _ = call("GET", "/")
            self.assertEqual(code, 401)
            self.assertIn("WWW-Authenticate: Digest ", head)

            code, head, html = call("GET", "/", auth=digest("GET", "/"))
            self.assertEqual(code, 200)
            self.assertIn(b"<", html)
            match = re.search(r"Set-Cookie: (SHINO_READ_SESSION=[a-f0-9]{32});", head)
            self.assertIsNotNone(match)
            cookie = match.group(1)

            code, _, data = call("GET", path, cookie=cookie)
            self.assertEqual(code, 200)
            self.assertFalse(json.loads(data)["received"])

            code, _, _ = call("POST", path, post_body(VALID), cookie=cookie)
            self.assertEqual(code, 401)  # read cookie NEVER upgrades write.

            code, _, _ = call("POST", path, post_body(VALID),
                              auth=digest("POST", path, invalid=True))
            self.assertEqual(code, 401)

            code, _, data = call("GET", path, cookie=cookie)
            self.assertEqual(code, 200)
            self.assertFalse(json.loads(data)["received"])

            code, _, data = call("POST", path, post_body(VALID),
                                 auth=digest("POST", path))
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(data), {
                "status": "RAM_SAMPLE_ACCEPTED", "persisted": False
            })

            code, _, data = call("GET", path, cookie=cookie)
            self.assertEqual(code, 200)
            observed = json.loads(data)
            self.assertEqual(observed["cpu_usage"], 22.5)
            self.assertEqual(observed["gpu_usage"], 34.5)
            self.assertEqual(observed["memory_used_gb"], 8.0)
            self.assertEqual(observed["memory_total_gb"], 16.0)
            self.assertEqual(observed["gpu_temp_c"], 56.0)
            self.assertEqual(observed["ttl_seconds"], 6)
            self.assertTrue(observed["received"])
            self.assertFalse(observed["filesystem_or_eeprom_write_performed"])
            first_at = observed["cpu_usage"]

            code, _, _ = call("POST", path, post_body({**VALID, "cpu_usage": 101}),
                              auth=digest("POST", path))
            self.assertEqual(code, 422)

            code, _, data = call("GET", path, cookie=cookie)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(data)["cpu_usage"], first_at)

            code, _, _ = call("POST", path, b'{"ok":true,"gpu_available":flase}',
                              auth=digest("POST", path))
            self.assertEqual(code, 422)

            code, _, data = call("GET", path, cookie=cookie)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(data)["cpu_usage"], first_at)

            without_total = dict(VALID)
            without_total.pop("memory_total_gb")
            without_total["cpu_usage"] = 66.0
            code, _, _ = call("POST", path, post_body(without_total),
                              auth=digest("POST", path))
            self.assertEqual(code, 200)

            code, _, data = call("GET", path, cookie=cookie)
            self.assertEqual(code, 200)
            observed = json.loads(data)
            self.assertEqual(observed["cpu_usage"], 66)
            self.assertEqual(observed["memory_total_gb"], 0)
            self.assertFalse(observed["memory_total_available"])

            code, _, _ = call("GET", "/api/v1/bridge/status", cookie=cookie)
            self.assertEqual(code, 401)  # privileged GET still Digest.

            code, _, script = call("GET", "/ui.js", cookie=cookie)
            self.assertEqual(code, 200)
            self.assertGreater(len(script), 1000)

            code, _, _ = call("POST", "/api/v1/bridge/ota/upload")
            self.assertEqual(code, 403)

            code, _, _ = call("POST", "/api/v1/bridge/factory-return",
                              auth=digest("POST", "/api/v1/bridge/factory-return"))
            self.assertEqual(code, 403)

            code, _, _ = call("GET", path, cookie="SHINO_READ_SESSION=" + "0"*32)
            self.assertEqual(code, 403)

            code, _, _ = call("GET", "/", cookie="SHINO_READ_SESSION=" + "0"*32)
            self.assertEqual(code, 401)

            self.assertEqual(requests, 20)
            out, err = server.communicate(timeout=6)
            self.assertEqual(server.returncode, 0, err)
            self.assertIn("DEVICE_WRITER 0", out)
            self.assertIn("HOST_RAM_METRICS_ONLY", out)
        finally:
            if server.poll() is None:
                server.kill()
                server.communicate(timeout=3)


if __name__ == "__main__":
    unittest.main()
