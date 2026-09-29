"""V0.7 wire-v2 HOST REFERENCE ONLY. No socket, firmware route or authentication.

Authority is a test-injected result of a hypothetical external verifier. It is
not a credential, signature, Digest implementation or production auth gate.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
import struct
import zlib


MAGIC = b"STV7"
VERSION = 2
BEGIN, TILE, COMMIT, ABORT = 1, 2, 3, 4
HEADER = struct.Struct(">4sBBHQ16sHHI")  # 40 bytes, network byte order
TILE_BYTES = 512
MAX_METADATA = 512
DEADLINE = 8.0
OVERLAY = 5.0
SIZES = {0: (0, 0), 32: (2048, 4), 48: (4608, 9)}
STATES = {"PLAYING", "PAUSED", "STOPPED", "NO_SESSION", "UNAVAILABLE"}
FIELDS = {"v", "tx", "state", "source", "title", "artist", "album",
          "position", "duration", "track_key", "width", "height", "pixel_format",
          "cover_len", "tile_count", "cover_sha256"}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class WireError(ValueError):
    pass


def transaction(epoch: int, sequence: int) -> bytes:
    if type(epoch) is not int or type(sequence) is not int or not 0 < epoch < 2**64 or not 0 < sequence < 2**64:
        raise WireError("BAD_TRANSACTION")
    return struct.pack(">QQ", epoch, sequence)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WireError("DUPLICATE_FIELD")
        result[key] = value
    return result


def metadata(value: dict) -> bytes:
    """Validate and serialize exact canonical UTF-8 JSON, never V0.5's schema."""
    if type(value) is not dict or set(value) != FIELDS or type(value["v"]) is not int or value["v"] != VERSION:
        raise WireError("BAD_SCHEMA")
    tx = value["tx"]
    if type(tx) is not str or len(tx) != 32 or not re.fullmatch(r"[0-9a-f]{32}", tx) or int(tx, 16) == 0:
        raise WireError("BAD_TX")
    if type(value["track_key"]) is not str or not HEX64.fullmatch(value["track_key"]):
        raise WireError("BAD_TRACK_KEY")
    if type(value["state"]) is not str or value["state"] not in STATES:
        raise WireError("BAD_STATE")
    for name, limit in (("source", 80), ("title", 60), ("artist", 60), ("album", 48)):
        item = value[name]
        if type(item) is not str or len(item) > limit or any(ord(c) < 32 or 0x7f <= ord(c) <= 0x9f or 0xd800 <= ord(c) <= 0xdfff for c in item):
            raise WireError("BAD_TEXT")
    for name in ("position", "duration"):
        item = value[name]
        if item is not None and (type(item) is not int or not 0 <= item <= 604800):
            raise WireError("BAD_PROGRESS")
    if value["position"] is not None and value["duration"] is not None and value["position"] > value["duration"]:
        raise WireError("BAD_PROGRESS")
    width, height = value["width"], value["height"]
    if type(width) is not int or type(height) is not int or width not in SIZES or height != width:
        raise WireError("BAD_DIMENSIONS")
    size, count = SIZES[width]
    if type(value["cover_len"]) is not int or value["cover_len"] != size or type(value["tile_count"]) is not int or value["tile_count"] != count:
        raise WireError("BAD_SIZE")
    if value["pixel_format"] != ("RGB565LE" if size else "NONE") or type(value["pixel_format"]) is not str:
        raise WireError("BAD_PIXEL_FORMAT")
    digest = value["cover_sha256"]
    if (digest is not None if not size else type(digest) is not str or not HEX64.fullmatch(digest)):
        raise WireError("BAD_SHA")
    try:
        data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError) as exc:
        raise WireError("BAD_METADATA") from exc
    if not 1 <= len(data) <= MAX_METADATA:
        raise WireError("METADATA_LENGTH")
    return data


def parse_metadata(data: bytes) -> dict:
    if type(data) is not bytes or not 1 <= len(data) <= MAX_METADATA:
        raise WireError("METADATA_LENGTH")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique)
        if metadata(value) != data:
            raise WireError("NONCANONICAL")
    except (UnicodeError, ValueError, TypeError) as exc:
        if isinstance(exc, WireError):
            raise
        raise WireError("BAD_METADATA") from exc
    return value


def encode(op: int, tx: bytes, payload: bytes = b"", *, index: int = 0) -> tuple[bytes, bytes]:
    if type(tx) is not bytes or len(tx) != 16 or type(payload) is not bytes or type(index) is not int or not 0 <= index < 2**16:
        raise WireError("BAD_ENVELOPE")
    epoch, sequence = struct.unpack(">QQ", tx)
    transaction(epoch, sequence)
    if op not in (BEGIN, TILE, COMMIT, ABORT) or len(payload) > MAX_METADATA:
        raise WireError("BAD_ENVELOPE")
    return HEADER.pack(MAGIC, VERSION, op, 0, epoch, tx, index, len(payload), zlib.crc32(payload) & 0xffffffff), payload


@dataclass(frozen=True)
class Authority:
    """Already-verified model input; no crypto or HTTP parser is supplied here."""
    principal: str
    epoch: int
    op: int
    tx: bytes


@dataclass
class Pending:
    principal: str
    tx: bytes
    document: dict
    buffer: bytearray | None
    started: float
    next_index: int = 0


class HostReceiver:
    def __init__(self, epoch: int):
        transaction(epoch, 1)
        self.epoch = epoch
        self.highest_sequence = 0  # O(1) terminal/replay state for this epoch
        self.pending: Pending | None = None
        self.committed_cover: bytearray | None = None
        self.committed_metadata: dict | None = None
        self.last_track: str | None = None
        self.view = "PC_HEALTH"
        self.overlay_until: float | None = None

    def _terminal(self, code: str):
        self.pending = None
        self.committed_cover = None
        self.committed_metadata = None
        self.last_track = None
        self.view = "PC_HEALTH"
        self.overlay_until = None
        raise WireError(code)

    def tick(self, now: float) -> str:
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            raise WireError("BAD_CLOCK")
        if self.pending is not None and (now < self.pending.started or now - self.pending.started > DEADLINE):
            self._terminal("EXPIRED")
        if self.overlay_until is not None and now >= self.overlay_until:
            self.view = "PC_HEALTH"
            self.overlay_until = None
        return self.view

    def receive(self, header: bytes, payload: bytes, authority: Authority | None, *, now: float):
        # A real ingress must enforce framing and authentication before body
        # allocation. This method receives pre-separated host test bytes only.
        if type(header) is not bytes or len(header) != HEADER.size:
            raise WireError("BAD_HEADER")
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            raise WireError("BAD_CLOCK")
        magic, version, op, flags, epoch, tx, index, length, crc = HEADER.unpack(header)
        if (magic, version, flags) != (MAGIC, VERSION, 0) or op not in (BEGIN, TILE, COMMIT, ABORT) or epoch != self.epoch or tx[:8] != struct.pack(">Q", epoch) or int.from_bytes(tx[8:], "big") == 0:
            raise WireError("BAD_HEADER")
        if (type(authority) is not Authority or not authority.principal or
                (authority.epoch, authority.op, authority.tx) != (epoch, op, tx)):
            raise WireError("UNAUTHORIZED")
        pending = self.pending
        owned = pending is not None and pending.tx == tx and pending.principal == authority.principal
        if op == BEGIN:
            sequence = int.from_bytes(tx[8:], "big")
            if pending is not None:
                raise WireError("BUSY")
            if sequence <= self.highest_sequence:
                raise WireError("REPLAY")
        elif not owned:
            raise WireError("NO_MATCHING_TRANSACTION")
        if owned and (now < pending.started or now - pending.started > DEADLINE):
            self._terminal("EXPIRED")
        expected_length = 512 if op == TILE else 0 if op in (COMMIT, ABORT) else length
        if (index != 0 if op != TILE else index >= (pending.document["tile_count"] if owned else 0)) or length != expected_length or (op == BEGIN and not 1 <= length <= MAX_METADATA):
            if owned:
                self._terminal("BAD_ENVELOPE")
            raise WireError("BAD_ENVELOPE")
        if type(payload) is not bytes or len(payload) != length or (zlib.crc32(payload) & 0xffffffff) != crc:
            if owned:
                self._terminal("BAD_BODY")
            raise WireError("BAD_BODY")
        if op == BEGIN:
            try:
                document = parse_metadata(payload)
            except MemoryError as exc:
                # The transaction has not crossed the accepted Begin boundary.
                raise WireError("ALLOCATION_FAILED") from exc
            if document["tx"] != tx.hex():
                raise WireError("TX_MISMATCH")
            # This accepted authorized boundary deliberately forfeits image rollback.
            self.highest_sequence = sequence
            self.committed_cover = None
            self.committed_metadata = None
            self.view = "PC_HEALTH"
            try:
                buffer = bytearray(document["cover_len"]) if document["cover_len"] else None
                self.pending = Pending(authority.principal, tx, document, buffer, now)
            except MemoryError:
                self._terminal("ALLOCATION_FAILED")
            return "STAGED"
        if op == ABORT:
            self._terminal("INTERRUPTED")
        if op == TILE:
            if pending.buffer is None:
                self._terminal("COVER_NOT_EXPECTED")
            start = index * TILE_BYTES
            if index < pending.next_index:
                if memoryview(pending.buffer)[start:start + TILE_BYTES] == payload:
                    return "DUPLICATE"
                self._terminal("CONFLICT")
            if index != pending.next_index:
                self._terminal("OUT_OF_ORDER")
            pending.buffer[start:start + TILE_BYTES] = payload
            pending.next_index += 1
            return "STAGED"
        if pending.next_index != pending.document["tile_count"]:
            self._terminal("INCOMPLETE")
        try:
            if pending.buffer is not None and hashlib.sha256(memoryview(pending.buffer)).hexdigest() != pending.document["cover_sha256"]:
                self._terminal("FINAL_SHA_MISMATCH")
        except MemoryError:
            self._terminal("ALLOCATION_FAILED")
        # Move the single staging bytearray to display ownership; never bytes(buffer).
        self.committed_cover = pending.buffer
        self.committed_metadata = pending.document
        self.pending = None
        document = self.committed_metadata
        new_playing = document["state"] == "PLAYING" and bool(document["title"]) and document["track_key"] != self.last_track
        self.last_track = document["track_key"]
        if new_playing:
            self.view = "NOW_PLAYING"
            self.overlay_until = now + OVERLAY
        elif document["state"] in ("STOPPED", "NO_SESSION", "UNAVAILABLE"):
            self.view = "PC_HEALTH"
            self.overlay_until = None
        elif self.overlay_until is not None and now < self.overlay_until:
            self.view = "NOW_PLAYING"
        return "COMMITTED"
