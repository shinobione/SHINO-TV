"""Host-only exact HTTP message-boundary gate: response before TCP FIN.

This is not a real browser, ESP8266 port-80 server or authentication.
The only host answers are 501 review-only / 403 deny, then socket close.
"""
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
CPP=ROOT/"tools/native_ota_message_boundary_loopback.cpp"
HEADER=ROOT/"firmware/include/boot/NativeOtaSingleIngressShadow.h"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"


def get(path="/",extra=""):
    return f"GET {path} HTTP/1.1\r\nHost: 192.168.4.1\r\n{extra}\r\n".encode("ascii")


def post(body,extra=""):
    return (f"POST /api/v1/bridge/metrics HTTP/1.1\r\n"
            f"Host: 192.168.4.1\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n{extra}\r\n").encode("ascii")+body


@unittest.skipUnless(shutil.which("g++"),"Host compiler required")
class MessageBoundaryNoFinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="shino-message-boundary-")
        cls.exe=Path(cls.temp.name)/"no-fin-fixture"
        result=subprocess.run([
            "g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
            "-I",str(ROOT/"firmware/include"),str(CPP),"-o",str(cls.exe)],
            capture_output=True,text=True,timeout=35,check=False)
        if result.returncode:
            raise AssertionError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def exchange(self,wire,expected,half_close=False,chunk=None):
        process=subprocess.Popen(
            [str(self.exe)],stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True)
        try:
            port_info=process.stdout.readline().strip()
            self.assertRegex(port_info,r"^MESSAGE_BOUNDARY_PORT \d+$")
            port=int(port_info.split()[1])
            answer=b""
            with socket.create_connection(("127.0.0.1",port),timeout=3) as sock:
                sock.settimeout(3)
                for i in range(0,len(wire),chunk or len(wire)):
                    sock.sendall(wire[i:i+(chunk or len(wire))])
                if half_close:
                    sock.shutdown(socket.SHUT_WR)
                # For normal GET/POST the write half remains OPEN. A reply
                # before the 3s timeout proves no deadlock waiting for FIN.
                while True:
                    part=sock.recv(4096)
                    if not part:
                        break
                    answer+=part
            code=process.wait(timeout=5)
            remainder=process.stdout.read()
            error=process.stderr.read()
            self.assertEqual(code,0,port_info+"\n"+remainder+"\n"+error)
            self.assertIn(f"HTTP/1.1 {expected} ".encode(),answer)
            self.assertIn(b"Connection: close\r\n",answer)
            self.assertIn(b"X-Shino-Host-Fixture: no-auth-no-device-no-writer",answer)
            self.assertEqual(answer.count(b"HTTP/1.1 "),1)
            self.assertIn("LEGACY_DISPATCH 0 WRITER 0 HTTP_ONLY_LOOPBACK",remainder)
            return answer,remainder
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
            for stream in (process.stdout,process.stderr):
                if stream:stream.close()

    def test_get_and_bounded_post_respond_without_tcp_half_close(self):
        reply,log=self.exchange(get(extra="Connection: keep-alive\r\n"),501)
        self.assertIn(b"MESSAGE_BOUNDARY_REVIEW_ONLY_NO_DISPATCH",reply)
        self.assertIn("MESSAGE_READY 1 REJECTED 0",log)
        valid=(b'{"ok":true,"cpu_usage":14.2,"gpu_usage":22.0,'
               b'"memory_used_gb":11.4,"gpu_temp_c":48.0}')
        reply,log=self.exchange(post(valid,extra="Connection: keep-alive\r\n"),
                                501,chunk=1)
        self.assertIn("MESSAGE_READY 1 REJECTED 0",log)

    def test_truncated_or_ambiguous_requests_fail_closed(self):
        body=b'{"ok":true,"cpu_usage":14.2}'
        partial=post(body)[:-3]
        self.exchange(partial,403,half_close=True)
        self.exchange(get(extra="Host: 192.168.4.1\r\n"),403)
        self.exchange(get(extra="Transfer-Encoding: chunked\r\n"),403)
        self.exchange(post(body)+b"EXTRA",403)

    def test_reserved_ota_is_not_served_and_pipelining_never_dispatches(self):
        reserved=(b"POST /api/v1/bridge/ota/upload HTTP/1.1\r\n"
                  b"Host: 192.168.4.1\r\n\r\n")
        response,_=self.exchange(reserved,403)
        self.assertIn(b"NO_WRITER",response)
        # A peer can queue more data, but this fixture sends one response then
        # closes. Exact result of later bytes in another recv is not claimed.
        response,_=self.exchange(get()+get(),501 if False else 403)
        self.assertEqual(response.count(b"HTTP/1.1 "),1)

    def test_source_is_disconnected_and_no_firmware_body_is_buffered(self):
        source=CPP.read_text(encoding="utf-8")
        header=HEADER.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        self.assertIn("finishOnExactMessageBoundaryForHostReviewOnly",header)
        self.assertIn("finishOnExactTransportClose",header)
        self.assertIn("finishOnExactMessageBoundaryForHostReviewOnly",source)
        self.assertIn("htonl(INADDR_LOOPBACK)",source)
        self.assertIn("htons(0)",source)
        self.assertNotIn("NativeOtaSingleIngressShadow.h",bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"',bridge)
        self.assertEqual(bridge.count("ESP8266WebServer server(80)"),1)
        for unsafe in ("Update.begin(", "Update.write(", "Update.end(",
                       "EEPROM.commit(", "LittleFS.begin(", "WiFiServer("):
            self.assertNotIn(unsafe,source)


if __name__=="__main__":
    unittest.main()
