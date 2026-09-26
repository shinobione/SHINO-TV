import json
import tempfile
from pathlib import Path
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

from metrics_server import collect_metrics, make_handler, parse_nvidia_row


class FakePsutil:
    @staticmethod
    def cpu_percent(interval=None):
        return 32.4

    @staticmethod
    def virtual_memory():
        class Memory:
            total = 16 * 1024 ** 3
            available = 6 * 1024 ** 3
        return Memory()


class FakeSampler:
    def snapshot(self):
        return {"ok": True, "gpu_usage": 50, "cpu_usage": 32.4}


class MetricsTests(unittest.TestCase):
    def test_parses_nvidia_csv(self):
        result = parse_nvidia_row("44, 6034, 81.2, 68\n")
        self.assertEqual(result["gpu_usage"], 44)
        self.assertEqual(result["gpu_vram_mb"], 6034)
        self.assertEqual(result["gpu_temp_c"], 68)
        self.assertIsNone(parse_nvidia_row("N/A, 123, 10, 40"))
        self.assertIsNone(parse_nvidia_row("nan, 123, 10, 40"))

    def test_schema_and_gpu_fallback(self):
        data = collect_metrics(FakePsutil, lambda: None)
        self.assertTrue(data["ok"])
        self.assertFalse(data["gpu_available"])
        self.assertEqual(data["memory_used_gb"], 10.0)
        self.assertEqual(data["gpu_usage"], 0)
        self.assertEqual(
            set(("ok", "gpu_usage", "cpu_usage", "gpu_vram_mb",
                 "memory_used_gb", "gpu_power", "gpu_temp_c")) - set(data), set()
        )

    def test_http_is_read_only_and_json(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(FakeSampler()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/metrics", timeout=2) as response:
                self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
                self.assertEqual(json.load(response)["gpu_usage"], 50)
            with urlopen(base + "/health", timeout=2) as response:
                self.assertEqual(json.load(response)["status"], "running")
            with self.assertRaises(HTTPError) as raised:
                urlopen(base + "/something-else", timeout=2)
            self.assertEqual(raised.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_local_preview_is_allowlisted_and_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "index.html").write_text("<h1>SHINO</h1>", encoding="utf-8")
            (root / "scene.mjs").write_text("export const ok = true;", encoding="utf-8")
            (root / "live.mjs").write_text("export const live = true;", encoding="utf-8")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(FakeSampler(), preview_root=root))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/", timeout=2) as response:
                    self.assertEqual(response.read(), b"<h1>SHINO</h1>")
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                with urlopen(base + "/live.mjs", timeout=2) as response:
                    self.assertIn("javascript", response.headers["Content-Type"])
                for path in ("/not-listed.txt", "/.git/config", "/companion/metrics_server.py"):
                    with self.subTest(path=path), self.assertRaises(HTTPError) as err:
                        urlopen(base + path, timeout=2)
                    self.assertEqual(err.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_no_preview_served_by_metrics_only_handler(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(FakeSampler()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(HTTPError) as err:
                urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=2)
            self.assertEqual(err.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
