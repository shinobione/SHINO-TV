"""Real urllib Digest, inert in-memory transport; never invoke the live CLI."""
import hashlib
import io
import json
from http.client import IncompleteRead
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import BaseHandler, parse_http_list, parse_keqv_list
from urllib.response import addinfourl

import m9_stagea_status_probe as probe

HOST = "10.123.45.67"  # Inert fixture only; all connection/DNS APIs are guarded.
SECRET = "PUBLIC-INERT-PHASE-R-FIXTURE-SECRET"
PRIVATE_TEXT = "host=10.123.45.67 SSID=fixture MAC=aa:bb:cc C:/private/link.json " + SECRET


def fixture(**updates):
    d = {k: True for k in probe.TRUE_FLAGS}
    d.update({k: False for k in probe.FALSE_FLAGS})
    d.update({k: True for k in probe.BOOL_FIELDS})
    d.update(probe.FLOORS)
    d.update(mode="M9_NORMAL_STAGE_A", boot_profile=1, telemetry_storage="RAM_ONLY",
             telemetry_ttl_ms=6000, checked_file_count=24, checked_payload_bytes=181402,
             blocked_write_attempts=0, setup_cont_stack_min=2800,
             fs_config_cont_stack_min=2500, runtime_cont_stack_min=2400,
             lowest_heap=26000, lowest_block=20000, highest_fragmentation_percent=10,
             resource_sample_count=123, rejected_sample_count=0)
    d.update(updates)
    return json.dumps(d, separators=(",", ":")).encode()


class Body(io.BytesIO):
    def __init__(self, raw):
        super().__init__(raw)
        self.read_sizes = []
        self.bytes_read = 0

    def read(self, size=-1):
        self.read_sizes.append(size)
        data = super().read(size)
        self.bytes_read += len(data)
        return data


class Transport(BaseHandler):
    handler_order = 400

    def __init__(self, code=200, raw=None, challenge=None, error=None, headers=None):
        self.code, self.raw = code, fixture() if raw is None else raw
        self.challenge = (challenge if challenge is not None else
                          'Digest realm="SHINO-StageA", nonce="inert-nonce", '
                          'opaque="inert-opaque", algorithm=MD5, qop="auth"')
        self.error, self.headers = error, headers or {}
        self.calls, self.bodies = [], []
        self.accepted = 0

    def http_open(self, request):
        self.calls.append((request.full_url, request.get_method(), request.data, request.timeout))
        assert request.full_url == "http://" + HOST + probe.STATUS_PATH
        assert request.get_method() == "GET" and request.data is None
        assert request.get_header("Accept") == "application/json"
        assert request.get_header("Cache-control") == "no-store"
        assert request.timeout == 3.0
        if self.error:
            raise self.error
        auth = request.get_header("Authorization")
        if not auth:
            return self.response(401, b'{"error":"UNAUTHORIZED"}',
                                 {"WWW-Authenticate": self.challenge})
        assert auth.startswith("Digest ")
        fields = parse_keqv_list(parse_http_list(auth[7:]))
        h = lambda value: hashlib.md5(value.encode()).hexdigest()
        expected = h(":".join((
            h("shino:SHINO-StageA:" + SECRET), "inert-nonce", fields["nc"],
            fields["cnonce"], "auth", h("GET:" + probe.STATUS_PATH))))
        assert fields["response"] == expected
        assert fields["realm"] == "SHINO-StageA" and fields["uri"] == probe.STATUS_PATH
        self.accepted += 1
        return self.response(self.code, self.raw, self.headers)

    def response(self, code, raw, extra):
        headers = Message()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(raw))
        for k, v in extra.items():
            if v is None:
                del headers[k]
            else:
                headers.replace_header(k, v) if k in headers else headers.add_header(k, v)
        body = Body(raw)
        self.bodies.append(body)
        result = addinfourl(body, headers, "http://" + HOST + probe.STATUS_PATH, code)
        result.msg = "inert-response"
        return result


class OfflineTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.create_connection", "socket.getaddrinfo",
                       "http.client.HTTPConnection.connect"):
            guard = self.enterContext(patch(target, side_effect=AssertionError("network forbidden")))
            self.addCleanup(guard.assert_not_called)

    def run_fixture(self, transport):
        opener = probe.make_opener(HOST, "shino", SECRET)
        digest = next(h for h in opener.handlers if isinstance(h, probe.OneGetDigest))
        digest.get_cnonce = lambda _: "public-inert-cnonce"
        opener.add_handler(transport)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = probe.report_once(lambda: probe.probe(HOST, opener))
        text = out.getvalue()
        self.assertEqual(err.getvalue(), "")
        for secret in (SECRET, HOST, "SSID", "MAC", "C:/private", "Authorization",
                       "WWW-Authenticate", "inert-nonce", "inert-opaque", "cnonce"):
            self.assertNotIn(secret, text)
        self.assertLessEqual(len(transport.calls), 2)
        self.assertTrue(all(body.closed for body in transport.bodies))
        return result, text

    def test_initial_digest_challenge_then_status(self):
        transport = Transport()
        code, output = self.run_fixture(transport)
        self.assertEqual(code, 0)
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(transport.accepted, 1)
        self.assertIn("STAGEA_STATUS_GET=HTTP_200", output)
        self.assertIn("checked_file_count=24 checked_payload_bytes=181402", output)
        self.assertIn("RESOURCE_FLOORS=PASS", output)
        self.assertIn("NORMAL_PROFILE_RUNTIME_GATE=HOLD/PARTIAL", output)

    def test_404_prebody_fallback_unattributed(self):
        for body, expected in (
            (b'{"error":"STAGE_A_PREBODY"}', "STAGE_A_PREBODY"),
            (b'{"error":"STAGE_A_ROUTE_CLOSED"}', "STAGE_A_ROUTE_CLOSED"),
            (PRIVATE_TEXT.encode(), "404_UNATTRIBUTED"),
            (b'{"error":"STAGE_A_PREBODY","secret":"STAGE_A_ROUTE_CLOSED"}', "404_UNATTRIBUTED"),
            (b'{"error":["STAGE_A_PREBODY"]}', "404_UNATTRIBUTED"),
            (b'{"error":"STAGE_A_PREBODY","error":"STAGE_A_ROUTE_CLOSED"}', "404_UNATTRIBUTED"),
        ):
            with self.subTest(body=body):
                transport = Transport(404, body)
                code, output = self.run_fixture(transport)
                self.assertEqual(code, 1)
                self.assertEqual(len(transport.calls), 2)
                self.assertEqual(output, "STAGEA_STATUS_GET=HTTP_404 ERROR_CODE=" + expected + "\n")

    def test_plain_unauthorized_and_unexpected_realm(self):
        for challenge, expected in (
            ("", "HTTP_401"),
            ('Basic realm="SHINO-StageA"', "HTTP_401"),
            ('Digest realm="SHINO-FirstBoot", nonce="fixture", qop="auth"', "UNEXPECTED_REALM"),
            ('Digest realm="other", nonce="fixture", qop="auth"', "UNEXPECTED_REALM"),
            ('Digest realm="SHINO-StageA", realm="SHINO-StageA", nonce="fixture", qop="auth"', "HTTP_401"),
            ('Digest realm="SHINO-StageA", nonce="fixture", qop="auth-int"', "HTTP_401"),
            ('Digest realm="SHINO-StageA", qop="auth"', "HTTP_401"),
        ):
            with self.subTest(expected=expected):
                transport = Transport(challenge=challenge)
                code, output = self.run_fixture(transport)
                self.assertEqual(code, 1)
                self.assertEqual(len(transport.calls), 1)
                self.assertEqual(output, "STAGEA_STATUS_GET=" + expected + "\n")

    def test_repeated_401_has_no_third_request(self):
        code, output = self.run_fixture(Transport(401))
        self.assertEqual(code, 1)
        self.assertEqual(output, "STAGEA_STATUS_GET=HTTP_401\n")

    def test_error_status_redirect_and_timeout(self):
        for transport, expected in (
            (Transport(403, PRIVATE_TEXT.encode()), "HTTP_403"),
            (Transport(500, PRIVATE_TEXT.encode()), "HTTP_OTHER"),
            (Transport(302, PRIVATE_TEXT.encode(), headers={"Location": "http://10.23.45.67/private"}), "REDIRECT_BLOCKED"),
            (Transport(error=TimeoutError(PRIVATE_TEXT)), "TIMEOUT"),
            (Transport(error=URLError(TimeoutError(PRIVATE_TEXT))), "TIMEOUT"),
            (Transport(error=URLError(PRIVATE_TEXT)), "NETWORK_ERROR"),
            (Transport(error=IncompleteRead(PRIVATE_TEXT.encode())), "MALFORMED_RESPONSE"),
        ):
            with self.subTest(expected=expected):
                code, output = self.run_fixture(transport)
                self.assertEqual(code, 1)
                self.assertEqual(output, "STAGEA_STATUS_GET=" + expected + "\n")

    def test_strict_body_caps_declared_and_undeclared(self):
        for status, limit, expected in ((200, 4096, "OVERSIZED_RESPONSE"),
                                        (404, 256, "HTTP_404 ERROR_CODE=404_UNATTRIBUTED")):
            for length in (str(limit + 1), None):
                with self.subTest(status=status, length=length):
                    transport = Transport(status, b"x" * (limit + 1), headers={"Content-Length": length})
                    code, output = self.run_fixture(transport)
                    self.assertEqual(code, 1)
                    self.assertEqual(output, "STAGEA_STATUS_GET=" + expected + "\n")
                    final_body = transport.bodies[-1]
                    self.assertLessEqual(final_body.bytes_read, limit)
                    self.assertTrue(all(0 <= n <= limit for n in final_body.read_sizes))

    def test_malformed_headers_and_status(self):
        for transport in (
            Transport(raw=b"not-json " + PRIVATE_TEXT.encode()),
            Transport(raw=b'[]'), Transport(raw=b'\xff'),
            Transport(raw=fixture(mode=PRIVATE_TEXT)),
            Transport(raw=fixture(boot_profile=True)),
            Transport(raw=fixture(filesystem_writes_enabled=True)),
            Transport(raw=fixture(telemetry_ttl_ms=6001)),
            Transport(raw=fixture(heap_floor=1)),
            Transport(raw=fixture(lowest_heap=True)),
            Transport(raw=fixture(lowest_block=30000)),
            Transport(raw=fixture(runtime_cont_stack_min=2401)),
            Transport(raw=fixture(design_floors_observed=False)),
            Transport(headers={"Content-Type": "text/html"}),
            Transport(headers={"Content-Length": "-1"}),
            Transport(headers={"Content-Encoding": "gzip"}),
            Transport(headers={"Transfer-Encoding": "chunked"}),
            Transport(raw=fixture(checked_file_count=23)),
            Transport(raw=fixture(rejected_sample_count=1)),
            Transport(raw=fixture().replace(b'"lowest_heap":26000', b'"lowest_heap":NaN')),
            Transport(raw=fixture()[:-1] + b',"unexpected":Infinity}'),
        ):
            with self.subTest(transport=transport):
                code, output = self.run_fixture(transport)
                self.assertEqual(code, 1)
                self.assertEqual(output, "STAGEA_STATUS_GET=MALFORMED_RESPONSE\n")

    def test_hostile_extra_strings_are_never_output(self):
        code, output = self.run_fixture(Transport(raw=fixture(secret=PRIVATE_TEXT, url=PRIVATE_TEXT)))
        self.assertEqual(code, 0)
        self.assertNotIn("secret=", output)
        self.assertNotIn("url=", output)

    def test_unchallenged_200_does_not_count_as_authenticated(self):
        class Unchallenged(Transport):
            def http_open(self, request):
                self.calls.append((request.full_url, request.get_method(), request.data, request.timeout))
                return self.response(200, fixture(), {})
        transport = Unchallenged()
        code, output = self.run_fixture(transport)
        self.assertEqual(code, 1)
        self.assertEqual(output, "STAGEA_STATUS_GET=HTTP_401\n")
        self.assertEqual(len(transport.calls), 1)

    def test_resource_floor_boundary_and_honest_hold(self):
        for updates, expected in (
            ({"lowest_heap": 20480, "lowest_block": 16384, "highest_fragmentation_percent": 25,
              "setup_cont_stack_min": 2048, "fs_config_cont_stack_min": 2048,
              "runtime_cont_stack_min": 2048}, "PASS"),
            ({"lowest_heap": 20479, "design_floors_observed": False}, "HOLD"),
            ({"lowest_block": 16383, "design_floors_observed": False}, "HOLD"),
            ({"highest_fragmentation_percent": 26, "design_floors_observed": False}, "HOLD"),
            ({"runtime_cont_stack_min": 2044, "design_floors_observed": False}, "HOLD"),
            ({"resource_measurements_valid": False, "rejected_sample_count": 1,
              "design_floors_observed": False}, "HOLD"),
            ({"resource_sample_count": 0, "design_floors_observed": False}, "HOLD"),
        ):
            with self.subTest(expected=expected):
                code, output = self.run_fixture(Transport(raw=fixture(**updates)))
                self.assertEqual(code, 0)
                self.assertIn("RESOURCE_FLOORS=" + expected, output)
                self.assertIn("NORMAL_PROFILE_RUNTIME_GATE=HOLD/PARTIAL", output)

    def test_closed_password_scope_no_proxy_basic_or_redirects(self):
        with patch.dict("os.environ", {"HTTP_PROXY": "http://untrusted-proxy.invalid"}):
            opener = probe.make_opener(HOST, "shino", SECRET)
        digest = next(h for h in opener.handlers if isinstance(h, probe.OneGetDigest))
        url = "http://" + HOST + probe.STATUS_PATH
        self.assertEqual(digest.passwd.find_user_password(probe.REALM, url), ("shino", SECRET))
        for realm in (None, "", "SHINO-FirstBoot", "other"):
            self.assertEqual(digest.passwd.find_user_password(realm, url), (None, None))
        self.assertFalse(any(type(h).__name__ == "HTTPBasicAuthHandler" for h in opener.handlers))
        self.assertTrue(any(isinstance(h, probe.NoRedirect) for h in opener.handlers))
        self.assertTrue(all(not h.proxies for h in opener.handlers if hasattr(h, "proxies")))
        for host in ("localhost", "8.8.8.8", "127.0.0.1", "10.1.2.3:80", "10.1.2.3/path"):
            with self.assertRaises(ValueError):
                probe.make_opener(host, "shino", SECRET)

    def test_default_audit_and_invalid_arguments_access_nothing(self):
        with patch.object(probe, "_private_probe") as private, patch.object(probe, "make_opener") as opener, \
                patch.object(Path, "read_text") as read, patch.object(Path, "is_file") as stat, \
                patch("builtins.open") as opened:
            for args in ([], ["--audit"], ["--host", PRIVATE_TEXT], ["--audit", "--live"]):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    probe.main(args)
                self.assertNotIn(PRIVATE_TEXT, out.getvalue() + err.getvalue())
            for guard in (private, opener, read, stat, opened):
                guard.assert_not_called()

    def test_private_loader_integration_with_generated_fixtures_only(self):
        # Exercise the internal operation, never main(["--live"]) or a live CLI.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "SHINO-TV").mkdir()
            creds = root / "inert-credentials.txt"
            creds.write_text("Rescue HTTP Digest user: shino\nRescue HTTP Digest password: " + SECRET, encoding="utf-8")
            config = root / "SHINO-TV" / "link.json"
            config.write_text(json.dumps(dict(schema=1, host=HOST, credentials_file=str(creds))), encoding="utf-8")
            transport = Transport()
            opener = probe.make_opener(HOST, "shino", SECRET)
            opener.add_handler(transport)
            with patch.dict("os.environ", {"LOCALAPPDATA": str(root)}), patch.object(probe, "make_opener", return_value=opener):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(probe.report_once(probe._private_probe), 0)
                self.assertNotIn(str(root), out.getvalue())
                config.write_text(json.dumps(dict(schema=1, host="public.invalid", credentials_file=str(creds))), encoding="utf-8")
                with redirect_stdout(out):
                    self.assertEqual(probe.report_once(probe._private_probe), 1)
                self.assertIn("STAGEA_STATUS_GET=CONFIG_INVALID", out.getvalue())
            self.assertEqual(len(transport.calls), 2)


if __name__ == "__main__":
    unittest.main()
