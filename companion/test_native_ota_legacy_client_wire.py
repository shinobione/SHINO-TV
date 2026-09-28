"""End-to-end HOST HTTP compatibility of existing browser read-cookie and Windows
urllib MD5 Digest POST behavior. This is a localhost-only, synthetic responder,
NOT ESP8266WebServer, Chrome, a production authenticator, a real LCD or OTA.
No owner credential, device connection, firmware body, flash writer or upload.
"""
from contextlib import contextmanager
from email.message import Message
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import (
    HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm,
    HTTPCookieProcessor, ProxyHandler, build_opener, parse_http_list,
    parse_keqv_list,
)
import hashlib
import json
import threading
import unittest

import push_fsless_metrics as sender

ROOT=Path(__file__).resolve().parent.parent
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
WEB_UI=ROOT/"firmware/src/boot/FslessWebUI.cpp"
ARM="/api/v1/bridge/ota/arm"
UPLOAD="/api/v1/bridge/ota/upload"
METRICS="/api/v1/bridge/metrics"
USER="shino"
PASS="long-disposable-fixture-only-password"
REALM="SHINO-FirstBoot"
NONCE="0123456789abcdef0123456789abcdef"
COOKIE="00112233445566778899aabbccddeeff"
SAMPLE={
    "ok":True,"gpu_available":True,"cpu_usage":23.5,"gpu_usage":47.5,
    "memory_used_gb":10.2,"memory_total_gb":16.0,
    "gpu_vram_mb":2048.0,"gpu_temp_c":53.0,"gpu_power":110.0,
}


def md5(text):
    return hashlib.md5(text.encode("ascii")).hexdigest()


def valid_fixture_digest(header,method,route):
    """Independent host MD5 verifier for today's legacy realm; NOT OTA SHA-256."""
    if not header or not header.startswith("Digest "):
        return False
    pairs=parse_keqv_list(parse_http_list(header[len("Digest "):]))
    if (pairs.get("username")!=USER or pairs.get("realm")!=REALM or
        pairs.get("nonce")!=NONCE or pairs.get("uri")!=route or
        pairs.get("qop")!="auth" or pairs.get("algorithm","MD5")!="MD5" or
        pairs.get("nc")!="00000001" or not pairs.get("cnonce")):
        return False
    ha1=md5(USER+":"+REALM+":"+PASS)
    ha2=md5(method+":"+route)
    expected=md5(ha1+":"+NONCE+":"+pairs["nc"]+":"+pairs["cnonce"]+":auth:"+ha2)
    return pairs.get("response")==expected


class LoopbackServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True


@contextmanager
def fixture():
    state={"challenges":0,"poll_challenges":0,"polls":0,"browser_cookie_issued":0,
           "verified_posts":0,"last_post":None,"expired":False,
           "ota_attempts":0,"all_request_paths":[],"posts_have_cookie":[],
           "post_rejected_without_digest":0}

    class Handler(BaseHTTPRequestHandler):
        protocol_version="HTTP/1.1"
        def log_message(self,*args):
            pass
        def response(self,code,body=b"",headers=()):
            self.send_response(code)
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Shino-Host-Fixture","synthetic-no-owner-auth-no-device")
            for k,v in headers:
                self.send_header(k,v)
            self.end_headers()
            if body:self.wfile.write(body)
        def challenge(self,route):
            state["challenges"]+=1
            if route==METRICS and self.command=="GET":
                state["poll_challenges"]+=1
            self.response(401,b"",[("WWW-Authenticate",
                f'Digest realm="{REALM}", nonce="{NONCE}", algorithm=MD5, qop="auth"')])
        def has_cookie(self):
            return self.headers.get("Cookie","")==f"SHINO_READ_SESSION={COOKIE}"
        def has_digest(self):
            return valid_fixture_digest(self.headers.get("Authorization",""),
                                        self.command,self.path)
        def do_GET(self):
            state["all_request_paths"].append((self.command,self.path))
            if self.path=="/":
                if self.has_cookie():
                    self.response(200,b"HOST_HTML_NOT_ACTUALLY_SERVED")
                elif self.has_digest():
                    state["browser_cookie_issued"]+=1
                    self.response(200,b"HOST_HTML_NOT_ACTUALLY_SERVED",[
                        ("Set-Cookie",f"SHINO_READ_SESSION={COOKIE}; Path=/; "
                                      "Max-Age=7200; HttpOnly; SameSite=Strict")])
                else:self.challenge(self.path)
            elif self.path==METRICS:
                state["polls"]+=1
                if self.has_cookie() and not state["expired"]:
                    self.response(200,b'{"host_fixture_only":true,"received":true,"stale":false}')
                else:
                    # Deliberately NO WWW-Authenticate on background polling.
                    self.response(403,
                        b'{"error":"Browser session expired; reopen / and authenticate"}')
            elif self.path in ("/ui.js","/api/v1/bridge/ota/capabilities"):
                if self.has_cookie() and not state["expired"]:
                    self.response(200,b'{"host_fixture_only":true}')
                elif self.has_digest():self.response(200,b'{"host_fixture_only":true}')
                else:self.challenge(self.path)
            elif self.path in (ARM,UPLOAD) or self.path.startswith("/api/v1/bridge/ota/"):
                state["ota_attempts"]+=1
                self.response(403,b'{"error":"HOST_FIXTURE_NO_OTA_ROUTE"}')
            else:
                if self.has_digest():self.response(404,b'{"host_fixture_only":true}')
                else:self.challenge(self.path)
        def do_POST(self):
            state["all_request_paths"].append((self.command,self.path))
            length=self.headers.get("Content-Length","0")
            if not length.isdecimal() or int(length)>384:
                self.response(413,b"")
                return
            body=self.rfile.read(int(length))
            if self.path!=METRICS:
                state["ota_attempts"]+=1
                self.response(403,b'{"error":"HOST_FIXTURE_NO_WRITE_ROUTE"}')
                return
            state["posts_have_cookie"].append(self.has_cookie())
            if not self.has_digest():
                state["post_rejected_without_digest"]+=1
                self.challenge(self.path)
                return
            if not 16<=len(body)<=384:
                self.response(413,b"")
                return
            if set(json.loads(body))!=set(sender.FIELDS):
                self.response(422,b"")
                return
            state["last_post"]=body
            state["verified_posts"]+=1
            self.response(200,b'{"status":"RAM_SAMPLE_ACCEPTED","persisted":false}')

    server=LoopbackServer(("127.0.0.1",0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}",state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def opener_for(base,with_digest=True,with_cookie=False):
    handlers=[ProxyHandler({}),sender.NoRedirect()]
    if with_digest:
        store=HTTPPasswordMgrWithDefaultRealm()
        store.add_password(REALM,base+"/",USER,PASS)
        handlers.append(HTTPDigestAuthHandler(store))
    if with_cookie:
        handlers.append(HTTPCookieProcessor(CookieJar()))
    return build_opener(*handlers)


class ExistingLegacyClientWireTests(unittest.TestCase):
    def test_browser_like_cookie_polling_and_windows_post_are_separately_authorized(self):
        with fixture() as (base,state):
            # A stateful HTTP cookie-jar CLIENT is not Chrome, and placeholder
            # HTML is NOT the compiled Web UI. The real GET/401/cookie/403
            # status and authentication exchange is exercised over TCP.
            browser=opener_for(base,with_digest=True,with_cookie=True)
            with browser.open(base+"/",timeout=4) as response:
                self.assertEqual(response.status,200)
                self.assertIn(b"HOST_HTML_NOT_ACTUALLY_SERVED",response.read())
            self.assertEqual(state["browser_cookie_issued"],1)
            self.assertEqual(state["challenges"],1)
            for _ in range(4):
                with browser.open(base+METRICS,timeout=4) as response:
                    self.assertEqual(response.status,200)
                    self.assertTrue(json.loads(response.read())["host_fixture_only"])
            for route in ("/ui.js","/api/v1/bridge/ota/capabilities"):
                with browser.open(base+route,timeout=4) as response:
                    self.assertEqual(response.status,200)
                    self.assertTrue(json.loads(response.read())["host_fixture_only"])
            self.assertEqual(state["challenges"],1) # no 2-second nonce/prompt storm
            self.assertEqual(state["poll_challenges"],0)
            state["expired"]=True
            with self.assertRaises(HTTPError) as expired:
                browser.open(base+METRICS,timeout=4)
            self.assertEqual(expired.exception.code,403)
            self.assertIsNone(expired.exception.headers.get("WWW-Authenticate"))
            expired.exception.close()
            self.assertEqual(state["poll_challenges"],0)
            self.assertEqual(state["challenges"],1)

            # Actual companion sender code + Python urllib Digest POST via
            # host-only IP adapter (production validate_host remains unchanged).
            host=base.split("//",1)[1]
            original_validate=sender.validate_host
            with patch.object(sender,"validate_host",side_effect=lambda value:
                              host if value=="loopback-fixture-only"
                              else original_validate(value)):
                windows=sender.make_opener("loopback-fixture-only",USER,PASS)
                self.assertTrue(sender.send_one("loopback-fixture-only",windows,SAMPLE))
            self.assertEqual(state["verified_posts"],1)
            self.assertEqual(json.loads(state["last_post"]),json.loads(sender.encode_sample(SAMPLE)))
            self.assertEqual(state["post_rejected_without_digest"],1)
            self.assertEqual(state["ota_attempts"],0)
            self.assertEqual(set(sender.FIELDS),set(SAMPLE))
            self.assertTrue(all(path not in (ARM,UPLOAD) for _,path in state["all_request_paths"]))

    def test_read_cookie_cannot_authorize_windows_post_and_no_ota_route_is_exposed(self):
        with fixture() as (base,state):
            anonymous=opener_for(base,with_digest=False,with_cookie=False)
            from urllib.request import Request
            body=sender.encode_sample(SAMPLE)
            cookie_req=Request(base+METRICS,data=body,method="POST",headers={
                "Cookie":f"SHINO_READ_SESSION={COOKIE}",
                "Content-Type":"application/json"})
            with self.assertRaises(HTTPError) as denied:
                anonymous.open(cookie_req,timeout=4)
            self.assertEqual(denied.exception.code,401)
            denied.exception.close()
            self.assertEqual(state["verified_posts"],0)
            self.assertEqual(state["post_rejected_without_digest"],1)
            for path in (ARM,UPLOAD):
                with self.assertRaises(HTTPError) as forbidden:
                    anonymous.open(Request(base+path,data=b"{}",method="POST"),timeout=4)
                self.assertEqual(forbidden.exception.code,403)
                forbidden.exception.close()
            self.assertEqual(state["ota_attempts"],2)
            self.assertEqual(state["verified_posts"],0)

    def test_live_bridge_and_exact_browser_asset_stay_unmodified_and_get_only(self):
        bridge=BRIDGE.read_text(encoding="utf-8")
        ui=WEB_UI.read_text(encoding="utf-8")
        companion=(ROOT/"companion/push_fsless_metrics.py").read_text(encoding="utf-8")
        self.assertIn('server.on("/api/v1/bridge/metrics", HTTP_POST, acceptMetrics)',bridge)
        self.assertIn('server.on("/api/v1/bridge/metrics", HTTP_GET, sendMetrics)',bridge)
        self.assertIn('server.collectHeaders("Cookie")',bridge)
        self.assertIn("if (!requireBrowserMetricsRead()) return;",bridge)
        self.assertIn("if (!requireAuth()) return;",bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"',bridge)
        self.assertIn("credentials:'same-origin'",ui)
        self.assertIn("if(response.status===401||response.status===403)",ui)
        self.assertIn("pollingDenied=true",ui)
        self.assertIn("HTTPDigestAuthHandler(store)",companion)
        self.assertIn('ENDPOINT = "/api/v1/bridge/metrics"',companion)
        with self.assertRaises(sender.SenderError):
            sender.validate_host("127.0.0.1")
        with self.assertRaises(sender.SenderError):
            sender.validate_host("127.0.0.1:8080")


if __name__=="__main__":
    unittest.main()
