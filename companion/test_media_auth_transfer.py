"""V0.6 SECURITY REVIEW ONLY: synthetic HTTP, fake authorization, no sockets.

These tests do NOT implement or verify production authentication. The HTTP
fixture is a proposed ordering contract, NOT ESP8266WebServer or a native route.
Tests named test_gap_* deliberately characterize unresolved V0.5 deficiencies;
their passing assertions mean the gap was reproduced, never that it was fixed.
No firmware or media_wire_v1 behavior is replaced outside temporary mock scopes.
"""
from dataclasses import dataclass, replace
import hashlib
import json
import re
import unittest
from unittest.mock import Mock, patch
import zlib

import media_wire_v1 as wire


RAW = bytes(range(256)) * 32  # synthetic 8192-byte RGB565 storage, no JPEG/file


def metadata(tx=1, *, cover=True, state="PLAYING"):
    return wire.canonical_metadata({
        "v": 1, "tx": f"{tx:032x}", "track_key": f"{tx:064x}",
        "state": state, "source": "SYNTHETIC", "title": "Test track",
        "artist": "Test artist", "album": "", "position": 1, "duration": 60,
        "cover_len": len(RAW) if cover else 0,
        "cover_sha256": hashlib.sha256(RAW).hexdigest() if cover else None,
    })


def packets(tx=1):
    return tuple(wire.Packet(f"{tx:032x}", index, RAW[index*512:(index+1)*512],
                             zlib.crc32(RAW[index*512:(index+1)*512]) & 0xffffffff)
                 for index in range(16))


def stage(receiver, tx=1, *, cover=True, now=0.0, state="PLAYING"):
    receiver.begin(metadata(tx, cover=cover, state=state), auth_verified=True, now=now)
    if cover:
        for packet in packets(tx):
            receiver.tile(packet, auth_verified=True, now=now + 0.1)


def commit(receiver, tx=1, *, cover=True, now=0.0, state="PLAYING"):
    stage(receiver, tx, cover=cover, now=now, state=state)
    return receiver.commit(auth_verified=True, now=now + 0.2)


class ReviewRejected(ValueError):
    pass


@dataclass
class FakeRequest:
    """Already-owned test bytes. No socket, URL opener, firmware or credentials."""
    head: bytes
    fragments: tuple = ()  # bytes or injected exception objects
    complete: bool = True
    elapsed: float = 0.0
    reads: int = 0

    def body_fragments(self):
        for item in self.fragments:
            self.reads += 1
            if isinstance(item, Exception):
                raise item
            yield item


def request(operation="begin", body=b"{}", *, length=None, extra=(), fragments=None):
    media_type = "application/json" if operation == "begin" else "application/octet-stream"
    headers = [("Host", "fixture.invalid"), ("Content-Type", media_type),
               ("Content-Length", str(len(body)) if length is None else length)]
    headers.extend(extra)
    head = (f"POST /test-only/{operation} HTTP/1.1\r\n" +
            "".join(f"{key}: {value}\r\n" for key, value in headers) + "\r\n").encode("ascii")
    return FakeRequest(head, (body,) if fragments is None else fragments)


class ReviewOnlyHttpGate:
    """Executable review contract, NOT a server, parser replacement or auth.

    2048 header bytes / 12 fields / 768 line bytes are provisional fixture
    ceilings only, not measured ESP8266 budgets. Synthetic paths are not a
    proposed deployed API. Chunk identity/CRC and Commit binding are not
    serialized here. No fixture result grants native implementation readiness.
    """
    def __init__(self, allocator=bytearray):
        self.allocator = allocator
        self.events = []

    def read(self, fake, authorization_test_double):
        self.events.append("bounded_headers")
        if type(fake.head) is not bytes or len(fake.head) > 2048:
            raise ReviewRejected("HEADER_LIMIT")
        if not fake.head.endswith(b"\r\n\r\n"):
            raise ReviewRejected("INCOMPLETE_HEADERS")
        lines = fake.head[:-4].split(b"\r\n")
        if len(lines) > 13 or any(len(line) > 768 for line in lines):
            raise ReviewRejected("HEADER_LIMIT")
        match = re.fullmatch(rb"POST /test-only/(begin|chunk|commit) HTTP/1\.1", lines[0])
        if not match:
            raise ReviewRejected("METHOD_OR_TARGET")
        operation = match[1].decode("ascii")
        headers = {}
        for line in lines[1:]:
            if b":" not in line:
                raise ReviewRejected("MALFORMED_HEADER")
            key, value = line.split(b":", 1)
            if not re.fullmatch(rb"[A-Za-z][A-Za-z0-9-]*", key):
                raise ReviewRejected("MALFORMED_HEADER")
            if any(c < 32 or c > 126 for c in value):
                raise ReviewRejected("MALFORMED_HEADER")
            key = key.lower()
            if key in headers:
                raise ReviewRejected("DUPLICATE_HEADER")
            headers[key] = value.strip()
        if any(key in headers for key in
               (b"transfer-encoding", b"content-encoding", b"expect", b"origin")):
            raise ReviewRejected("UNSUPPORTED_FRAMING_OR_ORIGIN")
        if headers.get(b"host") != b"fixture.invalid":
            raise ReviewRejected("HOST")
        expected_type = b"application/json" if operation == "begin" else b"application/octet-stream"
        if headers.get(b"content-type") != expected_type:
            raise ReviewRejected("CONTENT_TYPE")
        size = headers.get(b"content-length", b"")
        if not re.fullmatch(rb"0|[1-9][0-9]{0,8}", size):
            raise ReviewRejected("CONTENT_LENGTH")
        size = int(size)
        if not {"begin": 1 <= size <= 512, "chunk": size == 512,
                "commit": size == 0}[operation]:
            raise ReviewRejected("BODY_LIMIT")
        self.events.append("authorization_TEST_DOUBLE")
        # This decision is injected by test code, NEVER derived from a header.
        if authorization_test_double(fake) is not True:
            raise ReviewRejected("UNAUTHORIZED_TEST_DOUBLE")
        try:
            self.events.append("bounded_body_allocation")
            body = self.allocator(size)
            used = 0
            for fragment in fake.body_fragments():
                self.events.append("body_read")
                if type(fragment) is not bytes or len(fragment) > size - used:
                    raise ReviewRejected("EXTRA_BODY")
                body[used:used+len(fragment)] = fragment
                used += len(fragment)
            if not fake.complete or used != size:
                raise ReviewRejected("INCOMPLETE_BODY")
            if fake.elapsed < 0 or fake.elapsed > wire.MAX_TRANSACTION_SECONDS:
                raise ReviewRejected("ABSOLUTE_DEADLINE")
            self.events.append("complete_body_only")
            return bytes(body)
        except (MemoryError, ConnectionError, TimeoutError) as exc:
            raise ReviewRejected(type(exc).__name__) from exc


class ProtocolValidationTests(unittest.TestCase):
    def test_malformed_utf8_json_and_surrogate_revoke_old_art_before_staging(self):
        for payload in (b"\xff", b'{"title":"\xc3("}', b"{", b"null", b"[]",
                        metadata().replace(b"Test track", b"\\ud800")):
            with self.subTest(payload=payload):
                receiver = wire.EmulatedReceiver()
                commit(receiver, 2)
                with patch.object(wire, "bytearray", create=True) as alloc:
                    with self.assertRaises(wire.ProtocolError):
                        receiver.begin(payload, auth_verified=True, now=1)
                    alloc.assert_not_called()
                self.assertIsNone(receiver.committed)
                self.assertIsNone(receiver.pending)
                self.assertEqual(receiver.view, "PC_HEALTH")

    def test_wrong_metadata_types_unknown_fields_and_duplicate_json_fields(self):
        for key, value in (("v", True), ("cover_len", True), ("position", True),
                           ("duration", -1), ("title", []), ("state", {}),
                           ("tx", 12), ("cover_sha256", 12), ("unexpected", 1)):
            with self.subTest(key=key):
                record = json.loads(metadata())
                record[key] = value
                with self.assertRaises(wire.ProtocolError):
                    wire.EmulatedReceiver().begin(json.dumps(record).encode(), auth_verified=True)
        duplicate = metadata().replace(b'"v":1', b'"v":1,"v":1')
        with self.assertRaises(wire.ProtocolError):
            wire.EmulatedReceiver().begin(duplicate, auth_verified=True)

    def test_oversize_metadata_is_rejected_before_json_or_cover_allocation(self):
        with patch.object(wire.json, "loads") as parse, patch.object(wire, "bytearray", create=True) as alloc:
            with self.assertRaisesRegex(wire.ProtocolError, "OVERSIZE_METADATA"):
                wire.EmulatedReceiver().begin(b"x" * 513, auth_verified=True)
            parse.assert_not_called()
            alloc.assert_not_called()

    def test_chunk_types_order_identity_crc_and_final_sha_fail_closed(self):
        first = packets()[0]
        invalid = (replace(first, index=True), replace(first, index=-1),
                   replace(first, index=16), packets()[1], replace(first, tx="f" * 32),
                   replace(first, body=b""), replace(first, body=b"x" * 513),
                   replace(first, crc32=True), replace(first, crc32=first.crc32 ^ 1))
        for item in invalid:
            with self.subTest(item=item.index):
                receiver = wire.EmulatedReceiver()
                commit(receiver, 2)
                receiver.begin(metadata(), auth_verified=True, now=1)
                with self.assertRaises(wire.ProtocolError):
                    receiver.tile(item, auth_verified=True, now=2)
                self.assertIsNone(receiver.pending)
                self.assertIsNone(receiver.committed)
        receiver = wire.EmulatedReceiver()
        receiver.begin(metadata(), auth_verified=True)
        for item in packets():
            body = b"z" * 512 if item.index == 15 else item.body
            receiver.tile(replace(item, body=body, crc32=zlib.crc32(body)), auth_verified=True)
        with self.assertRaisesRegex(wire.ProtocolError, "FINAL_SHA_MISMATCH"):
            receiver.commit(auth_verified=True)
        self.assertIsNone(receiver.committed)


class AuthorizationGateOrderingTests(unittest.TestCase):
    def test_unauthenticated_fake_request_never_reads_or_allocates_body(self):
        for decision in (False, None, 1, "valid-cookie", "Digest pretend"):
            with self.subTest(decision=decision):
                alloc = Mock(side_effect=AssertionError("must not allocate"))
                fake = request(extra=(("Authorization", "Digest test-only"),))
                with self.assertRaisesRegex(ReviewRejected, "UNAUTHORIZED"):
                    ReviewOnlyHttpGate(alloc).read(fake, lambda _: decision)
                self.assertEqual(fake.reads, 0)
                alloc.assert_not_called()

    def test_test_double_is_called_before_allocation_and_body_read(self):
        gate = ReviewOnlyHttpGate()
        fake = request()
        def test_double(_):
            self.assertEqual(fake.reads, 0)
            self.assertNotIn("bounded_body_allocation", gate.events)
            return True
        self.assertEqual(gate.read(fake, test_double), b"{}")
        self.assertEqual(gate.events, ["bounded_headers", "authorization_TEST_DOUBLE",
                                      "bounded_body_allocation", "body_read", "complete_body_only"])

    def test_read_cookie_alone_cannot_authorize_or_mutate_receiver(self):
        receiver = wire.EmulatedReceiver()
        commit(receiver)
        old = receiver.committed
        fake = request(extra=(("Cookie", "SHINO_READ_SESSION=test-only"),))
        with self.assertRaisesRegex(ReviewRejected, "UNAUTHORIZED"):
            ReviewOnlyHttpGate().read(fake, lambda _: False)
        # The proposed outer gate never dispatched this unowned request.
        self.assertIs(receiver.committed, old)

    def test_v05_boolean_gate_precedes_parse_and_cover_allocation(self):
        with patch.object(wire.json, "loads") as parse, patch.object(wire, "bytearray", create=True) as alloc:
            with self.assertRaisesRegex(wire.ProtocolError, "UNAUTHORIZED"):
                wire.EmulatedReceiver().begin(metadata(), auth_verified=1)
            parse.assert_not_called()
            alloc.assert_not_called()


class RequestFramingAndBodyLimitTests(unittest.TestCase):
    def assert_early_rejection(self, fake):
        alloc, auth = Mock(), Mock(return_value=True)
        with self.assertRaises(ReviewRejected):
            ReviewOnlyHttpGate(alloc).read(fake, auth)
        alloc.assert_not_called()
        auth.assert_not_called()
        self.assertEqual(fake.reads, 0)

    def test_content_length_missing_duplicate_invalid_or_oversized(self):
        for value in ("513", "8192", "999999999999999", "-1", "+2", "2, 2", "2x", "02", ""):
            with self.subTest(value=value):
                self.assert_early_rejection(request(length=value))
        for value in ("2", "3"):
            self.assert_early_rejection(request(extra=(("content-length", value),)))
        fake = request()
        fake.head = fake.head.replace(b"Content-Length: 2\r\n", b"")
        self.assert_early_rejection(fake)

    def test_ambiguous_framing_encoding_origin_and_duplicate_authorization(self):
        for header in (("Transfer-Encoding", "chunked"), ("Transfer-Encoding", "identity"),
                       ("Content-Encoding", "gzip"), ("Expect", "100-continue"),
                       ("Origin", "https://untrusted.invalid")):
            with self.subTest(header=header):
                self.assert_early_rejection(request(extra=(header,)))
        self.assert_early_rejection(request(extra=(("Authorization", "first-test-double"),
                                                   ("authorization", "second-test-double"))))

    def test_header_limits_malformed_target_and_obs_fold(self):
        fakes = [request(extra=(("X-Pad", "x"*2048),)),
                 request(extra=tuple((f"X-{i}", "x") for i in range(13)))]
        for old, new in ((b"POST", b"GET"), (b"/test-only/begin", b"/test-only/begin?x=1"),
                         (b"Host:", b" Host:"), (b"fixture.invalid", b"wrong.invalid"),
                         (b"application/json", b"multipart/form-data")):
            fake = request()
            fake.head = fake.head.replace(old, new)
            fakes.append(fake)
        fake = request()
        fake.head = fake.head[:-2]
        fakes.append(fake)
        for fake in fakes:
            with self.subTest(head=fake.head[:60]):
                self.assert_early_rejection(fake)

    def test_operation_body_ceiling_and_exact_valid_boundaries(self):
        for operation, size in (("begin", 0), ("begin", 513), ("chunk", 511),
                                ("chunk", 513), ("commit", 1)):
            self.assert_early_rejection(request(operation, b"x"*size))
        for operation, body in (("begin", b"x"*512), ("chunk", RAW[:512]), ("commit", b"")):
            self.assertEqual(ReviewOnlyHttpGate().read(request(operation, body), lambda _: True), body)

    def test_partial_fragments_and_forged_length_never_deliver_partial_body(self):
        self.assertEqual(ReviewOnlyHttpGate().read(request(fragments=(b"{", b"}")), lambda _: True), b"{}")
        for fragments in ((b"{",), (b"{}x",), (b"{}", b"x")):
            gate = ReviewOnlyHttpGate()
            with self.assertRaises(ReviewRejected):
                gate.read(request(fragments=fragments), lambda _: True)
            self.assertNotIn("complete_body_only", gate.events)

    def test_incomplete_disconnect_timeout_and_simulated_body_oom(self):
        for failure in (ConnectionError("fake FIN"), TimeoutError("fake timeout")):
            with self.assertRaises(ReviewRejected):
                ReviewOnlyHttpGate().read(request(fragments=(b"{", failure)), lambda _: True)
        for complete, elapsed in ((False, 0), (True, 8.001), (True, -1)):
            fake = request()
            fake.complete, fake.elapsed = complete, elapsed
            with self.assertRaises(ReviewRejected):
                ReviewOnlyHttpGate().read(fake, lambda _: True)
        fake = request()
        with self.assertRaisesRegex(ReviewRejected, "MemoryError"):
            ReviewOnlyHttpGate(Mock(side_effect=MemoryError)).read(fake, lambda _: True)
        self.assertEqual(fake.reads, 0)


class TransactionConsistencyAndReplayTests(unittest.TestCase):
    def test_committed_id_replay_and_repeated_commit_reject_and_revoke_art(self):
        for repeat in ("begin", "commit"):
            receiver = wire.EmulatedReceiver()
            commit(receiver)
            with self.assertRaises(wire.ProtocolError):
                if repeat == "begin":
                    receiver.begin(metadata(), auth_verified=True, now=1)
                else:
                    receiver.commit(auth_verified=True, now=1)
            self.assertIsNone(receiver.pending)
            self.assertIsNone(receiver.committed)

    def test_identical_chunk_retry_does_not_advance_or_extend_deadline(self):
        receiver = wire.EmulatedReceiver()
        receiver.begin(metadata(), auth_verified=True, now=0)
        self.assertEqual(receiver.tile(packets()[0], auth_verified=True, now=1), "STAGED")
        self.assertEqual(receiver.tile(packets()[0], auth_verified=True, now=7), "DUPLICATE")
        self.assertEqual((receiver.pending["next"], receiver.pending["started"]), (1, 0))
        conflicting = replace(packets()[0], body=b"z"*512, crc32=zlib.crc32(b"z"*512))
        with self.assertRaisesRegex(wire.ProtocolError, "CONFLICTING_RETRY"):
            receiver.tile(conflicting, auth_verified=True, now=7)
        self.assertIsNone(receiver.pending)

    def test_gap_pending_begin_reuses_id_and_resets_deadline(self):
        receiver = wire.EmulatedReceiver()
        receiver.begin(metadata(), auth_verified=True, now=0)
        receiver.tile(packets()[0], auth_verified=True, now=1)
        receiver.begin(metadata(), auth_verified=True, now=7.9)
        self.assertEqual((receiver.pending["next"], receiver.pending["started"]), (0, 7.9))
        receiver.tick(9)
        self.assertIsNotNone(receiver.pending)  # GAP: original eight seconds passed

    def test_gap_aborted_and_expired_ids_can_be_reused(self):
        for abort in (False, True):
            receiver = wire.EmulatedReceiver()
            receiver.begin(metadata(), auth_verified=True)
            if abort:
                with self.assertRaises(wire.ProtocolError):
                    receiver.tile(packets()[1], auth_verified=True)
            else:
                receiver.tick(9)
            self.assertEqual(receiver.begin(metadata(), auth_verified=True, now=10), "STAGED")

    def test_gap_replay_cache_flush_after_33_commits_allows_old_id(self):
        receiver = wire.EmulatedReceiver()
        for tx in range(1, 34):
            commit(receiver, tx, cover=False, now=tx)
        self.assertEqual(receiver.recent_tx, {f"{33:032x}"})
        self.assertEqual(receiver.begin(metadata(1, cover=False), auth_verified=True, now=34), "STAGED")

    def test_gap_reboot_clears_staged_art_but_also_replay_memory(self):
        before = wire.EmulatedReceiver()
        commit(before, 1)
        before.begin(metadata(2), auth_verified=True, now=1)
        after = wire.EmulatedReceiver()  # simulated reboot, no persistent storage
        self.assertIsNone(after.pending)
        self.assertIsNone(after.committed)
        self.assertEqual(after.view, "PC_HEALTH")
        self.assertEqual(after.begin(metadata(1), auth_verified=True), "STAGED")

    def test_gap_commit_has_no_transaction_or_principal_parameter(self):
        receiver = wire.EmulatedReceiver()
        commit(receiver, 1)
        # Imagine a delayed duplicate of transaction 1's authenticated Commit.
        # The API cannot carry its original transaction identity or principal.
        delayed_old_commit = lambda: receiver.commit(auth_verified=True, now=2)
        stage(receiver, 2, now=1)
        self.assertEqual(delayed_old_commit(), "COMMITTED")
        self.assertEqual(receiver.committed[0]["tx"], f"{2:032x}")


class InterruptedTransferRecoveryTests(unittest.TestCase):
    def test_expiration_boundary_backward_clock_and_return_to_health(self):
        receiver = wire.EmulatedReceiver()
        stage(receiver, now=10)
        self.assertEqual(receiver.commit(auth_verified=True, now=18), "COMMITTED")
        for now in (9, 18.001):
            receiver = wire.EmulatedReceiver()
            commit(receiver, 2)
            stage(receiver, now=10)
            with self.assertRaisesRegex(wire.ProtocolError, "TRANSFER_EXPIRED"):
                receiver.commit(auth_verified=True, now=now)
            self.assertIsNone(receiver.pending)
            self.assertIsNone(receiver.committed)

    def test_modeled_owned_disconnect_discards_pending_and_old_art_then_recovers(self):
        receiver = wire.EmulatedReceiver()
        commit(receiver)
        receiver.begin(metadata(2), auth_verified=True, now=1)
        with self.assertRaisesRegex(wire.ProtocolError, "SIMULATED_OWNED_DISCONNECT"):
            # Required transport-to-state callback modeled explicitly; V0.5 has no transport.
            receiver.fail("SIMULATED_OWNED_DISCONNECT")
        self.assertIsNone(receiver.pending)
        self.assertIsNone(receiver.committed)
        self.assertEqual(receiver.view, "PC_HEALTH")
        self.assertEqual(commit(receiver, 3, now=2), "COMMITTED")

    def test_gap_unauthorized_call_directly_to_v05_revokes_previous_art(self):
        receiver = wire.EmulatedReceiver()
        commit(receiver)
        with self.assertRaisesRegex(wire.ProtocolError, "UNAUTHORIZED"):
            receiver.begin(metadata(2))
        self.assertIsNone(receiver.committed)  # outer unowned-request policy is missing

    def test_gap_json_and_staging_oom_escape_without_clearing_old_state(self):
        for target, name in ((wire.json, "loads"), (wire, "bytearray")):
            with self.subTest(allocation=name):
                receiver = wire.EmulatedReceiver()
                commit(receiver, 1)
                receiver.begin(metadata(2), auth_verified=True, now=1)
                pending, accepted = receiver.pending, receiver.committed
                with patch.object(target, name, side_effect=MemoryError, create=True):
                    with self.assertRaises(MemoryError):
                        receiver.begin(metadata(3), auth_verified=True, now=2)
                self.assertIs(receiver.pending, pending)
                self.assertIs(receiver.committed, accepted)  # GAP, not fail-closed

    def test_gap_commit_copy_oom_leaves_staging_and_previous_art(self):
        receiver = wire.EmulatedReceiver()
        commit(receiver, 1)
        stage(receiver, 2, now=1)
        pending, accepted = receiver.pending, receiver.committed
        with patch.object(wire, "bytes", side_effect=MemoryError, create=True):
            with self.assertRaises(MemoryError):
                receiver.commit(auth_verified=True, now=2)
        self.assertIs(receiver.pending, pending)
        self.assertIs(receiver.committed, accepted)


@dataclass
class MetricsClockFixture:
    """Four-value/unsigned-clock TEST MODEL, not FslessMetrics.cpp execution."""
    values: tuple = (27, 62, 8.5, 68)
    received: bool = False
    last_received_ms: int = 0

    def accept_fixture(self, values, now):
        self.values, self.received, self.last_received_ms = values, True, now

    def stale(self, now):
        return not self.received or ((now - self.last_received_ms) & 0xffffffff) > 6000


class MediaFailureMetricsIsolationTests(unittest.TestCase):
    def test_interleaved_metrics_and_media_failure_preserve_values_and_ttl(self):
        for failure in ("unauthorized", "crc", "expired", "partial", "oom"):
            with self.subTest(failure=failure):
                receiver = wire.EmulatedReceiver()
                meter = MetricsClockFixture()
                receiver.metrics = meter
                self.assertTrue(meter.stale(0))
                commit(receiver)
                meter.accept_fixture((29, 64, 9.0, 69), 1000)
                receiver.begin(metadata(2), auth_verified=True, now=1)
                meter.accept_fixture((31, 66, 9.5, 70), 2000)
                try:
                    if failure == "unauthorized":
                        receiver.commit(now=2)
                    elif failure == "crc":
                        receiver.tile(replace(packets(2)[0], crc32=0), auth_verified=True, now=2)
                    elif failure == "expired":
                        receiver.tick(10)
                    elif failure == "partial":
                        receiver.fail("SIMULATED_PARTIAL_BODY")
                    else:
                        with patch.object(wire, "bytearray", side_effect=MemoryError, create=True):
                            receiver.begin(metadata(3), auth_verified=True, now=2)
                except (wire.ProtocolError, MemoryError):
                    pass
                self.assertIs(receiver.metrics, meter)
                self.assertEqual(meter.values, (31, 66, 9.5, 70))
                self.assertEqual(meter.last_received_ms, 2000)
                self.assertFalse(meter.stale(8000))
                self.assertTrue(meter.stale(8001))
                meter.accept_fixture((33, 68, 10.0, 71), 8002)
                self.assertFalse(meter.stale(8002))
                self.assertEqual(meter.values, (33, 68, 10.0, 71))

    def test_fixture_freshness_wraparound_is_independent_of_media_clock(self):
        receiver = wire.EmulatedReceiver()
        meter = MetricsClockFixture()
        receiver.metrics = meter
        meter.accept_fixture((27, 62, 8.5, 68), 0xfffffff0)
        receiver.tick(100000)
        self.assertFalse(meter.stale((0xfffffff0 + 6000) & 0xffffffff))
        self.assertTrue(meter.stale((0xfffffff0 + 6001) & 0xffffffff))

    def test_metadata_only_clears_cover_and_overlay_returns_after_five_seconds(self):
        receiver = wire.EmulatedReceiver()
        original_metrics = receiver.metrics
        commit(receiver, 1)
        commit(receiver, 2, cover=False, now=1)
        self.assertIsNone(receiver.committed[1])
        self.assertEqual(receiver.view, "NOW_PLAYING")
        receiver.tick(6.2)
        self.assertEqual(receiver.view, "PC_HEALTH")
        self.assertEqual(receiver.metrics, original_metrics)
        for state in ("NO_SESSION", "UNAVAILABLE", "STOPPED", "PAUSED"):
            with self.subTest(state=state):
                fresh = wire.EmulatedReceiver()
                commit(fresh, cover=False, state=state)
                self.assertEqual(fresh.view, "PC_HEALTH")
                self.assertIsNone(fresh.committed[1])


if __name__ == "__main__":
    unittest.main()
