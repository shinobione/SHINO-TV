"""Actual loopback socket concurrency under one bounded two-slot host owner.

Slow A and full B are accepted on the same listener; B must complete before
A sends its remaining bytes. A third active concurrent peer gets an immediate
503 rather than extending the memory/slot budget. No real authentication,
browser/ESP8266, RAM sample, firmware upload or flash.
"""
from contextlib import contextmanager
from pathlib import Path
import select
import shutil
import socket
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
CPP=ROOT/"tools/native_ota_concurrent_ingress_loopback.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
DEVICE=ROOT/"firmware/src/boot/NativeOtaDevicePumpCompileProbe.cpp"


def get():
    return b"GET / HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n"


def partial():
    return b"GET / HTTP/1.1\r\nHost: 192.168"


def receive(sock,expected):
    # Use HTTP's declared message boundary; a promptly refused busy client
    # may receive an RST on socket close if unread inbound request bytes
    # remain, AFTER all Content-Length response bytes have arrived.
    # Do not wait for a graceful TCP FIN or drain a potentially huge request.
    response=b""
    while True:
        try:
            part=sock.recv(4096)
        except ConnectionResetError:
            break
        if not part:break
        response+=part
        head,separator,body_so_far=response.partition(b"\r\n\r\n")
        if separator:
            lengths=[line.split(b": ",1)[1] for line in head.split(b"\r\n")
                     if line.startswith(b"Content-Length: ")]
            if len(lengths)==1 and len(body_so_far)>=int(lengths[0]):
                break
    header,sep,body=response.partition(b"\r\n\r\n")
    assert sep==b"\r\n\r\n",response[:180]
    assert f"HTTP/1.1 {expected} ".encode() in header,header
    assert b"Connection: close" in header,header
    assert b"X-Shino-Host-Fixture: two-slot-no-auth-no-device-no-writer" in header,header
    assert len(body)==int(next(line.split(b": ",1)[1] for line in
                               header.split(b"\r\n") if line.startswith(b"Content-Length: ")))
    assert response.count(b"HTTP/1.1 ")==1
    assert b"NO_WRITER" in body if expected!=501 else b"NO_DISPATCH" in body
    return response


@unittest.skipUnless(shutil.which("g++"),"Host C++17 compiler required")
class TwoSlotSingleListenerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="shino-fairness-")
        cls.exe=Path(cls.tmp.name)/"two-slot-fixture"
        build=subprocess.run(
            ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
             "-I",str(ROOT/"firmware/include"),str(CPP),"-o",str(cls.exe)],
            capture_output=True,text=True,timeout=35,check=False)
        if build.returncode:
            raise AssertionError(build.stdout+build.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @staticmethod
    def await_log(proc,needle,limit=4.0):
        ready,_,_=select.select([proc.stdout],[],[],limit)
        if not ready:raise AssertionError("Missing admission milestone "+needle)
        line=proc.stdout.readline().strip()
        if needle not in line:
            raise AssertionError("Unexpected sanitized admission milestone: "+line)
        return line

    @contextmanager
    def server(self,connections):
        proc=subprocess.Popen([str(self.exe),str(connections)],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              text=True,bufsize=1)
        clients=[]
        try:
            line=self.await_log(proc,"HOST_FAIRNESS_PORT ")
            addr=("127.0.0.1",int(line.split()[-1]))
            def connect():
                client=socket.create_connection(addr,timeout=4)
                client.settimeout(4)
                clients.append(client)
                return client
            yield connect,proc
            rc=proc.wait(timeout=6)
            tail=proc.stdout.read()
            err=proc.stderr.read()
            self.assertEqual(rc,0,line+"\n"+tail+"\n"+err)
            self.assertIn("DISPATCH 0 WRITER 0 DEVICE 0",tail)
            self.summary=tail
        finally:
            for client in clients:client.close()
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)
            for stream in (proc.stdout,proc.stderr):
                if stream:stream.close()

    def test_slow_first_client_does_not_block_completed_second_get(self):
        with self.server(2) as (connect,proc):
            slow=connect()
            slow.sendall(partial())
            self.await_log(proc,"ADMITTED_SLOT 0 ACTIVE 1")
            fast=connect()
            fast.sendall(get())
            self.await_log(proc,"ADMITTED_SLOT 1 ACTIVE 2")
            self.assertIn(b"HOST_CONCURRENT_REVIEW_ONLY_NO_DISPATCH",receive(fast,501))
            # The slow client is still connected and has not finished its
            # Host line or body. Only now do we complete it.
            slow.sendall(b".4.1\r\n\r\n")
            receive(slow,501)
        self.assertIn("ACCEPTED 2 DENIED 0 BUSY 0 PEAK_SLOTS 2 ACTIVE 0",self.summary)

    def test_busy_third_is_immediately_refused_then_freed_slot_is_reusable(self):
        with self.server(4) as (connect,proc):
            first=connect()
            first.sendall(partial())
            self.await_log(proc,"ADMITTED_SLOT 0 ACTIVE 1")
            second=connect()
            second.sendall(partial())
            self.await_log(proc,"ADMITTED_SLOT 1 ACTIVE 2")
            third=connect()
            third.sendall(get())
            receive(third,503)
            self.await_log(proc,"REFUSED_BUSY ACTIVE 2")
            second.sendall(b".4.1\r\n\r\n")
            receive(second,501)
            fourth=connect()
            fourth.sendall(get())
            # B has closed and A remains slow: a new request must advance.
            # Close announcement may precede the new admission line.
            self.await_log(proc,"CLOSED_SLOT 1 RESULT 501")
            self.await_log(proc,"ADMITTED_SLOT 1 ACTIVE 2")
            receive(fourth,501)
            first.sendall(b".4.1\r\n\r\n")
            receive(first,501)
        self.assertIn("ACCEPTED 3 DENIED 0 BUSY 1 PEAK_SLOTS 2 ACTIVE 0",self.summary)

    def test_ota_early_refusal_does_not_consume_body_or_block_other_slot(self):
        with self.server(3) as (connect,proc):
            slow=connect()
            slow.sendall(b"POST /api/v1/bridge/metrics HTTP/1.1\r\n"
                         b"Host: 192.168.4.1\r\nContent-Type: application/json\r\n"
                         b"Content-Length: 16\r\n\r\n1")
            self.await_log(proc,"ADMITTED_SLOT 0 ACTIVE 1")
            ota=connect()
            ota.sendall(b"POST /api/v1/bridge/ota/upload HTTP/1.1\r\n")
            self.await_log(proc,"ADMITTED_SLOT 1 ACTIVE 2")
            receive(ota,403)
            # Free the refused slot without finishing the first client's POST.
            healthy=connect()
            healthy.sendall(get())
            self.await_log(proc,"CLOSED_SLOT 1 RESULT 403")
            self.await_log(proc,"ADMITTED_SLOT 1 ACTIVE 2")
            receive(healthy,501)
            slow.sendall(b"234567890123456")
            receive(slow,501)
        self.assertIn("ACCEPTED 2 DENIED 1 BUSY 0 PEAK_SLOTS 2 ACTIVE 0",self.summary)

    def test_only_local_host_fixture_and_static_xtensa_two_parser_ceiling(self):
        source=CPP.read_text(encoding="utf-8")
        device=DEVICE.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        for must in ("htonl(INADDR_LOOPBACK)","htons(0)",
                     "constexpr size_t kSlots=2u",
                     "constexpr size_t kReadPerSlotPerTurn=256u",
                     "HOST_CONCURRENT_BUSY_NO_WRITER","POLLIN",
                     "finishOnExactMessageBoundaryForHostReviewOnly"):
            self.assertIn(must,source)
        self.assertIn("2u*sizeof(ShinoNativeOta::NativeOtaSingleIngressShadow) <= 6144u",device)
        self.assertNotIn("NativeOtaSingleIngressShadow.h",bridge)
        self.assertNotIn("native_ota_concurrent_ingress_loopback",bridge)
        self.assertEqual(bridge.count("ESP8266WebServer server(80)"),1)
        for blocked in ("Update.begin(", "Update.write(", "Update.end(",
                        "EEPROM.commit(", "LittleFS.begin(", "ESP.restart(",
                        "INADDR_ANY","htons(80)"):
            self.assertNotIn(blocked,source)


if __name__=="__main__":
    unittest.main()
