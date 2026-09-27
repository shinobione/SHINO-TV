"""Host-only independent libcurl SHA-256 Digest protocol interoperability fixture.

The HTTP server just captures a header and never authenticates a request or
receives firmware. The real strict C++ gate separately verifies the captured
Authorization proof. This is neither Chrome nor a SmallTV/device test.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parent.parent
PROBE=ROOT/"tools/native_ota_external_digest_client_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"


@unittest.skipUnless(
    shutil.which("curl") and shutil.which("g++") and shutil.which("openssl"),
    "CI requires independent curl Digest client, OpenSSL and host compiler")
class ExternalDigestClientTests(unittest.TestCase):
    def test_curl_sha256_digest_response_verifies_in_actual_cpp_gate(self):
        with tempfile.TemporaryDirectory(prefix="shino-digest-wire-fixture-") as temp:
            exe=Path(temp)/"digest-wire-probe"
            compile_result=subprocess.run(
                ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(PROBE),
                 "-o",str(exe),"-lcrypto"],
                capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(compile_result.returncode,0,
                             compile_result.stdout+compile_result.stderr)
            generated=subprocess.run([str(exe),"challenge"],capture_output=True,
                                     text=True,timeout=5,check=False)
            self.assertEqual(generated.returncode,0,generated.stderr)
            challenge=generated.stdout.strip()
            self.assertEqual(challenge.count("SHA-256"),1)
            self.assertIn('qop="auth"',challenge)
            captured=[]
            class FixtureHandler(BaseHTTPRequestHandler):
                protocol_version="HTTP/1.1"
                def do_POST(self):
                    size=int(self.headers.get("Content-Length","0"))
                    if self.path!="/api/v1/bridge/ota/arm" or size>16:
                        self.send_response(404)
                        self.send_header("Content-Length","0")
                        self.end_headers()
                        return
                    self.rfile.read(size)
                    auth=self.headers.get_all("Authorization",[])
                    if not auth:
                        self.send_response(401)
                        self.send_header("WWW-Authenticate",challenge)
                        self.send_header("Content-Length","0")
                        self.end_headers()
                        return
                    captured.extend(auth)
                    # Capture ONLY. A 202 is NOT authenticated/device success.
                    self.send_response(202)
                    self.send_header("X-Shino-Host-Fixture","capture-only-no-device")
                    self.send_header("Content-Length","0")
                    self.end_headers()
                def log_message(self,*args):
                    pass

            host=HTTPServer(("127.0.0.1",0),FixtureHandler)
            thread=threading.Thread(target=host.serve_forever,daemon=True)
            thread.start()
            try:
                client=subprocess.run(
                    ["curl","--silent","--show-error","--max-time","10",
                     "--connect-timeout","3","--digest",
                     "--user","owner-fixture:not-the-owner-password",
                     "--data-binary","{}","-H","Content-Type: application/json",
                     "--output","/dev/null","--write-out","%{http_code}",
                     f"http://127.0.0.1:{host.server_port}/api/v1/bridge/ota/arm"],
                    capture_output=True,text=True,timeout=15,check=False)
            finally:
                host.shutdown()
                host.server_close()
                thread.join(timeout=5)
            self.assertEqual(client.returncode,0,client.stderr)
            self.assertEqual(client.stdout,"202",client.stderr)
            self.assertEqual(len(captured),1,"one independent client proof expected")
            auth=captured[0]
            self.assertTrue(auth.startswith("Digest "))
            self.assertIn('uri="/api/v1/bridge/ota/arm"',auth)
            self.assertRegex(auth,r'algorithm="?SHA-256"?')
            # Sanitized interoperability diagnostic: never log header values,
            # nonce/cnonce/response or any password. Independently check the
            # captured RFC7616 proof before trying the strict C++ parser.
            parameters=re.findall(
                r'(?:^Digest |,\\s*)([a-z-]+)=(?:"([^"]*)"|([^,\\s]+))',auth)
            names=[key for key,_,_ in parameters]
            expected_names={"username","realm","nonce","uri","response",
                            "opaque","qop","nc","cnonce","algorithm"}
            self.assertEqual(set(names),expected_names,
                             f"only captured parameter names: {sorted(names)}")
            self.assertEqual(len(names),10,"duplicate Digest parameter")
            fields={key: quoted if quoted else plain
                    for key,quoted,plain in parameters}
            self.assertEqual(fields["username"],"owner-fixture")
            self.assertEqual(fields["realm"],"SHINO-OTA")
            self.assertEqual(fields["nonce"],
                             "0102030405060708090a0b0c0d0e0f10")
            self.assertEqual(fields["opaque"],
                             "2122232425262728292a2b2c2d2e2f30")
            self.assertEqual(fields["qop"],"auth")
            self.assertEqual(fields["nc"],"00000001")
            self.assertEqual(fields["algorithm"],"SHA-256")
            self.assertRegex(fields["response"],r"^[0-9a-f]{64}$")
            cnonce_compatible=bool(re.fullmatch(r"[A-Za-z0-9_-]{8,64}",fields["cnonce"]))
            self.assertTrue(cnonce_compatible,"client cnonce uses additional RFC token characters")
            sha=lambda value: hashlib.sha256(value.encode("ascii")).hexdigest()
            expected_response=sha(
                sha("owner-fixture:SHINO-OTA:not-the-owner-password")+":"+
                fields["nonce"]+":"+fields["nc"]+":"+fields["cnonce"]+":auth:"+
                sha("POST:"+fields["uri"]))
            self.assertEqual(fields["response"],expected_response,
                             "independent RFC7616 SHA-256 proof mismatch")
            def verify(mode, header):
                return subprocess.run([str(exe),mode],input=header+"\n",
                                      capture_output=True,text=True,
                                      timeout=5,check=False)
            good=verify("replay",auth)
            self.assertEqual(good.returncode,0,good.stdout+good.stderr)
            self.assertIn("STRICT_DIGEST_VALID_FOR_HOST_REVIEW_ONLY",good.stdout)
            self.assertNotEqual(verify("verify",auth.replace(
                'uri="/api/v1/bridge/ota/arm"',
                'uri="/api/v1/bridge/ota/upload"')).returncode,0)
            self.assertNotEqual(verify("verify",auth.replace(
                "nc=00000001","nc=00000002")).returncode,0)
            self.assertNotEqual(verify("verify",auth.replace(
                "realm=\"SHINO-OTA\"","realm=\"WRONG\"")).returncode,0)
            bridge=BRIDGE.read_text(encoding="utf-8")
            self.assertNotIn("NativeOtaDigestChallengeReview.h",bridge)
            self.assertNotIn("native_ota_external_digest_client_probe",bridge)
            self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',bridge)


if __name__=="__main__":
    unittest.main()
