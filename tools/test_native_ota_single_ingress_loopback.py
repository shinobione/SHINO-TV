"""True localhost TCP exercises ONE nonwriting ingress shadow for legacy vs OTA.

A recognized legacy route returns HTTP 501, because genuine credentials,
handlers, browser sessions, four-card LCD and telemetry application have NOT
been ported or tested. No actual owner device is involved.
"""
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
CPP=ROOT/"tools/native_ota_single_ingress_loopback.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"

def request(method,path,headers="",body=b""):
    if isinstance(body,str):
        body=body.encode("ascii")
    return (f"{method} {path} HTTP/1.1\r\nHost: 192.168.4.1\r\n"
            f"{headers}\r\n").encode("ascii")+body

@unittest.skipUnless(shutil.which("g++"),"CI needs host C++ compiler")
class SingleOwnerShadowSocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="shino-one-owner-shadow-")
        cls.exe=Path(cls.tmp.name)/"loopback-single-owner"
        build=subprocess.run(
            ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
             "-I",str(ROOT/"firmware/include"),str(CPP),"-o",str(cls.exe)],
            capture_output=True,text=True,timeout=35,check=False)
        if build.returncode:
            raise AssertionError(build.stderr)
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def exercise(self,wire,accepted=False,chunk=4096):
        proc=subprocess.Popen([str(self.exe)],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            preface=proc.stdout.readline().strip()
            self.assertRegex(preface,r"^SHADOW_PORT \d+$")
            port=int(preface.split()[1])
            answer=b""
            with socket.create_connection(("127.0.0.1",port),timeout=4) as sock:
                sock.settimeout(4)
                try:
                    for i in range(0,len(wire),chunk):
                        sock.sendall(wire[i:i+chunk])
                    sock.shutdown(socket.SHUT_WR)
                except (BrokenPipeError,ConnectionResetError,OSError):
                    if accepted:raise
                try:
                    while True:
                        fragment=sock.recv(1024)
                        if not fragment:break
                        answer+=fragment
                except (ConnectionResetError,BrokenPipeError):
                    if accepted:raise
            status=proc.wait(timeout=12)
            out=proc.stdout.read()
            err=proc.stderr.read()
            self.assertIn("NO_AUTH_NO_LEGACY_HANDLER_NO_WRITER",out,
                          preface+"\n"+out+"\n"+err)
            if accepted:
                self.assertEqual(status,0,preface+"\n"+out+"\n"+err)
                self.assertIn(b"501 Not Implemented",answer)
                self.assertIn(b"SHADOW_CLASSIFIED_ONLY_NO_DISPATCH",answer)
                self.assertNotIn(b"200 OK",answer)
            else:
                self.assertEqual(status,1,preface+"\n"+out+"\n"+err)
                self.assertIn("BODY_BYTES 0",out)
                self.assertNotIn(b"SHADOW_CLASSIFIED_ONLY_NO_DISPATCH",answer)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
            for pipe in (proc.stdout,proc.stderr):
                if pipe is not None:pipe.close()

    def test_one_real_host_port_recognizes_get_routes_but_dispatches_none(self):
        for path in ("/","/ui.js","/api/v1/bridge/metrics",
                     "/api/v1/bridge/status","/api/v1/bridge/fs-plan",
                     "/api/v1/bridge/ota/capabilities",
                     "/api/v1/bridge/factory-return"):
            with self.subTest(path=path):
                self.exercise(request("GET",path,
                    "Cookie: SHINO_READ_SESSION=untrusted\r\n"),accepted=True,chunk=1)

    def test_small_windows_metrics_post_framed_without_dispatching_telemetry(self):
        body=b'{"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120}'
        wire=request("POST","/api/v1/bridge/metrics",
                     "Content-Type: application/json\r\n"
                     f"Content-Length: {len(body)}\r\n",body)
        self.exercise(wire,accepted=True,chunk=1)
        self.exercise(wire,accepted=True,chunk=8192)

    def test_every_ota_looking_route_rejected_on_one_listener_before_any_body(self):
        for method,path in (
            ("POST","/api/v1/bridge/ota/arm"),
            ("POST","/api/v1/bridge/ota/upload"),
            ("POST","/api/v1/bridge/ota/capabilities"),
            ("POST","/api/v1/bridge/ota"),
            ("GET","/api/v1/bridge/ota/install"),
            ("HEAD","/api/v1/bridge/ota/upload"),
        ):
            with self.subTest(method=method,path=path):
                self.exercise(request(method,path,"Content-Length: 494404\r\n"),
                              chunk=1)

    def test_malformed_or_ambiguous_legacy_headers_rejected_by_single_listener(self):
        for wire in (
            request("GET","/","HOST: 192.168.4.1\r\n"),
            request("GET","/","Transfer-Encoding: chunked\r\n"),
            request("GET","/","Content-Length: 1\r\n",b"x"),
            request("GET","/","Expect: 100-continue\r\n"),
            request("GET","/",""),
            request("POST","/api/v1/bridge/metrics",
                    "Content-Type: application/json\r\nContent-Length: 385\r\n"),
            request("POST","/api/v1/bridge/factory-return","Content-Length: 16\r\n"),
        ):
            # A second test of missing Host is supplied without the request helper.
            if wire==request("GET","/",""):continue
            with self.subTest(length=len(wire)):
                self.exercise(wire,chunk=7)
        self.exercise(b"GET / HTTP/1.1\r\n\r\n",chunk=1)

    def test_unknown_get_is_only_metadata_classified_not_dispatched(self):
        self.exercise(request("GET","/not-an-api-route"),accepted=True,chunk=1)

    def test_incomplete_windows_post_and_extra_pipelined_bytes_are_terminal(self):
        body=b'{"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120}'
        h=("Content-Type: application/json\r\n"
           f"Content-Length: {len(body)}\r\n")
        self.exercise(request("POST","/api/v1/bridge/metrics",h,body[:-1]))
        self.exercise(request("POST","/api/v1/bridge/metrics",h,body+b"EXTRA"))

    def test_proof_binds_literal_loopback_never_actual_port80_or_updater(self):
        text=CPP.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        self.assertIn("htonl(INADDR_LOOPBACK)",text)
        self.assertIn("htons(0)",text)
        self.assertIn("501 Not Implemented",text)
        self.assertIn("SHADOW_CLASSIFIED_ONLY_NO_DISPATCH",text)
        self.assertIn("SHADOW_REJECTED_NO_WRITER",text)
        self.assertNotIn("NativeOtaSingleIngressShadow.h",bridge)
        for forbidden in ("INADDR_ANY","htons(80)","Update.begin(",
                          "Update.write(","Update.end(","installSignature(",
                          "ESP.restart(","EEPROM.commit(","LittleFS.begin("):
            code="\n".join(line for line in text.splitlines()
                           if not line.lstrip().startswith("//"))
            self.assertNotIn(forbidden,code)
if __name__=="__main__":
    unittest.main()
