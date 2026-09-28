"""Actual localhost HTTP status/body fixture with separate simulated Digest state.

No real Digest challenge, no owner credentials, no ArduinoJson general decoder,
no native browser assets, no actual Windows telemetry or physical LCD/flash.
The private-AP address appears only as a literal fake Host header; server is
bound to host loopback 127.0.0.1 on ephemeral port.
"""
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
HOST=ROOT/"tools/native_ota_legacy_response_loopback.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
TOKEN="0102030405060708090a0b0c0d0e0f10"
GOOD=(b'{"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,'
      b'"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,'
      b'"gpu_temp_c":56,"gpu_power":120}')
BAD_NUMBER=GOOD.replace(b'"cpu_usage":22.5',b'"cpu_usage":999')

def request(method,path,body=b"",extra=""):
    if isinstance(body,str): body=body.encode("ascii")
    if method=="POST":
        extra+=f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n"
    return (f"{method} {path} HTTP/1.1\r\nHost: 192.168.4.1\r\n"
            f"{extra}\r\n").encode("ascii")+body

@unittest.skipUnless(shutil.which("g++"),"Host g++ required")
class LegacyResponseHttpLoopbackFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="shino-response-fixture-local-")
        cls.exe=Path(cls.temp.name)/"one-owner-response-fixture"
        built=subprocess.run(
            ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
             "-I",str(ROOT/"firmware/include"),str(HOST),"-o",str(cls.exe)],
            capture_output=True,text=True,timeout=40,check=False)
        if built.returncode: raise AssertionError(built.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_case(self,mode,wire,expected,chunk=4096,half_close=True):
        proc=subprocess.Popen([str(self.exe),mode],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            first=proc.stdout.readline().strip()
            self.assertRegex(first,r"^FIXTURE_PORT \d+$")
            port=int(first.split()[1])
            response=b""
            with socket.create_connection(("127.0.0.1",port),timeout=5) as sock:
                sock.settimeout(5)
                try:
                    for at in range(0,len(wire),chunk):
                        sock.sendall(wire[at:at+chunk])
                    if half_close:
                        sock.shutdown(socket.SHUT_WR)
                except (BrokenPipeError,ConnectionResetError,OSError):
                    if expected not in (403,413):raise
                try:
                    while True:
                        part=sock.recv(2048)
                        if not part:break
                        response+=part
                except (BrokenPipeError,ConnectionResetError):
                    if expected not in (403,413):raise
            rc=proc.wait(timeout=12)
            output=proc.stdout.read()
            error=proc.stderr.read()
            self.assertEqual(rc,0,first+"\n"+output+"\n"+error)
            header,sep,body=response.partition(b"\r\n\r\n")
            self.assertEqual(sep,b"\r\n\r\n",response[:220])
            self.assertIn(f"HTTP/1.1 {expected} ".encode(),header)
            self.assertIn(b"X-Shino-Host-Fixture: synthetic-no-owner-auth-no-device-writer",
                          header)
            self.assertIn(b"Cache-Control: no-store",header)
            self.assertIn(b"X-Content-Type-Options: nosniff",header)
            lines=header.decode("ascii").split("\r\n")
            lengths=[line for line in lines if line.startswith("Content-Length: ")]
            self.assertEqual(len(lengths),1)
            self.assertEqual(len(body),int(lengths[0].split(": ",1)[1]))
            self.assertIn(f"FIXTURE_RESULT {expected}",output)
            self.assertIn("REAL_DISPATCH 0 DEVICE_WRITER 0 PREVIEW_ONLY_NO_FLASH",output)
            return header,body
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
            for pipe in (proc.stdout,proc.stderr):
                if pipe is not None:pipe.close()

    def test_anonymous_root_is_401_fixture_not_an_actual_www_authenticate_challenge(self):
        h,b=self.run_case("anonymous",request("GET","/"),401,chunk=1)
        self.assertIn(b"X-Shino-Fixture-Digest-Challenge: required-but-NOT-generated",h)
        self.assertNotIn(b"WWW-Authenticate:",h)
        self.assertNotIn(b"Set-Cookie:",h)
        self.assertEqual(json.loads(b)["error"],"HOST_FIXTURE_DIGEST_CHALLENGE_REQUIRED")
        # Forging a request Authorization header NEVER flips the separately
        # supplied synthetic 'Digest passed' flag.
        h,b=self.run_case("anonymous",request("GET","/",
            extra="Authorization: Digest username=\"fake\", response=\"fake\"\r\n"),401)
        self.assertNotIn(b"Set-Cookie:",h)

    def test_simulated_digest_root_returns_html_200_and_disposable_read_cookie(self):
        h,b=self.run_case("digest_fixture",request("GET","/"),200)
        self.assertEqual(b,b"HOST_FIXTURE_DASHBOARD_HTML_NOT_SERVED")
        self.assertIn(b"Content-Type: text/html; charset=utf-8",h)
        self.assertIn(b"Content-Security-Policy: default-src 'none'",h)
        self.assertIn(("Set-Cookie: SHINO_READ_SESSION="+TOKEN+
                       "; Path=/; Max-Age=7200; HttpOnly; SameSite=Strict").encode(),h)
        self.assertNotIn(b"WWW-Authenticate:",h)
        self.assertNotIn(b"<html",b)

    def test_preissued_synthetic_cookie_allows_read_ui_metrics_and_capabilities_only(self):
        header="Cookie: SHINO_READ_SESSION="+TOKEN+"\r\n"
        h,b=self.run_case("cookie_fixture",request("GET","/ui.js",extra=header),200,chunk=1)
        self.assertEqual(b,b"HOST_FIXTURE_JAVASCRIPT_NOT_SERVED")
        self.assertIn(b"Content-Type: application/javascript; charset=utf-8",h)
        self.assertNotIn(b"Set-Cookie:",h)
        _,b=self.run_case("cookie_fixture",request("GET","/api/v1/bridge/metrics",
                                                  extra=header),200)
        item=json.loads(b)
        self.assertEqual(item["mode"],"FSLESS_PC_TELEMETRY_RAM_ONLY")
        self.assertFalse(item["real_device_sample_read"])
        _,b=self.run_case("cookie_fixture",
            request("GET","/api/v1/bridge/ota/capabilities",extra=header),200)
        self.assertFalse(json.loads(b)["native_ota_upload_route_registered"])
        self.assertFalse(json.loads(b)["physical_installation_authorized"])

    def test_expired_or_absent_read_cookie_metrics_poll_is_403_without_digest_prompt(self):
        header="Cookie: SHINO_READ_SESSION="+TOKEN+"\r\n"
        for scenario,request_headers in (
            ("anonymous",""),
            ("digest_fixture",""),
            ("expired_cookie_fixture",header),
            ("cookie_fixture","Cookie: SHINO_READ_SESSION=wrong\r\n"),
        ):
            with self.subTest(mode=scenario):
                h,b=self.run_case(scenario,
                    request("GET","/api/v1/bridge/metrics",extra=request_headers),403)
                self.assertNotIn(b"WWW-Authenticate:",h)
                self.assertNotIn(b"X-Shino-Fixture-Digest-Challenge:",h)
                self.assertEqual(json.loads(b)["error"],
                    "Browser session expired; reopen / and authenticate")

    def test_cookie_alone_is_never_write_authority_and_diagnostics_need_digest(self):
        header="Cookie: SHINO_READ_SESSION="+TOKEN+"\r\n"
        h,_=self.run_case("cookie_fixture",
             request("POST","/api/v1/bridge/metrics",body=GOOD,extra=header),401)
        self.assertIn(b"X-Shino-Fixture-Digest-Challenge: required-but-NOT-generated",h)
        h,_=self.run_case("cookie_fixture",
             request("GET","/api/v1/bridge/status",extra=header),401)
        self.assertNotIn(b"Set-Cookie:",h)
        _,b=self.run_case("digest_fixture",
             request("GET","/api/v1/bridge/status"),200)
        self.assertTrue(json.loads(b)["host_fixture_only"])

    def test_digest_fixture_windows_post_returns_source_200_or_source_422_strings(self):
        h,b=self.run_case("digest_fixture",request("POST","/api/v1/bridge/metrics",GOOD),200,
                          chunk=1)
        self.assertEqual(json.loads(b),{"status":"RAM_SAMPLE_ACCEPTED","persisted":False})
        self.assertNotIn(b"Set-Cookie:",h)
        _,b=self.run_case("digest_fixture",request("POST","/api/v1/bridge/metrics",
                                                  BAD_NUMBER),422)
        self.assertEqual(json.loads(b)["error"],
                         "Invalid, missing or out-of-range telemetry fields")
        _,b=self.run_case("digest_fixture",request("POST","/api/v1/bridge/metrics",
                                                  b"not-valid-json-xxxx"),422)
        self.assertEqual(json.loads(b)["error"],"Invalid JSON telemetry")
        # Only the two recognized literal host fixture JSON bodies are decoded
        # into model outcomes; this is NOT an ArduinoJson implementation.

    def test_unknown_non_ota_route_requires_fixture_digest_before_404(self):
        h,b=self.run_case("anonymous",request("GET","/not-an-api-route"),401)
        self.assertIn(b"X-Shino-Fixture-Digest-Challenge:",h)
        self.assertNotIn(b"Set-Cookie:",h)
        h,b=self.run_case("digest_fixture",request("GET","/not-an-api-route"),404)
        self.assertEqual(json.loads(b),{
            "error":"No arbitrary update, erase or filesystem route exists"})
        self.assertNotIn(b"Set-Cookie:",h)

    def test_declared_oversized_windows_sample_is_never_received_before_post_auth_413(self):
        # Only bounded Content-Length metadata is parsed. No large firmware
        # or metrics body is sent/staged in this host fixture.
        for declared in (15,385,494404):
            wire=(b"POST /api/v1/bridge/metrics HTTP/1.1\r\n"
                  b"Host: 192.168.4.1\r\nContent-Type: application/json\r\n"
                  +f"Content-Length: {declared}\r\n\r\n".encode("ascii"))
            with self.subTest(declared=declared):
                h,b=self.run_case("anonymous",wire,401,chunk=1)
                self.assertIn(b"X-Shino-Fixture-Digest-Challenge:",h)
                h,b=self.run_case("digest_fixture",wire,413,chunk=1)
                self.assertEqual(json.loads(b),{
                    "error":"Invalid bounded telemetry payload length"})
                self.assertNotIn(b"Set-Cookie:",h)

    def test_reserved_ota_namespace_remains_403_even_in_synthetic_digest_mode(self):
        for method,path in (
            ("POST","/api/v1/bridge/ota/upload"),
            ("POST","/api/v1/bridge/ota/arm"),
            ("POST","/api/v1/bridge/ota/capabilities"),
            ("POST","/api/v1/bridge/factory-return"),
        ):
            with self.subTest(method=method,path=path):
                _,b=self.run_case("digest_fixture",request(method,path),403,chunk=1)
                self.assertIn(b"NO_FLASH",b)

    def test_same_ingress_replies_without_client_fin_for_legacy_status_contract(self):
        # Previous tests used shutdown(SHUT_WR). A real keep-alive browser or
        # Windows HTTP client waits for the reply without that half-close.
        cases=(
            ("anonymous",request("GET","/",extra="Connection: keep-alive\r\n"),401),
            ("digest_fixture",request("GET","/",extra="Connection: keep-alive\r\n"),200),
            ("cookie_fixture",request("GET","/api/v1/bridge/metrics",
                extra="Cookie: SHINO_READ_SESSION="+TOKEN+"\r\n"
                      "Connection: keep-alive\r\n"),200),
            ("expired_cookie_fixture",request("GET","/api/v1/bridge/metrics",
                extra="Cookie: SHINO_READ_SESSION="+TOKEN+"\r\n"),403),
            ("digest_fixture",request("POST","/api/v1/bridge/metrics",GOOD,
                extra="Connection: keep-alive\r\n"),200),
            ("digest_fixture",request("POST","/api/v1/bridge/metrics",BAD_NUMBER),422),
            ("digest_fixture",request("POST","/api/v1/bridge/ota/arm"),403),
        )
        for mode,wire,status in cases:
            with self.subTest(mode=mode,status=status):
                headers,body=self.run_case(mode,wire,status,chunk=1,half_close=False)
                self.assertEqual(headers.count(b"HTTP/1.1 "),1)
                self.assertIn(b"Connection: close",headers)
                self.assertNotIn(b"Update.",body)
                if mode=="expired_cookie_fixture":
                    self.assertNotIn(b"WWW-Authenticate:",headers)
                if b"/api/v1/bridge/ota/arm" in wire:
                    self.assertIn(b"NO_FLASH",body)

    def test_pipeline_same_feed_refused_without_dispatching_second_message(self):
        wire=request("GET","/")+request("GET","/ui.js")
        headers,body=self.run_case("digest_fixture",wire,403,half_close=False)
        self.assertIn(b"HOST_FIXTURE_INGRESS_REJECTED_NO_FLASH",body)
        self.assertEqual(headers.count(b"HTTP/1.1 "),1)

    def test_host_fixture_bound_exclusively_to_loopback_and_unwired_from_firmware(self):
        source=HOST.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        self.assertIn("htonl(INADDR_LOOPBACK)",source)
        self.assertIn("htons(0u)",source)
        self.assertIn('const bool digestFixture=mode=="digest_fixture";',source)
        self.assertIn("synthetic-no-owner-auth-no-device-writer",source)
        self.assertIn("finishOnExactMessageBoundaryForHostReviewOnly",source)
        self.assertIn("messageReady",source)
        self.assertNotIn("NativeOtaLegacyResponsePreview.h",bridge)
        without_comments="\n".join(line for line in source.splitlines()
                                   if not line.lstrip().startswith("//"))
        for forbidden in ("INADDR_ANY","htons(80)","Update.begin(","Update.write(",
                          "Update.end(","installSignature(","ESP.restart(",
                          "LittleFS.begin(","EEPROM.commit("):
            self.assertNotIn(forbidden,without_comments)

if __name__=="__main__":
    unittest.main()
