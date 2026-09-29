"""Mission 3 host-only allocation and stress tests; no sockets or firmware."""
import hashlib
import unittest
from unittest.mock import patch
import zlib

import media_memory_lab as lab
import media_wire_v1 as wire


def raw(edge=64, seed=1):
    return lab.synthetic_cover(lab.IMAGE_BYTES[edge], seed)


def begin(receiver, tx_number=1, edge=64, now=0.0, payload=None):
    image = raw(edge, tx_number)
    tx = f"{tx_number:032x}"
    metadata = payload if payload is not None else f'{{"title":"track-{tx_number}"}}'.encode()
    receiver.begin(tx, metadata, len(image),
                   hashlib.sha256(image).hexdigest() if image else None, now=now)
    return tx, image


def fill(receiver, tx, image, now=0.1):
    for index in range(len(image) // lab.CHUNK_BYTES):
        chunk = image[index * lab.CHUNK_BYTES:(index + 1) * lab.CHUNK_BYTES]
        receiver.tile(tx, index, chunk, zlib.crc32(chunk) & 0xffffffff, now=now)


def complete(receiver, tx_number=1, edge=64, now=0.0):
    tx, image = begin(receiver, tx_number, edge, now)
    fill(receiver, tx, image, now + 0.1)
    receiver.commit(tx, now=now + 0.2)
    return tx, image


class PeakAllocationStrategyTests(unittest.TestCase):
    def test_current_copy_reaches_three_live_images_after_previous_commit(self):
        receiver = lab.MemoryLabReceiver(lab.CURRENT_COPY)
        complete(receiver, 1)
        tx, image = begin(receiver, 2)
        fill(receiver, tx, image)
        receiver.commit(tx, now=1)
        self.assertEqual(receiver.allocator.peak_image_live, 3 * 8192)
        self.assertEqual(receiver.allocator.image_live_bytes, 8192)

    def test_ownership_transfer_has_two_image_peak_and_no_commit_copy(self):
        receiver = lab.MemoryLabReceiver(lab.OWNERSHIP)
        complete(receiver, 1)
        complete(receiver, 2, now=1)
        self.assertEqual(receiver.allocator.peak_image_live, 2 * 8192)
        self.assertEqual(receiver.allocator.allocations, 2)
        self.assertIsInstance(receiver.committed_cover, bytearray)

    def test_revoke_first_has_one_image_peak(self):
        receiver = lab.MemoryLabReceiver(lab.REVOKE_FIRST)
        complete(receiver, 1)
        complete(receiver, 2, now=1)
        self.assertEqual(receiver.allocator.peak_image_live, 8192)
        self.assertEqual(receiver.allocator.image_live_bytes, 8192)

    def test_size_matrix_and_coverless_storage(self):
        expected = {
            lab.CURRENT_COPY.name: {0: 0, 32: 6144, 48: 13824, 64: 24576},
            lab.OWNERSHIP.name: {0: 0, 32: 4096, 48: 9216, 64: 16384},
            lab.REVOKE_FIRST.name: {0: 0, 32: 2048, 48: 4608, 64: 8192},
        }
        for strategy in lab.STRATEGIES:
            for edge in (0, 32, 48, 64):
                with self.subTest(strategy=strategy.name, edge=edge):
                    receiver = lab.MemoryLabReceiver(strategy)
                    complete(receiver, 1, edge)
                    complete(receiver, 2, edge, now=1)
                    self.assertEqual(receiver.allocator.peak_image_live,
                                     expected[strategy.name][edge])

    def test_cumulative_volume_distinct_from_peak_and_capacity(self):
        summary = lab.deterministic_stress(lab.CURRENT_COPY, 64, cycles=20)
        self.assertEqual(summary["peak_receiver_image_bytes"], 24576)
        self.assertEqual(summary["cumulative_receiver_image_bytes"], 20 * 16384)
        self.assertEqual(summary["final_live_image_bytes"], 8192)


class FailureCleanupTests(unittest.TestCase):
    def test_staging_oom_revokes_old_and_leaves_no_pending_storage(self):
        allocator = lab.LogicalAllocator()
        receiver = lab.MemoryLabReceiver(lab.OWNERSHIP, allocator)
        complete(receiver, 1)
        allocator.fail_next("staging")
        with self.assertRaises(MemoryError):
            begin(receiver, 2)
        self.assertIsNone(receiver.pending)
        self.assertIsNone(receiver.committed_cover)
        self.assertEqual(allocator.image_live_bytes, 0)
        self.assertEqual(receiver.view, "PC_HEALTH")

    def test_commit_copy_oom_releases_staging_and_revokes_old(self):
        allocator = lab.LogicalAllocator()
        receiver = lab.MemoryLabReceiver(lab.CURRENT_COPY, allocator)
        complete(receiver, 1)
        tx, image = begin(receiver, 2, now=1)
        fill(receiver, tx, image, 1.1)
        allocator.fail_next("commit_copy")
        with self.assertRaises(MemoryError):
            receiver.commit(tx, now=1.2)
        self.assertIsNone(receiver.pending)
        self.assertIsNone(receiver.committed_cover)
        self.assertEqual(allocator.image_live_bytes, 0)

    def test_metadata_copy_oom_after_staging_releases_all_images(self):
        allocator = lab.LogicalAllocator()
        receiver = lab.MemoryLabReceiver(lab.OWNERSHIP, allocator)
        complete(receiver, 1)
        with patch.object(lab, "memoryview", side_effect=MemoryError, create=True):
            with self.assertRaises(MemoryError):
                begin(receiver, 2)
        self.assertIsNone(receiver.pending)
        self.assertIsNone(receiver.committed_cover)
        self.assertEqual(allocator.image_live_bytes, 0)

    def test_capacity_failure_is_deterministic_and_fail_closed(self):
        receiver = lab.MemoryLabReceiver(lab.CURRENT_COPY, lab.LogicalAllocator(16384))
        complete(receiver, 1)
        tx, image = begin(receiver, 2, now=1)
        fill(receiver, tx, image, 1.1)
        with self.assertRaises(MemoryError):
            receiver.commit(tx, now=1.2)
        self.assertEqual(receiver.allocator.image_live_bytes, 0)

    def test_corrupt_digest_conflict_and_interruption_release_every_image(self):
        cases = ("digest", "conflict", "interrupt")
        for case in cases:
            with self.subTest(case=case):
                receiver = lab.MemoryLabReceiver(lab.OWNERSHIP)
                complete(receiver, 1)
                tx, image = begin(receiver, 2, now=1)
                if case == "digest":
                    fill(receiver, tx, image, 1.1)
                    receiver.pending.expected_sha256 = "0" * 64
                    call = lambda: receiver.commit(tx, now=1.2)
                elif case == "conflict":
                    chunk = image[:512]
                    receiver.tile(tx, 0, chunk, zlib.crc32(chunk) & 0xffffffff, now=1.1)
                    bad = bytes([chunk[0] ^ 1]) + chunk[1:]
                    call = lambda: receiver.tile(tx, 0, bad,
                                                  zlib.crc32(bad) & 0xffffffff, now=1.2)
                else:
                    call = lambda: receiver.abort(tx)
                with self.assertRaises(lab.LabError):
                    call()
                self.assertEqual(receiver.allocator.image_live_bytes, 0)
                self.assertIsNone(receiver.committed_cover)


class TransactionStressTests(unittest.TestCase):
    def test_repeated_pending_begin_rejects_without_replacing_or_extending(self):
        receiver = lab.MemoryLabReceiver(lab.OWNERSHIP)
        tx, _ = begin(receiver, 1, now=10)
        pending = receiver.pending
        with self.assertRaisesRegex(lab.LabError, "BUSY"):
            begin(receiver, 2, now=17)
        self.assertIs(receiver.pending, pending)
        self.assertEqual(receiver.pending.started, 10)
        receiver.tick(18.001)
        self.assertIsNone(receiver.pending)
        self.assertIn(tx, receiver.terminal_tx)

    def test_duplicate_chunk_idempotent_conflict_terminal_and_wrong_order_terminal(self):
        for fault in ("conflict", "order"):
            with self.subTest(fault=fault):
                receiver = lab.MemoryLabReceiver(lab.OWNERSHIP)
                tx, image = begin(receiver)
                first = image[:512]
                crc = zlib.crc32(first) & 0xffffffff
                self.assertEqual(receiver.tile(tx, 0, first, crc, now=.1), "STAGED")
                self.assertEqual(receiver.tile(tx, 0, first, crc, now=.2), "DUPLICATE")
                with self.assertRaises(lab.LabError):
                    if fault == "conflict":
                        bad = bytes([first[0] ^ 1]) + first[1:]
                        receiver.tile(tx, 0, bad, zlib.crc32(bad) & 0xffffffff, now=.3)
                    else:
                        third = image[1024:1536]
                        receiver.tile(tx, 2, third, zlib.crc32(third) & 0xffffffff, now=.3)
                self.assertEqual(receiver.allocator.image_live_bytes, 0)

    def test_stale_commit_does_not_commit_or_cancel_newer_transaction(self):
        receiver = lab.MemoryLabReceiver(lab.OWNERSHIP)
        old, _ = complete(receiver, 1)
        current, image = begin(receiver, 2, now=1)
        pending = receiver.pending
        with self.assertRaisesRegex(lab.LabError, "STALE_COMMIT"):
            receiver.commit(old, now=1.1)
        self.assertIs(receiver.pending, pending)
        fill(receiver, current, image, 1.2)
        receiver.commit(current, now=1.3)

    def test_long_metadata_malformed_utf8_and_nul_reject_before_image_allocation(self):
        for payload in (b"x" * 513, b"\xff", b'{"title":"bad\x00text"}',
                        b'{"title":'):
            with self.subTest(payload=payload[:10]):
                receiver = lab.MemoryLabReceiver(lab.OWNERSHIP)
                with self.assertRaisesRegex(lab.LabError, "BAD_METADATA"):
                    begin(receiver, payload=payload)
                self.assertEqual(receiver.allocator.allocations, 0)

    def test_coverless_transition_and_overlay_return_in_experimental_model(self):
        receiver = lab.MemoryLabReceiver(lab.OWNERSHIP)
        complete(receiver, 1)
        complete(receiver, 2, edge=0, now=1)
        self.assertIsNone(receiver.committed_cover)
        self.assertEqual(receiver.view, "NOW_PLAYING")
        self.assertEqual(receiver.tick(6.2), "PC_HEALTH")

    def test_v05_pause_resume_and_progress_do_not_restart_overlay(self):
        receiver = wire.EmulatedReceiver()
        for sequence, (state, position, now) in enumerate(
                (("PLAYING", 1, 0.0), ("PAUSED", 1, 1.0),
                 ("PAUSED", 10, 2.0), ("PLAYING", 10, 3.0)), 1):
            metadata = wire.canonical_metadata({
                "v": 1, "tx": f"{sequence:032x}", "track_key": "a" * 64,
                "state": state, "source": "SYNTHETIC", "title": "Same track",
                "artist": "Lab", "album": "", "position": position,
                "duration": 60, "cover_len": 0, "cover_sha256": None,
            })
            self.assertEqual(receiver.begin(metadata, auth_verified=True, now=now), "STAGED")
            self.assertEqual(receiver.commit(auth_verified=True, now=now), "COMMITTED")
            self.assertEqual(receiver.until, 5.0)
        self.assertEqual(receiver.tick(4.999), "NOW_PLAYING")
        self.assertEqual(receiver.tick(5.0), "PC_HEALTH")

    def test_500_transfer_cycles_for_all_strategies_and_sizes(self):
        for strategy in lab.STRATEGIES:
            for edge in (0, 32, 48, 64):
                with self.subTest(strategy=strategy.name, edge=edge):
                    result = lab.deterministic_stress(strategy, edge, cycles=500)
                    self.assertEqual(result["cycles"], 500)
                    self.assertFalse(result["metrics_stale_at_exact_boundary"])
                    self.assertTrue(result["metrics_stale_after_boundary"])


class MetricsIsolationTests(unittest.TestCase):
    def test_media_failures_never_mutate_four_metrics_or_freshness(self):
        scenarios = ("staging_oom", "commit_oom", "expired", "interrupt", "digest")
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                allocator = lab.LogicalAllocator()
                receiver = lab.MemoryLabReceiver(lab.CURRENT_COPY, allocator)
                metrics = lab.MetricsFixture()
                metrics.accept((31, 66, 9.5, 70), 2000)
                complete(receiver, 1)
                try:
                    if scenario == "staging_oom":
                        allocator.fail_next("staging")
                        begin(receiver, 2, now=1)
                    else:
                        tx, image = begin(receiver, 2, now=1)
                        if scenario in ("commit_oom", "digest"):
                            fill(receiver, tx, image, 1.1)
                        if scenario == "commit_oom":
                            allocator.fail_next("commit_copy")
                            receiver.commit(tx, now=1.2)
                        elif scenario == "expired":
                            receiver.tick(10)
                        elif scenario == "interrupt":
                            receiver.abort(tx)
                        else:
                            receiver.pending.expected_sha256 = "0" * 64
                            receiver.commit(tx, now=1.2)
                except (MemoryError, lab.LabError):
                    pass
                self.assertEqual(metrics.values, (31, 66, 9.5, 70))
                self.assertEqual(metrics.last_received_ms, 2000)
                self.assertFalse(metrics.stale(8000))
                self.assertTrue(metrics.stale(8001))
                metrics.accept((33, 68, 10.0, 71), 8002)
                self.assertEqual(metrics.values, (33, 68, 10.0, 71))

    def test_unsigned_wraparound_boundary_is_independent(self):
        metrics = lab.MetricsFixture()
        metrics.accept((27, 62, 8.5, 68), 0xfffffff0)
        self.assertFalse(metrics.stale((0xfffffff0 + 6000) & 0xffffffff))
        self.assertTrue(metrics.stale((0xfffffff0 + 6001) & 0xffffffff))


class HostProbeTests(unittest.TestCase):
    def test_cpython_probe_is_explicitly_host_scoped(self):
        result = lab.cpython_v05_probe(cycles=5)
        self.assertIn("CPython", result["scope"])
        self.assertEqual(result["cycles"], 5)
        self.assertGreater(result["traced_peak_bytes"], 0)
        self.assertGreater(result["sys_getsizeof_bytearray_8192"], 8192)


if __name__ == "__main__":
    unittest.main()
