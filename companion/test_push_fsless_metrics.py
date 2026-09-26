import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path

from push_fsless_metrics import (
    ENDPOINT, FIELDS, SenderError, encode_sample, make_opener,
    read_credentials, send_one, validate_host,
)


SAMPLE = {
    "ok": True, "cpu_usage": 31.5, "gpu_usage": 76.0,
    "memory_used_gb": 10.1, "gpu_vram_mb": 5000.0,
    "gpu_temp_c": 64.0, "gpu_power": 125.0, "gpu_available": True,
}


class FakeResponse:
    def __init__(self, code=200, body=b'{"status":"RAM_SAMPLE_ACCEPTED","persisted":false}'):
        self.code = code
        self.body = body
        self.headers = Message()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getcode(self):
        return self.code

    def read(self, n):
        return self.body[:n]


class FakeOpener:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or FakeResponse()

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return self.response


class SenderSafetyTests(unittest.TestCase):
    def test_private_ipv4_only(self):
        self.assertEqual(validate_host("192.168.4.1"), "192.168.4.1")
        for bad in ("localhost", "127.0.0.1", "8.8.8.8",
                    "http://192.168.4.1", "192.168.4.1:80",
                    "192.168.4.1/ota", "::1", "192.168.4.1@evil.com"):
            with self.subTest(host=bad), self.assertRaises(SenderError):
                validate_host(bad)

    def test_metrics_payload_is_bounded_and_strict(self):
        data = json.loads(encode_sample(SAMPLE))
        self.assertEqual(set(data), set(FIELDS))
        self.assertTrue(data["gpu_available"])
        self.assertEqual(data["cpu_usage"], 31.5)
        with self.assertRaises(SenderError):
            encode_sample(dict(SAMPLE, ok=False))
        with self.assertRaises(SenderError):
            encode_sample(dict(SAMPLE, gpu_available=1))
        with self.assertRaises((SenderError, ValueError)):
            encode_sample(dict(SAMPLE, gpu_usage=float("nan")))
        with self.assertRaises(SenderError):
            encode_sample(dict(SAMPLE, memory_used_gb="test"))

    def test_private_credentials_from_file_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "credentials.txt"
            path.write_text(
                "Setup/rescue Wi-Fi password: not-the-HTTP-secret\n"
                "Rescue HTTP Digest user: shino\n"
                "Rescue HTTP Digest password: a-long-different-private-digest-key\n",
                encoding="utf-8",
            )
            self.assertEqual(read_credentials(path),
                             ("shino", "a-long-different-private-digest-key"))
            path.write_text("Rescue HTTP Digest user: shino\n", encoding="utf-8")
            with self.assertRaises(SenderError):
                read_credentials(path)

    def test_exact_ram_post_only_no_firmware_or_fs_route(self):
        fake = FakeOpener()
        self.assertTrue(send_one("192.168.4.1", fake, SAMPLE))
        request, timeout = fake.calls[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, "http://192.168.4.1" + ENDPOINT)
        self.assertEqual(json.loads(request.data)["gpu_usage"], 76)
        self.assertNotIn("credential", request.full_url)
        self.assertNotIn("/ota/", request.full_url)
        self.assertNotIn("/factory-return", request.full_url)
        self.assertNotIn("/fs-plan", request.full_url)
        self.assertEqual(timeout, 3.0)
        self.assertFalse(send_one("192.168.4.1",
                                  FakeOpener(FakeResponse(body=b'{"status":"NO"}')), SAMPLE))

    def test_digest_opener_has_proxy_and_redirects_disabled(self):
        opener = make_opener("192.168.4.1", "shino", "long-password")
        names = {type(handler).__name__ for handler in opener.handlers}
        self.assertIn("HTTPDigestAuthHandler", names)
        self.assertIn("NoRedirect", names)
        # The proxy handler is intentionally configured with {}.
        proxy = next(h for h in opener.handlers if type(h).__name__ == "ProxyHandler")
        self.assertEqual(proxy.proxies, {})


if __name__ == "__main__":
    unittest.main()
