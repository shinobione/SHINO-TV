"""Disposable loopback HTTP proofs only. No private inputs or device addresses."""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from urllib.request import HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm, parse_http_list, parse_keqv_list

from owner_install_http import MESSAGES, UploadStopped, prepare_request, upload_once

PATH = "/api/v1/bridge/factory-return"
FIELD = "factory_v9_0_44"
USER = "loopback-test-user"
PASSWORD = "loopback-test-password"
CHALLENGE = {"realm": "SHINO-FirstBoot", "nonce": "local-nonce", "opaque": "local-opaque", "qop": "auth"}


def core_digest_matches(header, method, path, challenge):
    """Model pinned Core 3.1.2's exact POST/qop MD5 formula, not native execution."""
    if not header.startswith("Digest "):
        return False
    p = parse_keqv_list(parse_http_list(header[7:]))
    if any(p.get(k) != challenge[k] for k in ("realm", "nonce", "opaque")):
        return False
    if p.get("username") != USER or p.get("uri") != path or p.get("qop") != "auth":
        return False
    md5 = lambda s: hashlib.md5(s.encode()).hexdigest()
    h1 = md5(USER + ":" + p["realm"] + ":" + PASSWORD)
    h2 = md5(method + ":" + p["uri"])
    return p["response"] == md5(":".join((h1, p["nonce"], p["nc"], p["cnonce"], "auth", h2)))


class LocalServer:
    def __init__(self, mode="staged", status=200, body=None, headers=None):
        self.requests = []
        self.mode, self.status, self.body, self.headers = mode, status, body, headers or {}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):
                self.connection.settimeout(1)
                declared = int(self.headers["Content-Length"])
                raw = self.rfile.read(declared // 2 if owner.mode == "truncated_request" else declared)
                challenge = dict(CHALLENGE)
                if owner.mode == "stale":
                    challenge["nonce"] = "rotated-local-nonce"
                header = self.headers.get("Authorization", "")
                # Four callbacks reuse the same Digest; authenticate() has no
                # nonce mutation. Challenge generation rotates the shared pair.
                callbacks = [core_digest_matches(header, "POST", self.path, challenge) for _ in range(4)]
                owner.requests.append({"path": self.path, "headers": dict(self.headers),
                                       "body": raw, "declared": declared, "callbacks": callbacks})
                if owner.mode in ("disconnect", "truncated_request"):
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                if owner.mode == "timeout":
                    time.sleep(.2)
                status = 401 if owner.mode == "stale" else owner.status
                body = owner.body if owner.body is not None else json.dumps({
                    "status": "staged", "message": MESSAGES["staged"]}).encode()
                self.send_response(status)
                for key, value in owner.headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body) + (20 if owner.mode == "partial_response" else 0)))
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (OSError, BrokenPipeError):
                    pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.base = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)


def authorization(base):
    manager = HTTPPasswordMgrWithDefaultRealm()
    manager.add_password(CHALLENGE["realm"], base + "/", USER, PASSWORD)
    handler = HTTPDigestAuthHandler(manager)
    return lambda req: "Digest " + handler.get_authorization(req, CHALLENGE)


class UploadHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.file = self.root / "OEM-test.bin"
        # Exact 494144-byte payload length; deliberately synthetic, not firmware.
        self.file.write_bytes(b"\xe9\x02" + b"loopback" * 61767 + b"fixture")
        self.file.write_bytes(self.file.read_bytes()[:494144].ljust(494144, b"x"))
        self.sha = hashlib.sha256(self.file.read_bytes()).hexdigest()
        self.receipt = self.root / "one-attempt.json"

    def tearDown(self):
        self.temp.cleanup()

    def call(self, server, timeout=2):
        return upload_once(server.base, PATH, FIELD, self.file, self.sha,
                           authorization=authorization(server.base), receipt_path=self.receipt, timeout=timeout)

    def hold(self, server, timeout=2):
        with self.assertRaises(UploadStopped) as stopped:
            self.call(server, timeout)
        r = stopped.exception.receipt
        self.assertEqual(r, json.loads(self.receipt.read_text()))
        self.assertEqual(r["gate"], "HOLD")
        self.assertEqual(r["upload_attempts"], 1)
        self.assertEqual(len(server.requests), 1)
        self.assertFalse(r["automatic_retry"])
        return r

    def test_exact_digest_multipart_and_one_successful_post(self):
        with LocalServer() as s:
            result = self.call(s)
        self.assertEqual(len(s.requests), 1)
        request = s.requests[0]
        self.assertTrue(all(request["callbacks"]))
        self.assertEqual(request["path"], PATH)
        self.assertEqual(request["headers"]["Host"], s.base[7:])
        self.assertNotIn("Cookie", request["headers"])
        self.assertNotIn("Transfer-Encoding", request["headers"])
        self.assertNotIn("Expect", request["headers"])
        boundary = "SHINO_M8_" + self.sha[:20]
        self.assertEqual(request["headers"]["Content-Type"], "multipart/form-data; boundary=" + boundary)
        expected = (f'--{boundary}\r\nContent-Disposition: form-data; name="{FIELD}"; filename="OEM-test.bin"\r\n'
                    'Content-Type: application/octet-stream\r\n\r\n').encode() + self.file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        self.assertEqual(request["body"], expected)
        self.assertEqual(request["declared"], len(expected))
        self.assertEqual(result["http"], 200)
        self.assertEqual(result["receipt"]["outcome"], "ACKNOWLEDGED")

    def test_401_and_422_capture_code_and_allowlisted_body_without_retry(self):
        for code, state in ((401, "denied"), (422, "rejected")):
            with self.subTest(code=code), LocalServer(status=code, body=json.dumps({"status": state, "message": MESSAGES[state]}).encode()) as s:
                r = self.hold(s)
                self.assertEqual(r["http_status"], code)
                self.assertEqual(json.loads(r["response_snippet"])["message"], MESSAGES[state])
            self.receipt.unlink()

    def test_stale_digest_is_denied_without_challenge_refresh_or_resubmission(self):
        with LocalServer(mode="stale", headers={"WWW-Authenticate": 'Digest nonce="secret", opaque="secret"'}) as s:
            r = self.hold(s)
            self.assertEqual(r["http_status"], 401)
            self.assertFalse(any(s.requests[0]["callbacks"]))
            self.assertEqual(r["response_headers"]["auth_challenge_scheme"], "Digest")
            self.assertNotIn("secret", json.dumps(r))

    def test_redirects_never_follow_or_repost(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code), LocalServer(status=code, headers={"Location": "/other?password=secret"}) as s:
                r = self.hold(s)
                self.assertEqual(r["http_status"], code)
                self.assertTrue(r["response_headers"]["redirect_location_present"])
                self.assertNotIn("secret", json.dumps(r))
            self.receipt.unlink()

    def test_timeout_late_disconnect_and_truncated_request_hold(self):
        for mode in ("timeout", "disconnect", "truncated_request"):
            with self.subTest(mode=mode), LocalServer(mode=mode) as s:
                r = self.hold(s, timeout=.1 if mode == "timeout" else 2)
                self.assertIn(r["outcome"], ("TIMEOUT", "TRANSPORT_ERROR", "RESPONSE_READ_ERROR"))
                if mode == "truncated_request":
                    self.assertLess(len(s.requests[0]["body"]), s.requests[0]["declared"])
            self.receipt.unlink()

    def test_partial_response_cannot_ack_and_keeps_http_code(self):
        for code in (200, 422):
            with self.subTest(code=code), LocalServer(mode="partial_response", status=code) as s:
                r = self.hold(s)
                self.assertEqual(r["http_status"], code)
                self.assertIn(r["outcome"], ("INCOMPLETE_RESPONSE", "RESPONSE_READ_ERROR"))
            self.receipt.unlink()

    def test_missing_malformed_and_oversized_ack_hold(self):
        for body in (b"", b"not json", b'{"status": []}', b"x" * 5000, b'{"status": "denied"}'):
            with self.subTest(size=len(body)), LocalServer(body=body) as s:
                r = self.hold(s)
                self.assertEqual(r["http_status"], 200)
                self.assertLessEqual(r["response_bytes_observed"], 4097)
            self.receipt.unlink()

    def test_credentials_tokens_and_arbitrary_server_text_are_omitted(self):
        body = json.dumps({"status": "rejected", "message": PASSWORD, "Authorization": "secret", "url": "http://secret"}).encode()
        with LocalServer(status=422, body=body, headers={"Set-Cookie": "secret", "X-Custom": PASSWORD}) as s:
            r = self.hold(s)
        text = json.dumps(r)
        for value in (USER, PASSWORD, "local-nonce", "local-opaque", "cnonce", "secret", "Set-Cookie", "Authorization"):
            self.assertNotIn(value, text)
        self.assertEqual(json.loads(r["response_snippet"]), {"status": "rejected"})

    def test_exclusive_receipt_refuses_another_post(self):
        with LocalServer() as s:
            self.call(s)
            with self.assertRaises(FileExistsError):
                self.call(s)
            self.assertEqual(len(s.requests), 1)

    def test_preflight_errors_create_no_receipt_or_post(self):
        with LocalServer() as s:
            for base, path, field, sha, auth in (
                (s.base, PATH, FIELD, "0" * 64, authorization(s.base)),
                (s.base, PATH, "wrong-field", self.sha, authorization(s.base)),
                (s.base + "/?secret", PATH, FIELD, self.sha, authorization(s.base)),
                (s.base, PATH, FIELD, self.sha, None),
            ):
                with self.assertRaises(ValueError):
                    upload_once(base, path, field, self.file, sha, authorization=auth, receipt_path=self.receipt)
            self.assertEqual(s.requests, [])
            self.assertFalse(self.receipt.exists())


if __name__ == "__main__":
    unittest.main()
