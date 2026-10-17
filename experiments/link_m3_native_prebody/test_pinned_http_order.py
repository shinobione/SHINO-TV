"""M3-B exact Core 3.1.2 source ordering and HTTP auth gap.

Uses the existing whole-file SHA-256 pins, *not* regex snippets from a
floating upstream tag. A source mismatch is a hard failure. No live device.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from v07_pinned_core_probe import pinned_sources, EXPECTED

PARSER = "libraries/ESP8266WebServer/src/Parsing-impl.h"
IMPL = "libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h"
HEADER = "libraries/ESP8266WebServer/src/ESP8266WebServer.h"
STAGEA = ROOT / "firmware/src/boot/M9NormalStageA.cpp"


class PinnedHttpOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fails if package 3.30102.0 or any required Core source bytes drift.
        cls.source = pinned_sources()

    def test_expected_core_sources_exact_sha_pinned(self):
        for name in (PARSER, IMPL, HEADER):
            self.assertEqual(len(EXPECTED[name]), 64)
            self.assertIn(name, self.source)
        self.assertEqual(len(EXPECTED), 6)

    def test_hook_is_after_unbounded_string_request_line_before_headers(self):
        parser = self.source[PARSER]
        self.assertLess(parser.index("String req = client.readStringUntil('\\r')"),
                        parser.index("if (_hook)"))
        self.assertLess(parser.index("if (_hook)"),
                        parser.index("while(1)", parser.index("//parse headers")))
        stream = self.source["stream"]
        self.assertIn("String Stream::readStringUntil(char terminator)", stream)
        self.assertIn("ret += (char) c;", stream)

    def test_post_body_is_parsed_before_application_handler(self):
        parser = self.source[PARSER]
        impl = self.source[IMPL]
        self.assertLess(parser.index("readBytesWithTimeout<ServerType>(client, contentLength, plainBuf"),
                        parser.index("return CLIENT_REQUEST_CAN_CONTINUE;", parser.index("readBytesWithTimeout<ServerType>(client, contentLength, plainBuf")))
        self.assertLess(impl.index("switch (_parseRequest(_currentClient))"),
                        impl.index("_handleRequest();", impl.index("switch (_parseRequest(_currentClient))")))
        # The normal handler is only invoked after parsing completed; M3
        # must NOT register a normal server.on POST and call that prebody.
        self.assertIn("handled = _currentHandler->handle(*this, _currentMethod, _currentUri);", impl)

    def test_digest_does_not_bind_actual_url_body_or_nonce_count(self):
        impl = self.source[IMPL]
        start = impl.index("bool ESP8266WebServerTemplate<ServerType>::authenticateDigest(")
        end = impl.index("String ESP8266WebServerTemplate<ServerType>::_getRandomHexString()", start)
        digest = impl[start:end]
        self.assertIn('String _uri      = _extractParam(authReq, F("uri=\\""', digest)
        self.assertNotIn("_currentUri", digest)
        self.assertIn('md5.add(String(F("POST:")) + _uri)', digest)
        self.assertIn('_response == _responsecheck', digest)
        self.assertNotIn('auth-int', digest)
        self.assertNotIn("Content-Digest", digest)
        self.assertNotIn("_body", digest)

    def test_active_stagea_uses_handler_digest_only_and_no_m3_route(self):
        stage = STAGEA.read_text(encoding="utf-8")
        self.assertIn("service.on(\"/api/v1/bridge/metrics\", HTTP_POST, telemetry)", stage)
        self.assertIn("server.authenticate(", stage)
        self.assertNotIn("M3ModePrebodySyntax", stage)
        self.assertNotIn("/api/v1/display/mode", stage)
        self.assertNotIn("server.addHook(", stage)
        self.assertNotIn("service.addHook(", stage)


if __name__ == "__main__":
    unittest.main()
