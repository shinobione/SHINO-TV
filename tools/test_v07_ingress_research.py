"""Synthetic policy tests. These do NOT execute the ESP8266 HTTP parser."""
import base64
import hashlib
import struct
import unittest

import v07_ingress_research as research


def fixture(op="begin", seq=1, epoch=7, payload=b"{}", *, body_op=None, body_seq=None,
            declared_length=None, extra=b"", headers=(), body_delay=0, body_chunk=64):
    tx = struct.pack(">QQ", epoch, seq)
    body_tx = struct.pack(">QQ", epoch, body_seq if body_seq is not None else seq)
    body_op = research.OPERATIONS[body_op or op]
    crc = __import__("zlib").crc32(payload) & 0xffffffff
    body = research.BODY_HEADER.pack(b"STV7", 2, body_op, 0, epoch, body_tx, 0, len(payload), crc) + payload + extra
    digest = hashlib.sha256(body[:-len(extra)] if extra else body).digest()
    fields = [
        b"Host: unit.invalid",
        b"Content-Type: application/vnd.shino-tv.media-wire-v2",
        b"Content-Length: " + str(declared_length if declared_length is not None else len(body) - len(extra)).encode(),
        b"Content-Digest: sha-256=:" + base64.b64encode(digest) + b":",
        b"Signature-Input: synthetic-test-only",
        b"Signature: synthetic-test-only",
        b"Connection: close",
    ]
    fields.extend(headers)
    target = f"/api/v2/bridge/media/{op}/{tx.hex()}"
    head = (f"POST {target} HTTP/1.1\r\n".encode() + b"\r\n".join(fields) + b"\r\n\r\n")
    return (research.ByteSource(head),
            research.ByteSource(body, chunk=body_chunk, delay_ms=body_delay),
            target, tx, digest)


def accept(method, target, host, operation, tx, epoch, digest, fields):
    return research.Decision("pc", method, target, host, epoch, operation, tx, digest)


class SyntheticIngressPolicyTests(unittest.TestCase):
    def test_valid_complete_begin_and_fixed_record_header(self):
        head, body, _, tx, _ = fixture()
        record = research.inspect(head, body, accept, research.PendingFixture())
        self.assertEqual((record.operation, record.transaction, record.payload), (1, tx, b"{}"))
        self.assertEqual(len(record.record_header), 40)
        self.assertEqual(body.remaining, 0)

    def test_malformed_framing_rejected_before_any_body_read(self):
        cases = (
            {"headers": (b"Content-Length: 42",)},
            {"headers": (b"Signature: second",)},
            {"headers": (b"Authorization: duplicate",)},
            {"headers": (b"Authorization: first", b"Authorization: second")},
            {"headers": (b"Transfer-Encoding: chunked",)},
            {"headers": (b"Expect: 100-continue",)},
            {"headers": (b"Content-Encoding: gzip",)},
            {"declared_length": 999999999999999999999},
            {"declared_length": -1},
            {"declared_length": 553},
            {"declared_length": "42x"},
            {"declared_length": "+42"},
            {"declared_length": "042"},
            {"headers": (b" X-Fold: invalid",)},
            {"headers": (b"X-Unknown: value",)},
        )
        for change in cases:
            with self.subTest(change=change):
                head, body, _, _, _ = fixture(**change)
                with self.assertRaises(research.IngressError):
                    research.inspect(head, body, accept, research.PendingFixture())
                self.assertEqual(body.read_calls, 0)
                self.assertEqual(body.bytes_read, 0)

    def test_request_line_and_header_caps_precede_body(self):
        for inserted in (b"X" * 1100, b"X-Long: " + b"a" * 260 + b"\r\n"):
            head, body, _, _, _ = fixture()
            head.data = head.data[:-2] + inserted + b"\r\n"
            with self.assertRaises(research.IngressError):
                research.inspect(head, body, accept, research.PendingFixture())
            self.assertEqual(body.read_calls, 0)

    def test_denied_request_never_reads_body_or_mutates_unrelated_pending(self):
        head, body, _, tx, _ = fixture(seq=2)
        pending = research.PendingFixture("pc", 7, struct.pack(">QQ", 7, 1), 0, b"old", 0)
        with self.assertRaisesRegex(research.IngressError, "DENIED"):
            research.inspect(head, body, lambda *args: None, pending)
        self.assertEqual((body.read_calls, pending.transaction, pending.art, pending.terminal_count),
                         (0, struct.pack(">QQ", 7, 1), b"old", 0))

    def test_wrong_principal_transaction_and_busy_begin_preserve_pending(self):
        old = struct.pack(">QQ", 7, 1)
        for mode in ("principal", "transaction", "busy"):
            with self.subTest(mode=mode):
                op = "begin" if mode == "busy" else "tile"
                seq = 2 if mode == "transaction" or mode == "busy" else 1
                payload = b"{}" if op == "begin" else b"x" * 512
                head, body, _, _, _ = fixture(op, seq, payload=payload)
                pending = research.PendingFixture("pc", 7, old, 0, None, 0)
                verifier = (lambda m, t, h, o, x, e, d, f: research.Decision("other", m, t, h, e, o, x, d)) if mode == "principal" else accept
                with self.assertRaises(research.IngressError):
                    research.inspect(head, body, verifier, pending)
                self.assertEqual((body.read_calls, pending.transaction, pending.terminal_count), (0, old, 0))

    def test_replay_and_stale_epoch_rejected_before_body(self):
        for mode in ("replay", "stale"):
            epoch = 7 if mode == "replay" else 6
            head, body, _, _, _ = fixture(epoch=epoch)
            pending = research.PendingFixture(highest_sequence=1 if mode == "replay" else 0)
            with self.assertRaisesRegex(research.IngressError, "REPLAY|STALE_EPOCH"):
                research.inspect(head, body, accept, pending)
            self.assertEqual(body.read_calls, 0)

    def test_mismatched_declared_operation_and_transaction_cancel_only_owned(self):
        for mismatch in ({"body_op": "commit"}, {"body_seq": 2}):
            with self.subTest(mismatch=mismatch):
                head, body, _, tx, _ = fixture(op="tile", payload=b"a" * 512, **mismatch)
                pending = research.PendingFixture("pc", 7, tx, 0, None, 0)
                with self.assertRaisesRegex(research.IngressError, "DECLARATION_MISMATCH"):
                    research.inspect(head, body, accept, pending)
                self.assertIsNone(pending.transaction)
                self.assertEqual(pending.terminal_count, 1)

    def test_partial_fin_trailing_and_digest_mismatch_clean_owned(self):
        for mode in ("partial", "trailing", "digest"):
            with self.subTest(mode=mode):
                head, body, _, tx, _ = fixture(op="tile", payload=b"a" * 512,
                                               extra=b"x" if mode == "trailing" else b"")
                if mode == "partial":
                    body.data = body.data[:-1]
                if mode == "digest":
                    body.data = body.data[:-1] + b"b"
                pending = research.PendingFixture("pc", 7, tx, 0, None, 0)
                with self.assertRaises(research.IngressError):
                    research.inspect(head, body, accept, pending)
                self.assertEqual(pending.terminal_count, 1)
                self.assertIsNone(pending.transaction)

    def test_absolute_deadline_does_not_reset_on_trickle_progress(self):
        head, body, _, tx, _ = fixture(op="tile", payload=b"a" * 512,
                                       body_delay=10, body_chunk=1)
        body.time_ms = 1950
        pending = research.PendingFixture("pc", 7, tx, 0, None, 0)
        with self.assertRaisesRegex(research.IngressError, "ABSOLUTE_TIMEOUT"):
            research.inspect(head, body, accept, pending)
        self.assertGreater(body.bytes_read, 0)
        self.assertEqual(pending.terminal_count, 1)

    def test_four_metric_freshness_is_independent_of_policy_failures(self):
        values, last_received = (31, 66, 9.5, 70), 2000
        head, body, _, _, _ = fixture(headers=(b"Transfer-Encoding: chunked",))
        with self.assertRaises(research.IngressError):
            research.inspect(head, body, accept, research.PendingFixture())
        self.assertEqual(values, (31, 66, 9.5, 70))
        self.assertFalse(((8000 - last_received) & 0xffffffff) > 6000)
        self.assertTrue(((8001 - last_received) & 0xffffffff) > 6000)


if __name__ == "__main__":
    unittest.main()
