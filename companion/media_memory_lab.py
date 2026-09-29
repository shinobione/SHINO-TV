"""Host-only V0.6 media allocation laboratory.

This module is deliberately independent from ``media_wire_v1`` and has no
socket, device address, firmware route, credential, OTA or filesystem support.
Its allocator counts receiver-side logical storage.  CPython measurements are
reported separately and are never ESP8266 heap evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import platform
import re
import sys
import time
import tracemalloc
import zlib


CHUNK_BYTES = 512
MAX_METADATA_BYTES = 512
TRANSFER_SECONDS = 8.0
OVERLAY_SECONDS = 5.0
IMAGE_BYTES = {0: 0, 32: 32 * 32 * 2, 48: 48 * 48 * 2, 64: 64 * 64 * 2}
TX = re.compile(r"^[a-f0-9]{32}$")
SHA = re.compile(r"^[a-f0-9]{64}$")


class LabError(ValueError):
    pass


@dataclass(frozen=True)
class Strategy:
    name: str
    copy_on_commit: bool
    revoke_old_before_staging: bool


CURRENT_COPY = Strategy("A_CURRENT_COPY", True, False)
OWNERSHIP = Strategy("B_OWNERSHIP_TRANSFER", False, False)
REVOKE_FIRST = Strategy("C_REVOKE_OLD_FIRST", False, True)
STRATEGIES = (CURRENT_COPY, OWNERSHIP, REVOKE_FIRST)


@dataclass
class Allocation:
    identity: int
    phase: str
    size: int
    image: bool = True


class LogicalAllocator:
    """Deterministic storage ledger; not a native allocator simulation."""

    def __init__(self, capacity: int | None = None):
        self.capacity = capacity
        self.live: dict[int, Allocation] = {}
        self.next_identity = 1
        self.peak_live = 0
        self.peak_image_live = 0
        self.cumulative = 0
        self.allocations = 0
        self.fail_next_phases: set[str] = set()

    @property
    def live_bytes(self):
        return sum(item.size for item in self.live.values())

    @property
    def image_live_bytes(self):
        return sum(item.size for item in self.live.values() if item.image)

    def fail_next(self, phase: str):
        self.fail_next_phases.add(phase)

    def allocate(self, phase: str, size: int, *, image: bool = True):
        if phase in self.fail_next_phases:
            self.fail_next_phases.remove(phase)
            raise MemoryError(f"injected {phase}")
        if size < 0 or (self.capacity is not None and self.live_bytes + size > self.capacity):
            raise MemoryError(f"logical capacity exceeded in {phase}")
        token = Allocation(self.next_identity, phase, size, image)
        self.next_identity += 1
        self.live[token.identity] = token
        self.cumulative += size
        self.allocations += 1
        self.peak_live = max(self.peak_live, self.live_bytes)
        self.peak_image_live = max(self.peak_image_live, self.image_live_bytes)
        return token

    def release(self, token: Allocation | None):
        if token is not None:
            self.live.pop(token.identity, None)

    def rename(self, token: Allocation, phase: str):
        token.phase = phase


@dataclass
class Pending:
    tx: str
    metadata: bytes
    expected_size: int
    expected_sha256: str | None
    started: float
    staging_token: Allocation | None
    staging: bytearray
    next_index: int = 0


class MemoryLabReceiver:
    """Improved experimental ownership model, not the V0.5 receiver.

    Calls represent an already authorized transaction.  This class provides no
    authentication and must never be treated as an ingress implementation.
    """

    def __init__(self, strategy: Strategy, allocator: LogicalAllocator | None = None):
        self.strategy = strategy
        self.allocator = allocator or LogicalAllocator()
        self.pending: Pending | None = None
        self.committed_token: Allocation | None = None
        self.committed_cover: bytes | bytearray | None = None
        self.committed_metadata: bytes | None = None
        self.terminal_tx: set[str] = set()
        self.view = "PC_HEALTH"
        self.overlay_until: float | None = None

    def _revoke_committed(self):
        self.allocator.release(self.committed_token)
        self.committed_token = None
        self.committed_cover = None
        self.committed_metadata = None
        self.view = "PC_HEALTH"
        self.overlay_until = None

    def _owned_failure(self, code: str, tx: str):
        if self.pending is not None:
            self.allocator.release(self.pending.staging_token)
        self.pending = None
        self._revoke_committed()
        self.terminal_tx.add(tx)
        raise LabError(code)

    def begin(self, tx: str, metadata: bytes, cover_size: int,
              cover_sha256: str | None, *, now: float):
        if type(tx) is not str or not TX.fullmatch(tx):
            raise LabError("BAD_TX")
        if tx in self.terminal_tx:
            raise LabError("REPLAY")
        if self.pending is not None:
            raise LabError("BUSY")
        if type(metadata) is not bytes or not 1 <= len(metadata) <= MAX_METADATA_BYTES:
            raise LabError("BAD_METADATA")
        try:
            decoded = metadata.decode("utf-8")
        except UnicodeError as exc:
            raise LabError("BAD_METADATA") from exc
        if "\x00" in decoded:
            raise LabError("BAD_METADATA")
        try:
            document = json.loads(decoded)
        except ValueError as exc:
            raise LabError("BAD_METADATA") from exc
        if type(document) is not dict or type(document.get("title")) is not str:
            raise LabError("BAD_METADATA")
        if cover_size not in IMAGE_BYTES.values():
            raise LabError("BAD_COVER_SIZE")
        if cover_size == 0:
            if cover_sha256 is not None:
                raise LabError("BAD_COVER_HASH")
        elif type(cover_sha256) is not str or not SHA.fullmatch(cover_sha256):
            raise LabError("BAD_COVER_HASH")

        if self.strategy.revoke_old_before_staging:
            self._revoke_committed()
        token = None
        try:
            if cover_size:
                token = self.allocator.allocate("staging", cover_size)
                staging = bytearray(cover_size)
            else:
                staging = bytearray()
        except MemoryError:
            self.allocator.release(token)
            self._revoke_committed()
            self.terminal_tx.add(tx)
            raise
        try:
            # The copy and Pending object are also allocation points. If either
            # fails, the just-created cover storage must not be leaked.
            copied_metadata = memoryview(metadata).tobytes()
            self.pending = Pending(tx, copied_metadata, cover_size,
                                   cover_sha256, now, token, staging)
        except MemoryError:
            self.allocator.release(token)
            self._revoke_committed()
            self.terminal_tx.add(tx)
            raise
        return "STAGED"

    def tile(self, tx: str, index: int, body: bytes, crc32: int, *, now: float):
        pending = self.pending
        if pending is None or tx != pending.tx:
            raise LabError("NO_MATCHING_TRANSACTION")
        if now < pending.started or now - pending.started > TRANSFER_SECONDS:
            return self._owned_failure("EXPIRED", tx)
        if pending.expected_size == 0:
            return self._owned_failure("COVER_NOT_EXPECTED", tx)
        count = pending.expected_size // CHUNK_BYTES
        if type(index) is not int or not 0 <= index < count:
            return self._owned_failure("BAD_INDEX", tx)
        if type(body) is not bytes or len(body) != CHUNK_BYTES:
            return self._owned_failure("BAD_CHUNK", tx)
        if type(crc32) is not int or crc32 != (zlib.crc32(body) & 0xffffffff):
            return self._owned_failure("BAD_CRC", tx)
        start = index * CHUNK_BYTES
        if index < pending.next_index:
            if pending.staging[start:start + CHUNK_BYTES] == body:
                return "DUPLICATE"
            return self._owned_failure("CONFLICT", tx)
        if index != pending.next_index:
            return self._owned_failure("OUT_OF_ORDER", tx)
        pending.staging[start:start + CHUNK_BYTES] = body
        pending.next_index += 1
        return "STAGED"

    def commit(self, tx: str, *, now: float):
        pending = self.pending
        if pending is None or tx != pending.tx:
            raise LabError("STALE_COMMIT")
        if now < pending.started or now - pending.started > TRANSFER_SECONDS:
            return self._owned_failure("EXPIRED", tx)
        expected_chunks = pending.expected_size // CHUNK_BYTES
        commit_token = None
        candidate: bytes | bytearray | None = None
        try:
            if self.strategy.copy_on_commit and pending.expected_size:
                commit_token = self.allocator.allocate("commit_copy", pending.expected_size)
                candidate = bytes(memoryview(pending.staging))
            elif pending.expected_size:
                candidate = pending.staging
            if pending.next_index != expected_chunks:
                self.allocator.release(commit_token)
                return self._owned_failure("INCOMPLETE", tx)
            if candidate is not None and hashlib.sha256(candidate).hexdigest() != pending.expected_sha256:
                self.allocator.release(commit_token)
                return self._owned_failure("FINAL_SHA_MISMATCH", tx)
        except MemoryError:
            self.allocator.release(commit_token)
            self.allocator.release(pending.staging_token)
            self.pending = None
            self._revoke_committed()
            self.terminal_tx.add(tx)
            raise

        self._revoke_committed()
        if self.strategy.copy_on_commit:
            self.allocator.release(pending.staging_token)
            if commit_token is not None:
                self.allocator.rename(commit_token, "committed")
            self.committed_token = commit_token
        else:
            if pending.staging_token is not None:
                self.allocator.rename(pending.staging_token, "committed")
            self.committed_token = pending.staging_token
        self.committed_cover = candidate
        self.committed_metadata = pending.metadata
        self.pending = None
        self.terminal_tx.add(tx)
        self.view = "NOW_PLAYING"
        self.overlay_until = now + OVERLAY_SECONDS
        return "COMMITTED"

    def abort(self, tx: str, code: str = "INTERRUPTED"):
        if self.pending is None or self.pending.tx != tx:
            raise LabError("NO_MATCHING_TRANSACTION")
        return self._owned_failure(code, tx)

    def tick(self, now: float):
        if self.pending and (now < self.pending.started or
                             now - self.pending.started > TRANSFER_SECONDS):
            try:
                self._owned_failure("EXPIRED", self.pending.tx)
            except LabError:
                pass
        if self.overlay_until is not None and now >= self.overlay_until:
            self.view = "PC_HEALTH"
            self.overlay_until = None
        return self.view


@dataclass
class MetricsFixture:
    values: tuple[float, float, float, float] = (27.0, 62.0, 8.5, 68.0)
    received: bool = False
    last_received_ms: int = 0

    def accept(self, values, now_ms: int):
        self.values = values
        self.received = True
        self.last_received_ms = now_ms & 0xffffffff

    def stale(self, now_ms: int):
        return (not self.received or
                ((now_ms - self.last_received_ms) & 0xffffffff) > 6000)


def synthetic_cover(size: int, seed: int):
    return bytes(((offset + seed) & 0xff) for offset in range(size))


def transfer(receiver: MemoryLabReceiver, edge: int, sequence: int, now: float,
             metrics: MetricsFixture | None = None):
    size = IMAGE_BYTES[edge]
    raw = synthetic_cover(size, sequence)
    tx = f"{sequence:032x}"
    metadata = f'{{"title":"synthetic-{sequence}"}}'.encode()
    receiver.begin(tx, metadata, size,
                   hashlib.sha256(raw).hexdigest() if raw else None, now=now)
    for index in range(size // CHUNK_BYTES):
        if metrics is not None and index == (size // CHUNK_BYTES) // 2:
            metrics.accept((sequence % 101, (sequence * 3) % 101,
                            8.0 + (sequence % 8), 60.0 + (sequence % 20)),
                           sequence * 1000)
        chunk = raw[index * CHUNK_BYTES:(index + 1) * CHUNK_BYTES]
        receiver.tile(tx, index, chunk, zlib.crc32(chunk) & 0xffffffff, now=now + 0.1)
    if metrics is not None and size == 0:
        metrics.accept((sequence % 101, (sequence * 3) % 101,
                        8.0 + (sequence % 8), 60.0 + (sequence % 20)),
                       sequence * 1000)
    receiver.commit(tx, now=now + 0.2)


def deterministic_stress(strategy: Strategy, edge: int, cycles: int = 250):
    receiver = MemoryLabReceiver(strategy)
    metrics = MetricsFixture()
    for sequence in range(1, cycles + 1):
        now = float(sequence * 10)
        transfer(receiver, edge, sequence, now, metrics)
        receiver.tick(now + OVERLAY_SECONDS)
    return {
        "strategy": strategy.name, "edge": edge, "cycles": cycles,
        "image_bytes": IMAGE_BYTES[edge],
        "peak_receiver_image_bytes": receiver.allocator.peak_image_live,
        "cumulative_receiver_image_bytes": receiver.allocator.cumulative,
        "logical_allocations": receiver.allocator.allocations,
        "final_live_image_bytes": receiver.allocator.image_live_bytes,
        "terminal_ids": len(receiver.terminal_tx),
        "metrics_values": metrics.values,
        "metrics_stale_at_exact_boundary": metrics.stale(cycles * 1000 + 6000),
        "metrics_stale_after_boundary": metrics.stale(cycles * 1000 + 6001),
    }


def cpython_v05_probe(cycles: int = 250):
    """Measure this CPython process only; payloads are prepared before tracing."""
    import media_wire_v1 as wire

    raw = synthetic_cover(wire.COVER_RAW_BYTES, 7)
    fixtures = []
    for sequence in range(1, cycles + 1):
        tx = f"{sequence:032x}"
        document = {
            "v": 1, "tx": tx, "state": "PLAYING", "source": "SYNTHETIC",
            "title": f"track-{sequence}", "artist": "lab", "album": "",
            "position": 1, "duration": 60, "cover_len": len(raw),
            "cover_sha256": hashlib.sha256(raw).hexdigest(),
            "track_key": f"{sequence:064x}",
        }
        metadata = wire.canonical_metadata(document)
        packets = tuple(wire.Packet(tx, index,
                            raw[index * 512:(index + 1) * 512],
                            zlib.crc32(raw[index * 512:(index + 1) * 512]) & 0xffffffff)
                        for index in range(16))
        fixtures.append((metadata, packets))
    tracemalloc.start()
    started = time.perf_counter()
    receiver = wire.EmulatedReceiver()
    for sequence, (metadata, packets) in enumerate(fixtures, 1):
        receiver.begin(metadata, auth_verified=True, now=sequence * 10.0)
        for packet in packets:
            receiver.tile(packet, auth_verified=True, now=sequence * 10.0 + 0.1)
        receiver.commit(auth_verified=True, now=sequence * 10.0 + 0.2)
    elapsed = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "scope": "CPython tracemalloc; prebuilt synthetic sender payloads excluded",
        "python": platform.python_version(), "cycles": cycles,
        "elapsed_seconds": round(elapsed, 6),
        "traced_current_bytes": current, "traced_peak_bytes": peak,
        "sys_getsizeof_bytearray_8192": sys.getsizeof(bytearray(8192)),
        "sys_getsizeof_bytes_8192": sys.getsizeof(bytes(8192)),
    }


def report(cycles: int = 250):
    return {
        "warning": "HOST CPython and logical receiver model only; no ESP8266 evidence",
        "logical_stress": [deterministic_stress(strategy, edge, cycles)
                           for strategy in STRATEGIES for edge in (0, 32, 48, 64)],
        "cpython_v05": cpython_v05_probe(cycles),
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2, sort_keys=True))
