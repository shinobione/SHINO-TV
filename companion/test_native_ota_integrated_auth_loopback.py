"""Real legacy fixture MD5 proof integrated with C++ bounded ingress+sessions.

All socket operations are against one synthetic 127.0.0.1 ephemeral server.
No owner secret, Chrome, actual ESP8266 server, firmware write or real device.
"""
from contextlib import contextmanager
from http.cookiejar import CookieJar
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import (
    HTTPCookieProcessor, HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm,
    ProxyHandler, Request, build_opener,
)
import json
import hashlib
import re
import shutil
import socket
import subprocess
import tempfile
import unittest

import push_fsless_metrics as sender

ROOT=Path(__file__).resolve().parent.parent
HOST=ROOT/"tools/native_ota_integrated_auth_loopback.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
INGRESS=ROOT/"firmware/include/boot/NativeOtaSingleIngressShadow.h"
ACTUAL_WEB=ROOT/"firmware/src/boot/FslessWebUI.cpp"
USER="shino"
PASSWORD="disposable-only-never-owner-password"
METRICS="/api/v1/bridge/metrics"
SAMPLE={
    "ok":True,"cpu_usage":22.5,"gpu_usage":34.5,
    "memory_used_gb":8.0,"memory_total_gb":16.0,"gpu_vram_mb":2048.0,
    "gpu_temp_c":56.0,"gpu_power":120.0,"gpu_available":True,
}


@unittest.skipUnless(shutil.which("g++") and shutil.which("openssl"),
                     "host C++/OpenSSL test dependencies required in CI")
class ActualHeaderIntegratedFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="shino-integrated-auth-")
        cls.exe=Path(cls.temp.name)/"integrated-host"
        compiled=subprocess.run(
            ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
             "-DPROGMEM=","-I",str(ROOT/"tools/host_arduinojson_stubs"),
             "-I",str(ROOT/"firmware/include"),str(HOST),str(ACTUAL_WEB),
             "-o",str(cls.exe),"-lcrypto"],
            capture_output=True,text=True,timeout=40,check=False)
        if compiled.returncode:
            raise AssertionError(compiled.stdout+compiled.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @contextmanager
    def server(self,count):
        proc=subprocess.Popen(
            [str(self.exe),str(count)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            first=proc.stdout.readline().strip()
            self.assertRegex(first,r"^INTEGRATED_FIXTURE_PORT \d+$")
            base="http://127.0.0.1:"+first.split()[1]
            yield base,proc
            status=proc.wait(timeout=8)
            output=proc.stdout.read()
            err=proc.stderr.read()
            self.assertEqual(status,0,first+"\n"+output+"\n"+err)
            self.assertIn("REAL_LEGACY_DISPATCH 0 DEVICE_WRITER 0 HOST_ONLY",output)
            self.last_counts=output
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
            for file in (proc.stdout,proc.stderr):
                if file:file.close()

    @staticmethod
    def original_web_asset(name):
        # Independent extraction of the exact firmware C++ raw string, not a
        # copied fixture literal. UTF-8 source bytes == host C++ raw UTF-8.
        source=ACTUAL_WEB.read_text(encoding="utf-8")
        match=re.search(r'const char '+name+
                        r'\[\] PROGMEM = R"SHINO\((.*?)\)SHINO";',
                        source,re.DOTALL)
        if not match:
            raise AssertionError("Missing original firmware asset "+name)
        return match.group(1).encode("utf-8")

    def opener(self,base,jar=None,with_digest=True):
        handlers=[ProxyHandler({}),sender.NoRedirect()]
        if with_digest:
            mgr=HTTPPasswordMgrWithDefaultRealm()
            mgr.add_password("SHINO-FirstBoot",base+"/",USER,PASSWORD)
            handlers.append(HTTPDigestAuthHandler(mgr))
        if jar is not None:
            handlers.append(HTTPCookieProcessor(jar))
        return build_opener(*handlers)

    def raw(self,base,wire):
        addr=("127.0.0.1",int(base.rsplit(":",1)[1]))
        content=b""
        with socket.create_connection(addr,timeout=4) as sock:
            sock.settimeout(4)
            sock.sendall(wire)
            # Deliberately leave write-half OPEN, like a normal HTTP client.
            try:
                while True:
                    block=sock.recv(4096)
                    if not block:break
                    content+=block
            except ConnectionResetError:
                if not content:raise
        header,sep,body=content.partition(b"\r\n\r\n")
        self.assertEqual(sep,b"\r\n\r\n")
        self.assertIn(b"X-Shino-Host-Fixture: real-fixture-proof-no-real-handler-no-writer",
                      header)
        self.assertIn(b"Connection: close",header)
        return header,body

    def test_real_urllib_digest_bytes_cookie_and_windows_sender_share_one_ingress(self):
        # GET / anonymous, Digest retry, GET metrics, JS, capabilities,
        # Windows POST anonymous and Digest retry, cookie-only POST, OTA deny.
        with self.server(9) as (base,proc):
            jar=CookieJar()
            browser=self.opener(base,jar)
            with browser.open(Request(base+"/",headers={"Host":"192.168.4.1"}),
                              timeout=4) as res:
                self.assertEqual(res.status,200)
                page=res.read()
                self.assertEqual(page,self.original_web_asset("PAGE"))
                self.assertEqual(int(res.headers["Content-Length"]),len(page))
                self.assertIn(b'<section class="screen"',page)
                self.assertIn("SHINO_READ_SESSION=",res.headers.get("Set-Cookie",""))
                self.assertTrue(res.headers.get("X-Shino-Host-Fixture"))
            self.assertEqual(len(list(jar)),1)
            for route in (METRICS,"/ui.js","/api/v1/bridge/ota/capabilities"):
                with browser.open(Request(base+route,headers={"Host":"192.168.4.1"}),
                                  timeout=4) as res:
                    self.assertEqual(res.status,200)
                    data=res.read()
                    self.assertTrue(data)
                    if route=="/ui.js":
                        self.assertEqual(data,self.original_web_asset("SCRIPT"))
                        self.assertEqual(int(res.headers["Content-Length"]),len(data))
                        self.assertIn(b"credentials:'same-origin'",data)
                        self.assertIn(b"pollingDenied=true",data)
                    if route.endswith("capabilities"):
                        self.assertFalse(json.loads(data)["native_ota_upload_route_registered"])
            # Production sender restrictions stay unchanged: only the
            # test-scope fake sentinel maps to this localhost/ephemeral port.
            real_validate=sender.validate_host
            fake="integrated-test-loopback-only"
            original_request=sender.Request
            def local_fixture_request(url,*args,**kwargs):
                # Host names the simulated private AP even though the test
                # transport is 127.0.0.1:ephemeral. The actual sender/host
                # whitelist and strict C++ Host check are not modified.
                headers=dict(kwargs.pop("headers",{}))
                headers["Host"]="192.168.4.1"
                return original_request(url,*args,headers=headers,**kwargs)
            with patch.object(sender,"validate_host",
                              side_effect=lambda h: base.split("//",1)[1]
                                  if h==fake else real_validate(h)), \
                 patch.object(sender,"Request",side_effect=local_fixture_request):
                windows=sender.make_opener(fake,USER,PASSWORD)
                self.assertTrue(sender.send_one(fake,windows,SAMPLE,timeout=4.0))
            read_only=self.opener(base,jar,with_digest=False)
            cookie_req=Request(base+METRICS,data=sender.encode_sample(SAMPLE),
                               method="POST",headers={
                                   "Host":"192.168.4.1","Content-Type":"application/json"})
            with self.assertRaises(HTTPError) as denied:
                read_only.open(cookie_req,timeout=4)
            self.assertEqual(denied.exception.code,401)
            denied.exception.close()
            h,b=self.raw(base,b"POST /api/v1/bridge/ota/arm HTTP/1.1\r\n")
            self.assertIn(b"HTTP/1.1 403 ",h)
            self.assertIn(b"NO_WRITER",b)
        self.assertIn("ACTUAL_FIXTURE_PROOFS 2",self.last_counts)
        self.assertIn("READ_COOKIES 1",self.last_counts)
        self.assertIn("POST_PREVIEWS 1",self.last_counts)

    def test_original_progmeme_assets_are_byte_exact_and_not_anonymous(self):
        # One 401 for unauthenticated JS, then two requests for root Digest,
        # then read-only JS with the returned cookie. No synthetic text body.
        with self.server(4) as (base,proc):
            h,b=self.raw(base,b"GET /ui.js HTTP/1.1\\r\\nHost: 192.168.4.1\\r\\n\\r\\n")
            self.assertIn(b"HTTP/1.1 401 ",h)
            self.assertNotIn(b"FslessWebUI",b)
            browser=self.opener(base,CookieJar())
            with browser.open(Request(base+"/",headers={"Host":"192.168.4.1"}),
                              timeout=4) as response:
                page=response.read()
                self.assertEqual(page,self.original_web_asset("PAGE"))
                self.assertIn(b"SHINO // TV",page)
                self.assertLess(len(page),16*1024) # explicitly bounded source asset review
            with browser.open(Request(base+"/ui.js",headers={"Host":"192.168.4.1"}),
                              timeout=4) as response:
                script=response.read()
                self.assertEqual(script,self.original_web_asset("SCRIPT"))
                self.assertLess(len(script),16*1024)
                self.assertIn(b"setInterval(poll,2000)",script)
                self.assertIn(b"if(response.status===401||response.status===403)",script)
        self.assertIn("READ_COOKIES 1",self.last_counts)
        for name in ("PAGE","SCRIPT"):
            original=self.original_web_asset(name)
            self.assertEqual(len(hashlib.sha256(original).hexdigest()),64)
            self.assertNotIn(b"/api/v1/bridge/ota/upload",original)
            self.assertNotIn(b'form method="post"',original.lower())

    def test_invalid_digest_and_ambiguous_ingress_never_issue_a_read_cookie(self):
        # One refused metrics poll, two wrong root proofs, duplicate auth,
        # reserved upload, and same-feed pipeline. No fixture success.
        with self.server(6) as (base,proc):
            h,b=self.raw(base,b"GET /api/v1/bridge/metrics HTTP/1.1\r\n"
                         b"Host: 192.168.4.1\r\n\r\n")
            self.assertIn(b"HTTP/1.1 403 ",h)
            self.assertNotIn(b"WWW-Authenticate:",h)
            for auth in (
                'Digest username="shino", response="0000"',
                'Digest username="shino", realm="SHINO-FirstBoot", '
                'nonce="0123456789abcdef0123456789abcdef", '
                'uri="/api/v1/bridge/metrics", response="00000000000000000000000000000000", '
                'algorithm=MD5, qop=auth, nc=00000001, cnonce="fixtureonly"',
            ):
                h,b=self.raw(base,("GET / HTTP/1.1\r\nHost: 192.168.4.1\r\n"
                         "Authorization: "+auth+"\r\n\r\n").encode("ascii"))
                self.assertIn(b"HTTP/1.1 401 ",h)
                self.assertIn(b"WWW-Authenticate: Digest",h)
                self.assertNotIn(b"Set-Cookie:",h)
            h,b=self.raw(base,b"GET / HTTP/1.1\r\nHost: 192.168.4.1\r\n"
                         b"Authorization: Digest foo\r\n"
                         b"authorization: Digest bar\r\n\r\n")
            self.assertIn(b"HTTP/1.1 403 ",h)
            self.assertNotIn(b"Set-Cookie:",h)
            h,b=self.raw(base,b"POST /api/v1/bridge/ota/upload HTTP/1.1\r\n")
            self.assertIn(b"HTTP/1.1 403 ",h)
            h,b=self.raw(base,b"GET / HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n"
                         b"GET /ui.js HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n")
            self.assertIn(b"HTTP/1.1 403 ",h)
            self.assertNotIn(b"Set-Cookie:",h)
        self.assertIn("ACTUAL_FIXTURE_PROOFS 0",self.last_counts)
        self.assertIn("READ_COOKIES 0",self.last_counts)
        self.assertIn("POST_PREVIEWS 0",self.last_counts)

    def test_real_bridge_unmodified_and_host_verifier_not_a_production_md5_ota_gate(self):
        native=INGRESS.read_text(encoding="utf-8")
        source=HOST.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        self.assertIn("authorizationValueForHostReviewOnly",native)
        self.assertIn('Span{"authorization",13u}',native)
        self.assertIn("isLegacyProof(authorization,authorizationLength",source)
        self.assertIn("NativeOtaLegacySessionReview sessions;",source)
        self.assertIn('#include "boot/FslessWebUI.h"',source)
        self.assertIn("std::string(FslessWebUI::PAGE)",source)
        self.assertIn("std::string(FslessWebUI::SCRIPT)",source)
        self.assertIn('const char PAGE[] PROGMEM',ACTUAL_WEB.read_text(encoding="utf-8"))
        self.assertIn("NativeOtaLegacyResponsePreview::decide(",source)
        self.assertIn("htonl(INADDR_LOOPBACK)",source)
        self.assertIn("htons(0u)",source)
        self.assertNotIn("native_ota_integrated_auth_loopback",bridge)
        self.assertNotIn("NativeOtaSingleIngressShadow.h",bridge)
        self.assertEqual(bridge.count("ESP8266WebServer server(80)"),1)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"',bridge)
        self.assertEqual(sender.validate_host("192.168.4.1"),"192.168.4.1")
        with self.assertRaises(sender.SenderError):
            sender.validate_host("127.0.0.1")
        for unsafe in ("Update.begin(", "Update.write(", "Update.end(",
                       "EEPROM.commit(", "LittleFS.begin(", "ESP.restart("):
            self.assertNotIn(unsafe,source)


if __name__=="__main__":
    unittest.main()
