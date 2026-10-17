"""Actual loopback TCP M3-D lab, one listener, no real SHINO device.

A dedicated client half-closes its WRITE side after Content-Length bytes.
Unlike ordinary HTTP clients this allows the server to require TCP FIN prior
to its 202 lab receipt, without deadlocking. No installed LINK is started.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import unittest

HOST = "192.168.1.46"  # test binding, NOT a contacted IP
DEVICE = "1234567890abcdef"
BOOT = "1234567890abcdef1234567890abcdef"
PUBLIC_TEST_KEY = bytes(range(1, 33))
TX1 = "00000000000000000000000000000001"
TX2 = "00000000000000000000000000000002"


def packet(mode="MUSIC", revision=0, tx=TX1):
    body = json.dumps({
        "boot": BOOT, "device": DEVICE, "mode": mode,
        "protocol": "shino-display-control-1", "revision": revision,
        "tx": tx,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    body_hash = hashlib.sha256(body).hexdigest()
    signed = "\n".join((
        "SHINO-M3-CONTROL-1", "POST", "/api/v1/display/mode",
        HOST, DEVICE, BOOT, str(revision), mode, tx, str(len(body)), body_hash
    )).encode("ascii")
    mac = hmac.new(PUBLIC_TEST_KEY, signed, hashlib.sha256).hexdigest()
    headers = (
        "POST /api/v1/display/mode HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        f"X-Shino-Device: {DEVICE}\r\n"
        f"X-Shino-Boot: {BOOT}\r\n"
        f"X-Shino-Revision: {revision}\r\n"
        f"X-Shino-Mode: {mode}\r\n"
        f"X-Shino-Tx: {tx}\r\n"
        f"X-Shino-Body-Sha256: {body_hash}\r\n"
        f"X-Shino-Proof: {mac}\r\n\r\n"
    ).encode("ascii")
    return headers, body


def status(raw: bytes) -> int:
    first = raw.split(b"\r\n", 1)[0].split(b" ")
    if len(first) < 3 or first[0] != b"HTTP/1.1":
        raise AssertionError(f"bad response {raw[:120]!r}")
    return int(first[1])


class LoopbackContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binary = os.environ.get("M3D_LAB_BINARY")
        if not binary:
            raise RuntimeError("M3D_LAB_BINARY required, no external executable guessing")
        target = Path(binary)
        if not target.is_file():
            raise RuntimeError(f"missing compiled C++ source: {target}")
        cls.CASES = 12
        cls.server = subprocess.Popen(
            [str(target), str(cls.CASES)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        line = cls.server.stdout.readline().strip()
        if not line.startswith("M3D_LOOPBACK_PORT="):
            raise RuntimeError(f"could not start one-listener host lab: {line!r}")
        cls.port = int(line.split("=", 1)[1])
        if not (0 < cls.port <= 65535):
            raise RuntimeError("invalid local port")

    @classmethod
    def tearDownClass(cls):
        # Lifetime of server and all requests is bounded by subprocess wait.
        try:
            out, err = cls.server.communicate(timeout=7)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            out, err = cls.server.communicate()
            raise AssertionError(f"server did not terminate: {err}")
        if cls.server.returncode != 0:
            raise AssertionError(f"server exited {cls.server.returncode}: {err}")
        expected = f"M3D_LOOPBACK_SINGLE_LISTENER_DONE={cls.CASES}"
        if expected not in out:
            raise AssertionError(f"not all socket cases visited: {out!r} {err!r}")

    def exchange(self, request: bytes, *, half_close=True, pieces=None):
        with socket.create_connection(("127.0.0.1", self.port), timeout=4) as s:
            s.settimeout(4)
            if pieces:
                position = 0
                for n in pieces:
                    block = request[position:position+n]
                    if not block:
                        break
                    s.sendall(block)
                    position += len(block)
                    time.sleep(0.002)
                s.sendall(request[position:])
            else:
                s.sendall(request)
            if half_close:
                # Explicit half-close is required by M3-C exact FIN contract.
                s.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                part = s.recv(4096)
                if not part:
                    break
                chunks.append(part)
            return b"".join(chunks)

    def test_01_valid_half_close_responds_202_after_sha(self):
        header, body = packet()
        raw = self.exchange(header + body)
        self.assertEqual(status(raw), 202)
        self.assertIn(b'"applied":false', raw)
        self.assertIn(b"CRYPTO_VERIFIED_BUT_NOT_APPLIED", raw)

    def test_02_ordinary_http_client_without_write_fin_fails_bounded(self):
        h, b = packet("MONITORING", 1, TX2)
        start = time.monotonic()
        raw = self.exchange(h + b, half_close=False)
        seconds = time.monotonic() - start
        self.assertEqual(status(raw), 408)
        self.assertLess(seconds, 3.9)  # host-only wall clock tolerance
        self.assertIn(b"REJECTED_NO_MUTATION", raw)

    def test_03_same_transaction_replay_rejected(self):
        h, b = packet()
        raw = self.exchange(h + b)
        self.assertIn(status(raw), (403, 409))
        self.assertNotIn(b'"applied":true', raw)

    def test_04_fresh_transaction_after_cas(self):
        h, b = packet("MONITORING", 1, TX2)
        raw = self.exchange(h + b)
        self.assertEqual(status(raw), 202)

    def test_05_wrong_mac_rejected_before_any_body_is_sent(self):
        h, _ = packet("MUSIC", 2, TX1)
        # No body, no half close, still must not wait for body.
        wrong = h.replace(b"X-Shino-Mode: MUSIC", b"X-Shino-Mode: AUTO")
        raw = self.exchange(wrong, half_close=False)
        self.assertEqual(status(raw), 403)

    def test_06_wrong_body_hash_rejected(self):
        h, b = packet("MUSIC", 2, TX1)
        corrupted = bytearray(b)
        corrupted[50] ^= 1
        self.assertEqual(status(self.exchange(h + corrupted)), 403)

    def test_07_extra_bytes_prior_fin_refused(self):
        h, b = packet("MUSIC", 2, TX1)
        self.assertEqual(status(self.exchange(h + b + b"EXTRA")), 403)

    def test_08_partial_body_fin_refused(self):
        h, b = packet("MUSIC", 2, TX1)
        self.assertEqual(status(self.exchange(h + b[:-1])), 403)

    def test_09_doubled_length_early_reject(self):
        h, b = packet("MUSIC", 2, TX1)
        mutated = h.replace(b"\r\nConnection: close\r\n",
                            b"\r\nContent-Length: 176\r\nConnection: close\r\n")
        self.assertEqual(status(self.exchange(mutated + b)), 403)

    def test_10_legacy_metrics_closed_not_fake_accepted(self):
        req = (
            b"POST /api/v1/bridge/metrics HTTP/1.1\r\n"
            b"Host: 192.168.1.46\r\nContent-Length: 2\r\n\r\n{}"
        )
        raw = self.exchange(req)
        self.assertEqual(status(raw), 503)
        self.assertIn(b"LEGACY_PARITY_NOT_IMPLEMENTED", raw)

    def test_11_legacy_dashboard_closed_not_fake_accepted(self):
        req = b"GET /status HTTP/1.1\r\nHost: 192.168.1.46\r\n\r\n"
        raw = self.exchange(req)
        self.assertEqual(status(raw), 503)
        self.assertIn(b"LEGACY_PARITY_NOT_IMPLEMENTED", raw)

    def test_12_wrong_path_and_header_chunking_fail_closed(self):
        h, b = packet("MUSIC", 2, TX1)
        corrupted = h.replace(b"/api/v1/display/mode", b"/api/v1/display/reboot")
        raw = self.exchange(corrupted + b, pieces=(1, 2, 3, 5, 7, 11))
        self.assertEqual(status(raw), 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
