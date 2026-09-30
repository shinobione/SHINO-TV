import json
import tempfile
import unittest
import io
import hashlib
from email.message import Message
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import BaseHandler, parse_http_list, parse_keqv_list, HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm, build_opener, ProxyHandler
from urllib.response import addinfourl

from push_fsless_metrics import (
    ENDPOINT, FIELDS, SenderError, encode_sample, make_opener,
    read_credentials, send_one, send_sample, SendStatus, validate_host, NoRedirect,
)


SAMPLE = {
    "ok": True, "cpu_usage": 31.5, "gpu_usage": 76.0,
    "memory_used_gb": 10.1, "memory_total_gb": 16.0, "gpu_vram_mb": 5000.0,
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
        self.assertEqual(data["memory_total_gb"], 16.0)
        with self.assertRaises(SenderError):
            encode_sample(dict(SAMPLE, memory_total_gb=0))
        with self.assertRaises(SenderError):
            encode_sample(dict(SAMPLE, memory_total_gb=9))
        with self.assertRaises(SenderError):
            encode_sample({k: v for k, v in SAMPLE.items() if k != "memory_total_gb"})
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
        self.assertIn("TelemetryDigestAuthHandler", names)
        self.assertIn("NoRedirect", names)
        # urllib may omit a ProxyHandler({}) from opener.handlers entirely,
        # because an empty handler registers no protocol methods. In both
        # cases no inherited HTTP(S) proxy must be installed.
        proxies = [h for h in opener.handlers if type(h).__name__ == "ProxyHandler"]
        self.assertTrue(all(proxy.proxies == {} for proxy in proxies))

    def test_failure_classes_are_sanitized_and_response_shape_is_strict(self):
        class Broken:
            def __init__(self, error): self.error = error
            def open(self, *args, **kwargs): raise self.error
        secret = 'Authorization nonce password C:/private/credentials.txt'
        cases = [(URLError(TimeoutError(secret)), SendStatus.NO_ROUTE_TIMEOUT),
                 (URLError(OSError(10051, secret)), SendStatus.NO_ROUTE_TIMEOUT),
                 (URLError(OSError(10061, secret)), SendStatus.CONNECTION),
                 (URLError(ConnectionRefusedError(secret)), SendStatus.CONNECTION),
                 (ConnectionResetError(secret), SendStatus.CONNECTION),
                 (HTTPError('http://private', 401, secret, Message(), None), SendStatus.HTTP_401),
                 (HTTPError('http://private', 403, secret, Message(), None), SendStatus.HTTP_403)]
        for error, expected in cases:
            with self.subTest(expected=expected):
                result = send_sample('192.168.4.1', Broken(error), SAMPLE)
                self.assertIs(result, expected)
                self.assertNotIn(secret, result.value)
        for body in (b'[]', b'null', b'bad-json', b'\xff', b'{"status":"NO"}', b'x' * 257):
            self.assertIs(send_sample('192.168.4.1', FakeOpener(FakeResponse(body=body)), SAMPLE), SendStatus.MALFORMED)


class DigestTransport(BaseHandler):
    """Real urllib Digest handlers; deterministic in-memory HTTP transport only."""
    handler_order = 400

    def __init__(self):
        self.unavailable_after_challenge = False
        self.unavailable_before_challenge = False
        self.generation = 1
        self.accepted = 0
        self.anonymous = 0
        self.challenges = 0

    def http_open(self, request):
        if self.unavailable_before_challenge:
            raise URLError(ConnectionRefusedError('fixture private path'))
        headers = Message()
        auth = request.get_header('Authorization')
        valid = False
        if auth:
            if self.unavailable_after_challenge:
                raise URLError(TimeoutError('private-password Authorization nonce private-path'))
            fields = parse_keqv_list(parse_http_list(auth.removeprefix('Digest ')))
            md5 = lambda value: hashlib.md5(value.encode()).hexdigest()
            expected = md5(':'.join((md5('shino:SHINO-FirstBoot:fixture-password'),
                                    f'fixture-{self.generation}', fields['nc'], fields['cnonce'],
                                    'auth', md5('POST:' + request.selector))))
            valid = fields['nonce'] == f'fixture-{self.generation}' and fields['response'] == expected
        else:
            self.anonymous += 1
        if valid:
            code, body = 200, b'{"status":"RAM_SAMPLE_ACCEPTED","persisted":false}'
            self.accepted += 1
        else:
            self.challenges += 1
            code, body = 401, b''
            headers['WWW-Authenticate'] = ('Digest realm="SHINO-FirstBoot", qop="auth", '
                                         f'nonce="fixture-{self.generation}", opaque="fixture"')
        response = addinfourl(io.BytesIO(body), headers, request.full_url, code)
        response.msg = 'OK' if code == 200 else 'Unauthorized'
        return response


class DigestContinuityTests(unittest.TestCase):
    def opener(self, transport, stock=False):
        if stock:
            store = HTTPPasswordMgrWithDefaultRealm()
            store.add_password('SHINO-FirstBoot','http://192.168.4.1'+ENDPOINT,'shino','fixture-password')
            opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPDigestAuthHandler(store))
        else:
            opener = make_opener('192.168.4.1', 'shino', 'fixture-password')
        opener.add_handler(transport)
        return opener

    def test_interrupted_digest_handshakes_poison_retained_real_urllib_state(self):
        transport = DigestTransport()
        opener = self.opener(transport, stock=True)
        self.assertTrue(send_one('192.168.4.1', opener, SAMPLE))
        transport.unavailable_after_challenge = True
        for _ in range(7):
            self.assertFalse(send_one('192.168.4.1', opener, SAMPLE))
        digest = next(h for h in opener.handlers if type(h).__name__ == 'HTTPDigestAuthHandler')
        self.assertGreater(digest.retried, 5)
        transport.unavailable_after_challenge = False
        transport.generation += 1
        for _ in range(3):
            self.assertFalse(send_one('192.168.4.1', opener, SAMPLE))
        self.assertTrue(send_one('192.168.4.1', self.opener(transport), SAMPLE))

    def test_fixed_handler_reuses_challenge_and_resets_after_interrupted_auth(self):
        transport = DigestTransport()
        opener = self.opener(transport)
        for _ in range(5): self.assertTrue(send_one('192.168.4.1', opener, SAMPLE))
        self.assertEqual(transport.anonymous, 1)
        self.assertEqual(transport.challenges, 1)
        transport.unavailable_after_challenge = True
        for _ in range(8): self.assertFalse(send_one('192.168.4.1', opener, SAMPLE))
        transport.unavailable_after_challenge = False
        transport.generation += 1
        self.assertTrue(send_one('192.168.4.1', opener, SAMPLE))
        self.assertEqual(transport.challenges, 2)

    def test_fresh_device_digest_challenge_alone_recovers_without_new_opener(self):
        transport = DigestTransport()
        opener = self.opener(transport)
        for _ in range(3):
            self.assertTrue(send_one('192.168.4.1', opener, SAMPLE))
            transport.generation += 1


if __name__ == "__main__":
    unittest.main()
