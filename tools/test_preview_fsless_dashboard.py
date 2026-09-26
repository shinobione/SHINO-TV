"""Offline/localhost-only tests for the exact FS-less embedded browser preview."""
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from preview_fsless_dashboard import assets, make_handler


class FakeSampler:
    def snapshot(self):
        return {
            "ok": True, "cpu_usage": 41.0, "gpu_usage": 65.0,
            "memory_used_gb": 12.2, "gpu_vram_mb": 4300,
            "gpu_temp_c": 59.0, "gpu_power": 100.0,
            "gpu_available": True,
        }


class FslessPreviewTests(unittest.TestCase):
    def test_cxx_exact_html_and_js_extract_without_filesystem_dependency(self):
        result = assets()
        self.assertEqual(set(result), {"PAGE", "SCRIPT"})
        html = result["PAGE"].decode()
        script = result["SCRIPT"].decode()
        self.assertIn("SHINO // TV", html)
        self.assertIn('/ui.js', html)
        self.assertIn('/api/v1/bridge/metrics', script)
        self.assertNotIn("<form", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("fetch('/update", script)

    def test_local_preview_serves_expected_contract_and_refuses_posts(self):
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(assets(), FakeSampler()))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(server.server_port)
        try:
            with urlopen(base + "/", timeout=2) as reply:
                self.assertIn(b"SHINO // TV", reply.read())
                self.assertIn("script-src 'self'", reply.headers["Content-Security-Policy"])
            with urlopen(base + "/ui.js", timeout=2) as reply:
                self.assertIn(b"function", reply.read())
            with urlopen(base + "/api/v1/bridge/metrics", timeout=2) as reply:
                payload = json.load(reply)
                self.assertEqual(payload["cpu_usage"], 41.0)
                self.assertEqual(payload["mode"], "PC_ONLY_PREVIEW_NOT_DEVICE")
            req = Request(base + "/api/v1/bridge/metrics", method="POST", data=b"{}")
            with self.assertRaises(HTTPError) as raised:
                urlopen(req, timeout=2)
            self.assertEqual(raised.exception.code, 405)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
