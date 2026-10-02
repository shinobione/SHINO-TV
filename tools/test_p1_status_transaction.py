"""Offline scripted sockets only. Never creates a real socket or contacts AP."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from urllib.request import parse_http_list, parse_keqv_list

from p1_status_transaction import DiagnosticStopped, single_status

USER, PASSWORD = "FAKE_USER", "FAKE_PASSWORD_NOT_PRIVATE"
CHALLENGE = 'Digest realm="SHINO-FirstBoot", qop="auth", nonce="fake-nonce", opaque="fake-opaque"'


def status_body():
    return json.dumps({"mode": "FIRST_BOOT_BRIDGE", "running_application_bytes": 464544,
        "physical_flash_bytes_observed_at_runtime": 4194304, "available_heap_bytes": 14000,
        "wifi_state": "NO_SAVED_WIFI", "wifi_saved": False, "wifi_storage_layout_safe": True,
        "p1_observation": {"boot": 42, "reset_reason": 0, "min_heap": 13000,
            "min_block": 11000, "min_cont": 1200, "allocation_failures": 0,
            "canary_failures": 0, "secondary_busy": 0, "receiver_pending": False},
        "heap_observation": {"schema": "OBSERVED_HEAP_V1", "state": "NO_SAMPLES", "sample_count": 0},
        "secret_unknown_field": PASSWORD}).encode()


def wire(code=200, body=None, extra=b"", mime=b"application/json"):
    body = status_body() if body is None else body
    return (b"HTTP/1.1 " + str(code).encode() + b" Fake\r\nContent-Type: " + mime +
            b"\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n" +
            extra + b"\r\n" + body)


class ScriptFile(io.BytesIO):
    def __init__(self, data, fail):
        super().__init__(data)
        self.fail, self.lines = fail, 0
    def readline(self, size=-1):
        self.lines += 1
        if (self.fail == "status" and self.lines == 1) or (self.fail == "headers" and self.lines == 2):
            raise TimeoutError()
        return super().readline(size)
    def read(self, size=-1):
        if self.fail == "body":
            raise TimeoutError()
        return super().read(size)


class FakeSocket:
    def __init__(self, data=None, fail=None):
        self.data = wire() if data is None else data
        self.fail, self.sent, self.closed, self.connects = fail, [], False, 0
        self.file = None
    def settimeout(self, value):
        self.timeout = value
    def connect(self, address):
        assert address == ("192.168.4.1", 80)
        self.connects += 1
        if self.fail == "connect": raise TimeoutError()
        if self.fail == "reset": raise ConnectionResetError(10054, "FAKE_SECRET_ERROR")
        if self.fail == "deadline":
            time.sleep(.05)
            if self.closed: raise OSError(9, "FAKE_SECRET_ERROR")
    def sendall(self, data):
        self.sent.append(data)
        if self.fail == "send": raise TimeoutError()
    def makefile(self, mode):
        assert mode == "rb"
        self.file = ScriptFile(self.data, self.fail)
        return self.file
    def shutdown(self, how): pass
    def close(self): self.closed = True


class TransactionTests(unittest.TestCase):
    def run_case(self, sockets, stop=False, **kwargs):
        made = []
        def factory(*args):
            self.assertLess(len(made), len(sockets), "unexpected retry / third request")
            item = sockets[len(made)]
            made.append(item)
            return item
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            if stop:
                with self.assertRaises(DiagnosticStopped) as result:
                    single_status(USER, PASSWORD, path, socket_factory=factory, **kwargs)
                receipt = result.exception.receipt
            else:
                receipt = single_status(USER, PASSWORD, path, socket_factory=factory, **kwargs)
            self.assertEqual(json.loads(path.read_text()), receipt)
        self.assertTrue(all(s.closed for s in made))
        self.assertTrue(all(s.file is None or s.file.closed for s in made))
        serialized = json.dumps(receipt)
        for secret in (USER, PASSWORD, "fake-nonce", "fake-opaque", "FAKE_SECRET_ERROR", "Authorization"):
            self.assertNotIn(secret, serialized)
        return receipt, made

    def test_timeout_each_phase(self):
        cases = (("connect", "TCP_CONNECT", False, False), ("send", "REQUEST_SEND", True, False),
                 ("status", "HTTP_STATUS_WAIT", True, True),
                 ("headers", "RESPONSE_HEADERS", True, True), ("body", "RESPONSE_BODY", True, True))
        for fail, phase, connected, sent in cases:
            with self.subTest(fail=fail):
                r, made = self.run_case([FakeSocket(fail=fail)], stop=True)
                self.assertEqual(r["error_phase"], phase)
                self.assertEqual(r["error_type"], "TimeoutError")
                self.assertEqual(len(made), 1)
                self.assertEqual(r["requests"][0]["tcp_connected"], connected)
                self.assertEqual(r["requests"][0]["send_completed"], sent)
                self.assertEqual("http_status" in r["requests"][0], fail in ("headers", "body"))

    def test_digest_wire_and_status_projection(self):
        first = FakeSocket(wire(401, b"", b"WWW-Authenticate: " + CHALLENGE.encode() + b"\r\n", b"text/html"))
        r, made = self.run_case([first, FakeSocket()])
        self.assertEqual(len(made), 2)
        self.assertEqual(r["status"]["heap_observation"]["state"], "NO_SAMPLES")
        self.assertNotIn("secret_unknown_field", r["status"])
        initial = b"".join(first.sent).decode()
        self.assertTrue(initial.startswith("GET /api/v1/bridge/status HTTP/1.1\r\n"))
        self.assertIn("Host: 192.168.4.1\r\n", initial)
        self.assertIn("Connection: close\r\n", initial)
        self.assertNotIn("Authorization", initial)
        authenticated = b"".join(made[1].sent).decode()
        auth = next(line for line in authenticated.split("\r\n") if line.startswith("Authorization: Digest "))
        fields = parse_keqv_list(parse_http_list(auth[len("Authorization: Digest "):]))
        md5 = lambda s: hashlib.md5(s.encode()).hexdigest()
        h1 = md5(USER + ":SHINO-FirstBoot:" + PASSWORD)
        h2 = md5("GET:/api/v1/bridge/status")
        expected = md5(":".join((h1, "fake-nonce", fields["nc"], fields["cnonce"], "auth", h2)))
        self.assertEqual(fields["response"], expected)
        self.assertEqual(fields["uri"], "/api/v1/bridge/status")
        self.assertEqual(fields["nc"], "00000001")
        ticks = [event["monotonic_ns"] for event in r["events"]]
        self.assertEqual(ticks, sorted(ticks))
        self.assertTrue(all(req["response_complete"] for req in r["requests"]))

    def test_second_401_never_third_request(self):
        challenge = wire(401, b"", b"WWW-Authenticate: " + CHALLENGE.encode() + b"\r\n", b"text/html")
        r, made = self.run_case([FakeSocket(challenge), FakeSocket(challenge)], stop=True)
        self.assertEqual(len(made), 2)
        self.assertEqual(r["validation_error"], "MISSING_STATUS_ACK")

    def test_invalid_challenge_stops_before_credentials_sent(self):
        for value in ("Basic realm=SHINO", CHALLENGE + ', nonce="duplicate"', CHALLENGE.replace("auth", "auth-int")):
            with self.subTest(value=value):
                r, made = self.run_case([FakeSocket(wire(401, b"", b"WWW-Authenticate: " + value.encode() + b"\r\n"))], stop=True)
                self.assertEqual(len(made), 1)
                self.assertEqual(r["error_phase"], "DIGEST_PREPARATION")

    def test_reset_records_error_code_only(self):
        r, _ = self.run_case([FakeSocket(fail="reset")], stop=True)
        self.assertEqual(r["errno"], 10054)
        self.assertEqual(r["error_phase"], "TCP_CONNECT")

    def test_absolute_deadline_interrupts_connect(self):
        r, _ = self.run_case([FakeSocket(fail="deadline")], stop=True, phase_timeout=.1, total_timeout=.02)
        self.assertTrue(r["absolute_deadline_exceeded"])
        self.assertEqual(r["error_phase"], "TCP_CONNECT")
        self.assertFalse(r["requests"][0]["tcp_connected"])

    def test_http_invalid_or_oversized_stops(self):
        cases = [wire(302), wire(100), wire(extra=b"Transfer-Encoding: chunked\r\n"),
                 wire(extra=b"Content-Length: 1\r\n"), wire(extra=b"X: " + b"x"*4097 + b"\r\n"),
                 wire(body=b"x"*16385), wire().replace(b"\r\n", b"\n"),
                 wire().replace(b"Content-Length: ", b"Content-Length: 9")]
        for data in cases:
            with self.subTest(size=len(data)):
                r, made = self.run_case([FakeSocket(data)], stop=True)
                self.assertEqual(len(made), 1)
                self.assertEqual(r["outcome"], "STOP_NO_RETRY")

    def test_truncated_body_stops(self):
        r, _ = self.run_case([FakeSocket(wire()[:-10])], stop=True)
        self.assertEqual(r["error_phase"], "RESPONSE_BODY")
        self.assertEqual(r["validation_error"], "INCOMPLETE_BODY")

    def test_bad_json_or_types_stop(self):
        for body in (b'{"mode":1,"mode":2}', b'not json', status_body().replace(b'"min_cont": 1200', b'"min_cont": true')):
            with self.subTest(body_size=len(body)):
                r, _ = self.run_case([FakeSocket(wire(body=body))], stop=True)
                self.assertEqual(r["error_phase"], "JSON_VALIDATION")

    def test_existing_receipt_prevents_all_io(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"receipt.json"
            path.write_text("existing evidence")
            with self.assertRaises(FileExistsError):
                single_status(USER, PASSWORD, path, socket_factory=lambda *args: self.fail("socket created"))
            self.assertEqual(path.read_text(), "existing evidence")


if __name__ == "__main__":
    unittest.main()
