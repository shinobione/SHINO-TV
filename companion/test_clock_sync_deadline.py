"""Absolute PC exchange deadline regression; only a fake loopback server."""
import contextlib
import json
import socket
import socketserver
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import clock_sync as clock
from shino_digest_coord import digest_exchange

class Trickle(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.request.settimeout(1)
            packet=b""
            while b"\r\n\r\n" not in packet:packet+=self.request.recv(1024)
            method=packet.split(b" ",1)[0].decode()
            with self.server.guard:self.server.methods.append(method)
            if method=="GET" and self.server.phase=="body":
                body=json.dumps({"protocol":clock.PROTOCOL,"clock_enabled":True,"boot":"11"*16,"challenge":"22"*16,"challenge_ms":2000}).encode()
                self.request.sendall(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: "+str(len(body)).encode()+b"\r\n\r\n"+body)
                return
            if self.server.phase=="headers":
                self.request.sendall(b"HTTP/1.1 200 OK\r\nX-Trickle: ")
                while True:self.request.sendall(b"x");time.sleep(.05)
            else:
                body=b'{"status":"CLOCK_SAMPLE_ACCEPTED","persisted":false}'
                self.request.sendall(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: "+str(len(body)).encode()+b"\r\n\r\n")
                for ch in body:self.request.sendall(bytes((ch,)));time.sleep(.05)
        except OSError:self.server.closed.set()

class Server(socketserver.ThreadingTCPServer):
    daemon_threads=True
    def __init__(self,phase):
        self.phase=phase;self.methods=[];self.guard=threading.Lock();self.closed=threading.Event()
        super().__init__(("127.0.0.1",0),Trickle)

class DeadlineTests(unittest.TestCase):
    def test_headers_and_body_trickle_close_socket_release_lock_no_retry(self):
        real_connect=socket.create_connection
        def only_loopback(address,*a,**k):
            self.assertEqual(address[0],"127.0.0.1","NO DEVICE CONTACT")
            return real_connect(address,*a,**k)
        for phase in ("headers","body"):
            with self.subTest(phase=phase),tempfile.TemporaryDirectory(prefix="clock-deadline-") as td:
                with Server(phase) as server:
                    thread=threading.Thread(target=server.serve_forever,kwargs={"poll_interval":.02},daemon=True);thread.start()
                    try:
                        transport=clock.ClockTransport("192.168.4.1","shino","PUBLIC-INERT-CLOCK-FIXTURE")
                        # HOST-only fixed loopback seam; no public CLI transport option.
                        transport.base="http://127.0.0.1:"+str(server.server_address[1])
                        locks=Path(td)/"locks"
                        def lock(host,wait_seconds):return digest_exchange(host,wait_seconds=wait_seconds,directory=locks)
                        started=time.monotonic()
                        with patch.object(clock,"TOTAL_EXCHANGE_S",.35),patch.object(clock,"digest_exchange",lock),patch.object(socket,"create_connection",only_loopback):
                            result=clock.publish_clock("192.168.4.1",transport,authorize_clock_sync=True)
                        elapsed=time.monotonic()-started
                        self.assertLess(elapsed,.9,"absolute deadline; trickles must not refresh it")
                        self.assertEqual(result,"CLOCK_SOURCE_HOLD" if phase=="headers" else "CLOCK_UNKNOWN_NO_RETRY")
                        self.assertTrue(server.closed.wait(.7),"client socket shutdown reached fake peer")
                        self.assertIsNone(transport._deadline,"session released")
                        with digest_exchange("192.168.4.1",wait_seconds=0,directory=locks):pass
                        self.assertEqual(server.methods.count("POST"),0 if phase=="headers" else 1,"no POST retry")
                    finally:server.shutdown();thread.join(timeout=1)

if __name__=="__main__":unittest.main()

