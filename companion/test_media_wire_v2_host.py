"""V0.7 Mission 1 host reference tests; V0.5 gap tests stay untouched."""
import hashlib
import struct
import unittest
from dataclasses import dataclass
from unittest.mock import patch

import media_wire_v2_host as wire


@dataclass
class FourMetrics:
    values: tuple = (0, 0, 0, 0)
    received: bool = False
    last_received_ms: int = 0

    def accept(self, values, now_ms):
        self.values, self.received, self.last_received_ms = values, True, now_ms

    def stale(self, now_ms):
        return not self.received or ((now_ms - self.last_received_ms) & 0xffffffff) > 6000


def fixture(epoch=7, seq=1, edge=48, state="PLAYING", key="a" * 64):
    tx = wire.transaction(epoch, seq)
    raw = bytes((i + seq) % 256 for i in range(edge * edge * 2))
    record = dict(v=2, tx=tx.hex(), state=state, source="Synthetic", title="Track",
                  artist="Artist", album="", position=2, duration=60, track_key=key,
                  width=edge, height=edge, pixel_format="RGB565LE" if edge else "NONE",
                  cover_len=len(raw), tile_count=len(raw) // 512,
                  cover_sha256=hashlib.sha256(raw).hexdigest() if raw else None)
    return tx, raw, record


def send(receiver, op, tx, payload=b"", index=0, now=0, principal="pc", authority=None):
    header, body = wire.encode(op, tx, payload, index=index)
    if authority is None:
        authority = wire.Authority(principal, receiver.epoch, op, tx)
    return receiver.receive(header, body, authority, now=now)


def begin(receiver, seq=1, edge=48, now=0, **changes):
    tx, raw, record = fixture(receiver.epoch, seq, edge)
    record.update(changes)
    send(receiver, wire.BEGIN, tx, wire.metadata(record), now=now)
    return tx, raw


def fill(receiver, tx, raw, now=.1):
    for index in range(len(raw) // 512):
        send(receiver, wire.TILE, tx, raw[index * 512:(index + 1) * 512], index, now)


def commit(receiver, seq=1, edge=48, now=0, **changes):
    tx, raw = begin(receiver, seq, edge, now, **changes)
    fill(receiver, tx, raw, now + .1)
    send(receiver, wire.COMMIT, tx, now=now + .2)
    return tx, raw


class WireV2HostTests(unittest.TestCase):
    def test_exact_shapes_tile_count_and_network_header(self):
        for edge, (size, count) in wire.SIZES.items():
            with self.subTest(edge=edge):
                tx, raw, record = fixture(edge=edge)
                self.assertEqual((len(raw), record["tile_count"]), (size, count))
                self.assertLessEqual(len(wire.metadata(record)), 512)
                header, payload = wire.encode(wire.BEGIN, tx, wire.metadata(record))
                self.assertEqual((len(header), len(payload)), (40, len(wire.metadata(record))))
                self.assertEqual(header[:4], b"STV7")
                self.assertEqual(header[8:16], struct.pack(">Q", 7))
                self.assertEqual(header[16:32], tx)

    def test_rgb565_little_endian_is_explicit(self):
        self.assertEqual(struct.pack("<H", ((255 >> 3) << 11)), b"\x00\xf8")
        self.assertEqual(struct.pack("<H", (63 << 5)), b"\xe0\x07")

    def test_schema_rejects_dimension_hash_tile_and_version_mismatch(self):
        for change in ({"width": 64, "height": 64}, {"height": 32},
                       {"tile_count": 4}, {"cover_len": 2048},
                       {"pixel_format": "RGB565BE"}, {"v": 1},
                       {"cover_sha256": "0" * 63}):
            with self.subTest(change=change):
                _, _, record = fixture()
                record.update(change)
                with self.assertRaises(wire.WireError):
                    wire.metadata(record)

    def test_canonical_utf8_unknown_duplicate_and_tx_binding(self):
        receiver = wire.HostReceiver(7)
        tx, _, record = fixture()
        good = wire.metadata(record)
        for bad in (b"\xff", good.replace(b'"v":2', b'"v":2,"v":2'),
                    good + b" ", good.replace(b'"v":2', b'"v":1'), b"x" * 513):
            with self.subTest(bad=bad[:20]):
                with self.assertRaises(wire.WireError):
                    send(receiver, wire.BEGIN, tx, bad)
                self.assertIsNone(receiver.pending)
        record["tx"] = wire.transaction(7, 2).hex()
        with self.assertRaisesRegex(wire.WireError, "TX_MISMATCH"):
            send(receiver, wire.BEGIN, tx, wire.metadata(record))

    def test_one_pending_busy_begin_cannot_reset_deadline(self):
        receiver = wire.HostReceiver(7)
        first, _ = begin(receiver, now=10)
        pending = receiver.pending
        with self.assertRaisesRegex(wire.WireError, "BUSY"):
            begin(receiver, 2, now=17.9)
        self.assertIs(receiver.pending, pending)
        self.assertEqual(pending.started, 10)
        with self.assertRaisesRegex(wire.WireError, "EXPIRED"):
            receiver.tick(18.001)
        self.assertIsNone(receiver.pending)
        with self.assertRaisesRegex(wire.WireError, "REPLAY"):
            send(receiver, wire.BEGIN, first, wire.metadata(fixture()[2]), now=19)

    def test_exact_eight_second_boundary_and_backward_clock(self):
        receiver = wire.HostReceiver(7)
        tx, _ = begin(receiver, edge=0, now=10)
        self.assertEqual(send(receiver, wire.COMMIT, tx, now=18), "COMMITTED")
        tx, _ = begin(receiver, 2, edge=0, now=20)
        with self.assertRaisesRegex(wire.WireError, "EXPIRED"):
            send(receiver, wire.COMMIT, tx, now=19)
        self.assertIsNone(receiver.pending)

    def test_bounded_high_water_rejects_old_ids_after_many_terminal_transactions(self):
        receiver = wire.HostReceiver(7)
        for seq in range(1, 101):
            commit(receiver, seq, 0, now=seq)
        self.assertEqual(receiver.highest_sequence, 100)
        self.assertFalse(hasattr(receiver, "terminal_tx"))
        old, _, record = fixture(seq=1, edge=0)
        with self.assertRaisesRegex(wire.WireError, "REPLAY"):
            send(receiver, wire.BEGIN, old, wire.metadata(record), now=101)

    def test_epoch_change_requires_new_external_authority(self):
        old = wire.transaction(7, 1)
        receiver = wire.HostReceiver(8)
        with self.assertRaises(wire.WireError):
            send(receiver, wire.COMMIT, old, authority=wire.Authority("pc", 7, wire.COMMIT, old))
        self.assertEqual(receiver.highest_sequence, 0)

    def test_unbound_or_stale_commit_preserves_current_pending(self):
        receiver = wire.HostReceiver(7)
        old, _ = commit(receiver, 1, 0)
        current, raw = begin(receiver, 2, 48, 1)
        with self.assertRaisesRegex(wire.WireError, "NO_MATCHING_TRANSACTION"):
            send(receiver, wire.COMMIT, old, now=1.1)
        self.assertEqual(receiver.pending.tx, current)
        fill(receiver, current, raw, 1.2)
        self.assertEqual(send(receiver, wire.COMMIT, current, now=1.3), "COMMITTED")

    def test_authenticated_principal_is_bound_to_pending(self):
        receiver = wire.HostReceiver(7)
        tx, raw = begin(receiver)
        with self.assertRaisesRegex(wire.WireError, "NO_MATCHING_TRANSACTION"):
            send(receiver, wire.TILE, tx, raw[:512], principal="other")
        self.assertEqual(receiver.pending.next_index, 0)
        self.assertEqual(send(receiver, wire.TILE, tx, raw[:512]), "STAGED")

    def test_malformed_header_rejected_without_unrelated_art_revocation(self):
        receiver = wire.HostReceiver(7)
        commit(receiver, 1)
        art = receiver.committed_cover
        tx = wire.transaction(7, 2)
        header, body = wire.encode(wire.COMMIT, tx)
        authority = wire.Authority("pc", 7, wire.COMMIT, tx)
        for bad in (header[:-1], b"FAIL" + header[4:], header[:4] + b"\x01" + header[5:],
                    header[:6] + b"\x00\x01" + header[8:]):
            with self.subTest(bad=bad[:8]):
                with self.assertRaises(wire.WireError):
                    receiver.receive(bad, body, authority, now=1)
                self.assertIs(receiver.committed_cover, art)

    def test_unrelated_unauthorized_request_cannot_revoke_art_or_pending(self):
        receiver = wire.HostReceiver(7)
        commit(receiver, 1)
        art = receiver.committed_cover
        tx, _, record = fixture(seq=2)
        header, body = wire.encode(wire.BEGIN, tx, wire.metadata(record))
        with self.assertRaisesRegex(wire.WireError, "UNAUTHORIZED"):
            receiver.receive(header, body, None, now=1)
        self.assertIs(receiver.committed_cover, art)
        self.assertIsNone(receiver.pending)
        begin(receiver, 2, now=2)
        pending = receiver.pending
        with self.assertRaisesRegex(wire.WireError, "UNAUTHORIZED"):
            receiver.receive(*wire.encode(wire.COMMIT, tx), wire.Authority("pc", 7, wire.TILE, tx), now=2.1)
        self.assertIs(receiver.pending, pending)

    def test_revocation_at_accepted_begin_and_ownership_transfer(self):
        receiver = wire.HostReceiver(7)
        commit(receiver, 1)
        tx, raw = begin(receiver, 2, 48, 1)
        stage = receiver.pending.buffer
        self.assertIsNone(receiver.committed_cover)
        self.assertEqual(receiver.view, "PC_HEALTH")
        fill(receiver, tx, raw, 1.1)
        send(receiver, wire.COMMIT, tx, now=1.2)
        self.assertIs(receiver.committed_cover, stage)
        self.assertIsNone(receiver.pending)

    def test_exact_duplicate_is_idempotent_conflict_and_order_are_terminal(self):
        for fault in ("conflict", "order", "crc", "short"):
            with self.subTest(fault=fault):
                receiver = wire.HostReceiver(7)
                tx, raw = begin(receiver)
                first = raw[:512]
                send(receiver, wire.TILE, tx, first, 0, .1)
                self.assertEqual(send(receiver, wire.TILE, tx, first, 0, .2), "DUPLICATE")
                with self.assertRaises(wire.WireError):
                    if fault == "conflict":
                        send(receiver, wire.TILE, tx, bytes([first[0] ^ 1]) + first[1:], 0, .3)
                    elif fault == "order":
                        send(receiver, wire.TILE, tx, raw[1024:1536], 2, .3)
                    elif fault == "short":
                        send(receiver, wire.TILE, tx, raw[512:1023], 1, .3)
                    else:
                        header, body = wire.encode(wire.TILE, tx, raw[512:1024], index=1)
                        receiver.receive(header[:-4] + b"\0\0\0\0", body,
                                         wire.Authority("pc", 7, wire.TILE, tx), now=.3)
                self.assertIsNone(receiver.pending)
                self.assertIsNone(receiver.committed_cover)

    def test_incomplete_sha_failure_interrupt_and_allocation_failure(self):
        for fault in ("incomplete", "sha", "abort", "oom"):
            with self.subTest(fault=fault):
                receiver = wire.HostReceiver(7)
                commit(receiver, 1)
                if fault == "oom":
                    with patch.object(wire, "bytearray", side_effect=MemoryError, create=True):
                        with self.assertRaisesRegex(wire.WireError, "ALLOCATION_FAILED"):
                            begin(receiver, 2, now=1)
                else:
                    tx, raw = begin(receiver, 2, now=1)
                    if fault == "sha":
                        receiver.pending.document["cover_sha256"] = "0" * 64
                        fill(receiver, tx, raw, 1.1)
                    with self.assertRaises(wire.WireError):
                        send(receiver, wire.ABORT if fault == "abort" else wire.COMMIT, tx, now=1.2)
                self.assertIsNone(receiver.pending)
                self.assertIsNone(receiver.committed_cover)
                self.assertEqual(receiver.view, "PC_HEALTH")
                self.assertEqual(receiver.highest_sequence, 2)

    def test_coverless_32_and_48_commit_and_overlay_boundary(self):
        receiver = wire.HostReceiver(7)
        for seq, edge in enumerate((48, 32, 0), 1):
            tx, raw = commit(receiver, seq, edge, now=seq * 10, track_key=f"{seq:064x}")
            self.assertEqual(len(receiver.committed_cover or b""), len(raw))
            self.assertEqual(receiver.view, "NOW_PLAYING")
            self.assertEqual(receiver.overlay_until, seq * 10 + .2 + 5)
            self.assertEqual(receiver.tick(seq * 10 + 5.199), "NOW_PLAYING")
            self.assertEqual(receiver.tick(seq * 10 + 5.2), "PC_HEALTH")

    def test_same_track_progress_pause_resume_do_not_restart_overlay(self):
        receiver = wire.HostReceiver(7)
        commit(receiver, 1, 0, now=0)
        deadline = receiver.overlay_until
        for seq, state in ((2, "PAUSED"), (3, "PLAYING")):
            commit(receiver, seq, 0, now=seq, state=state)
            self.assertEqual(receiver.overlay_until, deadline)
        self.assertEqual(receiver.tick(deadline), "PC_HEALTH")

    def test_four_metric_fixture_is_independent_and_exactly_stale_after_6000(self):
        receiver = wire.HostReceiver(7)
        metrics = FourMetrics()
        metrics.accept((31, 66, 9.5, 70), 2000)
        commit(receiver, 1)
        tx, _ = begin(receiver, 2, now=1)
        with self.assertRaises(wire.WireError):
            send(receiver, wire.COMMIT, tx, now=1.1)
        self.assertEqual(metrics.values, (31, 66, 9.5, 70))
        self.assertEqual(metrics.last_received_ms, 2000)
        self.assertFalse(metrics.stale(8000))
        self.assertTrue(metrics.stale(8001))
        metrics.accept((33, 68, 10, 71), 8002)
        self.assertEqual(metrics.values, (33, 68, 10, 71))


if __name__ == "__main__":
    unittest.main()
