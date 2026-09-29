"""Pinned-source assertions and optional narrow source-executed C++ probe."""
import unittest

import v07_pinned_core_probe as probe


class PinnedCoreSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.sources = probe.pinned_sources()
        except FileNotFoundError:
            raise unittest.SkipTest("pinned local ESP8266 core unavailable")

    def test_exact_core_312_fingerprints(self):
        self.assertEqual(len(probe.EXPECTED), 6)

    def test_parser_order_and_body_allocation_from_actual_source(self):
        parser = self.sources["libraries/ESP8266WebServer/src/Parsing-impl.h"]
        server = self.sources["libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h"]
        self.assertLess(parser.index("String req = client.readStringUntil('\\r');"),
                        parser.index("auto whatNow = _hook(methodStr, url"))
        self.assertLess(parser.index("auto whatNow = _hook(methodStr, url"),
                        parser.index("contentLength = headerValue.toInt();"))
        self.assertLess(parser.index("contentLength = headerValue.toInt();"),
                        parser.index("readBytesWithTimeout<ServerType>(client, contentLength, plainBuf"))
        self.assertLess(server.index("switch (_parseRequest(_currentClient))"),
                        server.index("_handleRequest();", server.index("switch (_parseRequest(_currentClient))")))
        self.assertIn("_currentHeaders[i].value=headerValue;", parser)
        self.assertIn("client.flush();", parser)

    def test_actual_auth_source_has_basic_and_unbound_digest_uri(self):
        server = self.sources["libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h"]
        auth = server[server.index("bool ESP8266WebServerTemplate<ServerType>::authenticate("):
                      server.index("String ESP8266WebServerTemplate<ServerType>::_getRandomHexString()")]
        self.assertIn('authReq.startsWith(F("Basic"))', auth)
        self.assertIn('authReq.startsWith(F("Digest"))', auth)
        self.assertIn('String _uri      = _extractParam(authReq, F("uri=\\\""));', auth)
        self.assertNotIn("_currentUri", auth)
        self.assertIn('F(":auth:")', auth)
        self.assertNotIn("auth-int", auth)

    def test_actual_stream_uses_progress_or_per_character_timeouts(self):
        stream = self.sources["stream"]
        send = self.sources["stream_send"]
        self.assertIn("_startMillis = millis();", stream)
        self.assertIn("c = timedRead();", stream[stream.index("String Stream::readStringUntil"):])
        self.assertIn("timedOut.reset();  // something has been written", send)

    def test_source_executed_unbounded_line_and_body_helper_when_compiler_exists(self):
        status, detail = probe.run_host_probe(self.sources)
        if status == "SKIPPED":
            self.skipTest(detail)
        self.assertEqual(status, "PASS", detail)

    def test_extracted_source_harness_cross_compiles_syntax_only(self):
        status, detail = probe.run_cross_syntax(self.sources)
        if status == "SKIPPED":
            self.skipTest(detail)
        self.assertEqual(status, "PASS", detail)


if __name__ == "__main__":
    unittest.main()
