"""Real host TCP 127.0.0.1 upload fragmentation test. No ESP8266/flash use."""
import hashlib
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
CPP=ROOT/"tools/native_ota_loopback_socket_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
USER="synthetic-loopback-owner"
PASSWORD="synthetic-fixture-password-not-owner-secret"
NONCE="0123456789abcdef0123456789abcdef"
OPAQUE="fedcba9876543210fedcba9876543210"
CNONCE="abcdef0123456789"
TOKEN="0102030405060708090a0b0c0d0e0f10"
ROUTE="/api/v1/bridge/ota/upload"


def sha(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def auth():
    ha1=sha(f"{USER}:SHINO-OTA:{PASSWORD}")
    ha2=sha(f"POST:{ROUTE}")
    proof=sha(f"{ha1}:{NONCE}:00000001:{CNONCE}:auth:{ha2}")
    return (f'Digest username="{USER}", realm="SHINO-OTA", nonce="{NONCE}", '
            f'uri="{ROUTE}", response="{proof}", opaque="{OPAQUE}", '
            f'qop=auth, nc=00000001, cnonce="{CNONCE}", algorithm=SHA-256')


def header(n,authorization=None,extra=""):
    if authorization is None:
        authorization=auth()
    return (f"POST {ROUTE} HTTP/1.1\r\nHost: 192.168.4.1\r\n"
            f"Origin: http://192.168.4.1\r\nContent-Type: application/octet-stream\r\n"
            f"Content-Length: {n}\r\nAuthorization: {authorization}\r\n"
            f"X-Shino-Intent: {TOKEN}\r\n{extra}\r\n").encode("ascii")


@unittest.skipUnless(shutil.which("g++") and shutil.which("openssl"),
                     "Host test requires compiler/OpenSSL")
class LoopbackOtaTcpReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="shino-loopback-tcp-only-")
        cls.root=Path(cls.temp.name)
        cls.exe=cls.root/"loopback-ram-only"
        build=subprocess.run(
            ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
             "-I",str(ROOT/"firmware/include"),str(CPP),"-o",str(cls.exe),"-lcrypto"],
            capture_output=True,text=True,check=False,timeout=40)
        if build.returncode:
            raise AssertionError("Host-only TCP receiver failed to compile: "+build.stderr)
        cls.payload=bytes((i*73+i//19+7)&255 for i in range(64260))
        cls.selected=hashlib.sha256(cls.payload).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def exercise(self,header_bytes=None,payload=None,chunk=4096,
                 expected_ok=True,baseline=None):
        reference=self.payload if baseline is None else baseline
        selected=hashlib.sha256(reference).hexdigest()
        hdr=header(len(reference)) if header_bytes is None else header_bytes
        body=reference if payload is None else payload
        proc=subprocess.Popen(
            [str(self.exe),selected,str(len(reference))],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            portline=proc.stdout.readline().strip()
            self.assertRegex(portline,r"^LOOPBACK_PORT \d+$")
            port=int(portline.split()[1])
            self.assertGreater(port,0)
            reply=b""
            with socket.create_connection(("127.0.0.1",port),timeout=5) as sock:
                sock.settimeout(5)
                try:
                    # Splits header even at single-byte CRLF boundaries.
                    for i in range(0,len(hdr),chunk):
                        sock.sendall(hdr[i:i+chunk])
                    for i in range(0,len(body),chunk):
                        sock.sendall(body[i:i+chunk])
                    sock.shutdown(socket.SHUT_WR)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    if expected_ok:
                        raise
                try:
                    while True:
                        data=sock.recv(4096)
                        if not data:break
                        reply+=data
                except (ConnectionResetError,BrokenPipeError):
                    if expected_ok:
                        raise
            rc=proc.wait(timeout=12)
            out=proc.stdout.read()
            err=proc.stderr.read()
            if expected_ok:
                self.assertEqual(rc,0,portline+"\n"+out+"\n"+err)
                self.assertIn(b"200 OK",reply)
                self.assertIn(b"OFFLINE_REVIEW_ONLY_NO_FLASH_OK",reply)
                self.assertIn("RESULT OFFLINE_REVIEW_ONLY RAM_BYTES "+str(len(reference)),out)
            else:
                self.assertEqual(rc,1,portline+"\n"+out+"\n"+err)
                self.assertIn("RESULT REJECTED RAM_BYTES 0 NO_DEVICE_NO_FLASH",out)
                self.assertNotIn(b"OFFLINE_REVIEW_ONLY_NO_FLASH_OK",reply)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
            for pipe in (proc.stdout, proc.stderr):
                if pipe is not None:
                    pipe.close()

    def test_real_tcp_accepts_arbitrarily_fragmented_header_and_file(self):
        for chunk in (1,7,151,4096,65536):
            with self.subTest(chunk=chunk):
                self.exercise(chunk=chunk)

    def test_real_tcp_accepts_header_and_payload_in_one_transport_send(self):
        self.exercise(chunk=131072)

    def test_real_tcp_accepts_full_oem_sized_synthetic_transport(self):
        # 494404 transport bytes with no actual manufacturer application.
        reference=bytes((i*53+i//11+3)&255 for i in range(494404))
        self.exercise(baseline=reference,chunk=4096)

    def test_real_tcp_blocks_corrupt_payload_against_owner_selected_full_sha256(self):
        mutated=bytearray(self.payload)
        mutated[12345]^=1
        self.exercise(payload=mutated,expected_ok=False)

    def test_real_tcp_rejects_early_eof_or_late_extra_bytes(self):
        self.exercise(payload=self.payload[:-1],expected_ok=False)
        self.exercise(payload=self.payload+b"X",expected_ok=False)

    def test_real_tcp_rejects_duplicated_content_length_before_receiving_payload(self):
        self.exercise(header_bytes=header(len(self.payload),extra="Content-Length: 64260\r\n"),
                      payload=b"",expected_ok=False)

    def test_real_tcp_rejects_fake_digest_or_cross_origin_without_body(self):
        self.exercise(header_bytes=header(len(self.payload),authorization="Digest bogus"),
                      payload=b"",expected_ok=False)
        self.exercise(header_bytes=header(len(self.payload),extra="Origin: http://evil\r\n"),
                      payload=b"",expected_ok=False)

    def test_host_server_is_literal_loopback_only_and_no_live_device_route(self):
        source=CPP.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        self.assertIn("htonl(INADDR_LOOPBACK)",source)
        self.assertIn("htons(0u)",source)
        self.assertIn("::recv(client,segment,sizeof(segment),0)",source)
        self.assertIn("finishAfterExactFraming",source)
        self.assertIn("NO_DEVICE_NO_FLASH",source)
        for forbidden in ("Update.begin(","Update.write(","Update.end(",
                          "U_FLASH","ESP8266WebServer","LittleFS","EEPROM.commit(",
                          "INADDR_ANY"):
            real="\n".join(line for line in source.splitlines()
                           if not line.lstrip().startswith("//"))
            self.assertNotIn(forbidden,real)
        self.assertNotIn("NativeOtaStreamingReview.h",bridge)

if __name__=="__main__":
    unittest.main()
