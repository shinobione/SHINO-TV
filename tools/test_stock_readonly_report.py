"""Unit tests use a fake opener only. Never contact any real TV or local LAN."""
import json
import unittest
from datetime import datetime, timezone
from email.message import Message
from urllib.error import HTTPError

from stock_readonly_report import (
    MAX_BODY, NoRedirect, ProbeError, checked_ip, collect, get_one,
    project_json, project_update_page,
)


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200, declared: str | None = None):
        self.body = body
        self.status = status
        self.headers = Message()
        if declared is not None:
            self.headers["Content-Length"] = declared

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getcode(self):
        return self.status

    def read(self, size):
        return self.body[:size]


class FakeOpener:
    def __init__(self, payloads: dict):
        self.payloads = payloads
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url, timeout))
        path = request.full_url.split("192.168.1.70", 1)[-1]
        response = self.payloads[path]
        if isinstance(response, Exception):
            raise response
        return response


class StockProbeSafetyTests(unittest.TestCase):
    def test_reject_everything_except_strict_rfc1918_literal(self):
        self.assertEqual(checked_ip("192.168.1.70"), "192.168.1.70")
        self.assertEqual(checked_ip("10.2.3.4"), "10.2.3.4")
        self.assertEqual(checked_ip("172.20.7.1"), "172.20.7.1")
        for unsafe in (
            "example.com", "127.0.0.1", "169.254.1.1", "1.1.1.1",
            "192.168.1.70:80", "http://192.168.1.70", "192.168.1.70/ota",
            "192.168.1.70@remote.com", "172.32.0.1", "::1",
        ):
            with self.subTest(unsafe=unsafe), self.assertRaises(ProbeError):
                checked_ip(unsafe)

    def test_get_only_exact_allowlist_not_write_paths(self):
        opener = FakeOpener({
            "/v.json": FakeResponse(b'{"m":"SmallTV-Ultra","v":"Ultra-V9.0.44","secret":"hidden"}'),
            "/space.json": FakeResponse(b'{"total":3121152,"free":269836,"wifi_password":"dontprint"}'),
            "/app.json": FakeResponse(b'{"theme":5,"api_token":"dontprint"}'),
            "/update": FakeResponse(b'<form method="POST" action="/doUpload">'
                                    b'<input type="hidden" name="token" value="dontprint">'
                                    b'<input type="file" name="firmware"></form>'),
        })
        stamp = lambda: datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc)
        result = collect("192.168.1.70", opener=opener, include_update_page=True, clock=stamp)
        encoded = json.dumps(result)
        self.assertEqual([method for method, url, timeout in opener.calls], ["GET"] * 4)
        self.assertEqual([url for method, url, timeout in opener.calls],
                         ["http://192.168.1.70" + path
                          for path in ("/v.json", "/space.json", "/app.json", "/update")])
        self.assertNotIn("dontprint", encoded)
        self.assertNotIn("192.168.1.70", encoded)
        self.assertNotIn('"token"', encoded)
        self.assertEqual(result["observations"]["/space.json"]["data"]["stock_OTA_available_bytes"],
                         "NOT_DISCLOSED_BY_THIS_ENDPOINT")
        self.assertFalse(result["permission_to_flash"])

    def test_update_get_is_separate_opt_in(self):
        opener = FakeOpener({
            "/v.json": FakeResponse(b'{"m":"SmallTV-Ultra","v":"Ultra-V9.0.44"}'),
            "/space.json": FakeResponse(b'{"total":100,"free":50}'),
            "/app.json": FakeResponse(b'{"theme":5}'),
        })
        result = collect("192.168.1.70", opener=opener)
        self.assertNotIn("/update", result["routes_requested"])
        self.assertEqual(len(opener.calls), 3)

    def test_never_fetch_arbitrary_routes(self):
        with self.assertRaisesRegex(ProbeError, "allowlist"):
            get_one("192.168.1.70", "/doUpload", FakeOpener({}), 3)
        with self.assertRaisesRegex(ProbeError, "allowlist"):
            get_one("192.168.1.70", "/delete", FakeOpener({}), 3)

    def test_redirects_are_not_followed(self):
        handler = NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {},
                                                   "http://192.168.1.2/anything"))
        error = HTTPError("http://192.168.1.70/v.json", 302, "Moved", {}, None)
        opener = FakeOpener({"/v.json": error})
        self.assertEqual(get_one("192.168.1.70", "/v.json", opener, 2),
                         {"status": "http_error", "http_code": 302})

    def test_oversized_body_and_header_discarded(self):
        for body, declared in (
            (b"{" + b"x" * MAX_BODY, None),
            (b'{"m":"hidden"}', str(MAX_BODY + 1)),
        ):
            opener = FakeOpener({"/v.json": FakeResponse(body, declared=declared)})
            self.assertEqual(get_one("192.168.1.70", "/v.json", opener, 2),
                             {"status": "body_too_large"})

    def test_update_html_never_keeps_values_or_script_urls(self):
        html = (b'<form action="/doUpload?password=hidden" method="POST" '
                b'enctype="multipart/form-data">'
                b'<input type="hidden" name="csrf" value="secret">'
                b'<input type="password" name="wifi" value="secret">'
                b'<input type="file" name="firmware"></form>'
                b'<form action="https://secret.example/upload" method="POST">'
                b'<input type="file" name="other"></form>'
                b'<script src="https://external.example/code.js"></script>')
        report = project_update_page(html)
        self.assertEqual(report["forms"][0]["action_path"], "/doUpload")
        self.assertEqual(report["forms"][0]["file_field_names"], ["firmware"])
        self.assertEqual(report["forms"][1]["action_path"], "(nonlocal or unrecognized)")
        self.assertEqual(report["script_tag_count"], 1)
        encoded = json.dumps(report)
        self.assertNotIn("secret", encoded)
        self.assertNotIn("csrf", encoded)
        self.assertNotIn("external.example", encoded)
        self.assertEqual(report["actual_OTA_capacity_bytes"], "UNKNOWN")

    def test_invalid_json_and_unexpected_values_are_not_leaked(self):
        with self.assertRaises(ProbeError):
            project_json("/v.json", b'{"private":"SECRET",broken')
        report = project_json("/space.json", b'{"total":null,"free":"secret","password":"hidden"}')
        encoded = json.dumps(report)
        self.assertNotIn("hidden", encoded)
        self.assertNotIn("secret", encoded)
        self.assertIsNone(report["total_bytes"])
        self.assertIsNone(report["free_bytes"])

    def test_method_or_body_can_never_be_inferred_as_flash_permission(self):
        opener = FakeOpener({
            "/v.json": FakeResponse(b'{"m":"SmallTV-Ultra","v":"Ultra-V9.0.44"}'),
            "/space.json": FakeResponse(b'{"total":3121152,"free":269836}'),
            "/app.json": FakeResponse(b'{"theme":5}'),
            "/update": FakeResponse(b'<h1>Update</h1><form action="/doUpload">'
                                    b'<input type="file" name="firmware"></form>'),
        })
        result = collect("192.168.1.70", opener=opener, include_update_page=True)
        self.assertFalse(result["permission_to_flash"])
        self.assertEqual(result["observations"]["/update"]["data"]["actual_file_acceptance"],
                         "NOT_TESTED")
        self.assertEqual(result["http_methods_sent"], ["GET"])


if __name__ == "__main__":
    unittest.main()
