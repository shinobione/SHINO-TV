"""V0.5 PC-ONLY experiment: bounded media/cover wire format and emulated receiver.

This module provides NO SmallTV HTTP endpoint, Digest implementation, firmware,
network request, device write or flashing ability. Auth is represented only by a
test-injected boolean gate to verify reject-before-stage ordering; implementing
actual server-side Digest and nonce/replay protections is a separate firmware gate.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import re
import secrets
import zlib

from media_sessions import MAX_PREVIEW_JPEG, MediaSnapshot, bounded_text

VERSION = 1
COVER_EDGE = 64
COVER_RAW_BYTES = COVER_EDGE * COVER_EDGE * 2  # 8192 RGB565 little-endian
CHUNK_BYTES = 512
CHUNK_COUNT = COVER_RAW_BYTES // CHUNK_BYTES  # 16
MAX_METADATA_BYTES = 512
MAX_TRANSACTION_SECONDS = 8.0
OVERLAY_SECONDS = 5.0
VALID_STATES = frozenset(("PLAYING", "PAUSED", "STOPPED", "NO_SESSION", "UNAVAILABLE"))
HEX_32 = re.compile(r"^[a-f0-9]{32}$")
HEX_64 = re.compile(r"^[a-f0-9]{64}$")
FIELDS = frozenset(("v", "tx", "state", "source", "title", "artist", "album",
                    "position", "duration", "cover_len", "cover_sha256", "track_key"))


class ProtocolError(ValueError):
    pass


def valid_int(value, maximum: int) -> bool:
    return type(value) is int and 0 <= value <= maximum


def track_identity(snapshot: MediaSnapshot) -> str:
    identity = json.dumps([
        bounded_text(snapshot.source, 80), bounded_text(snapshot.title, 60),
        bounded_text(snapshot.artist, 60), bounded_text(snapshot.album, 48)
    ], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(identity).hexdigest()


def jpeg_to_rgb565(jpeg: bytes | None) -> bytes | None:
    """Decode on PC only. A bad/huge JPEG yields coverless media, not fake pixels."""
    if not jpeg or not isinstance(jpeg, bytes) or len(jpeg) > MAX_PREVIEW_JPEG:
        return None
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(BytesIO(jpeg)) as source:
            if source.format != "JPEG":
                return None
            width, height = source.size
            if not (0 < width <= 4096 and 0 < height <= 4096
                    and width * height <= 4_000_000):
                return None
            source.load()
            corrected = ImageOps.exif_transpose(source)
            scaled = ImageOps.fit(corrected.convert("RGB"), (COVER_EDGE, COVER_EDGE),
                                  method=Image.Resampling.LANCZOS)
            pixels = scaled.tobytes()
        result = bytearray(COVER_RAW_BYTES)
        for offset in range(0, len(pixels), 3):
            r, g, b = pixels[offset:offset + 3]
            rgb565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            output = offset // 3 * 2
            result[output] = rgb565 & 0xff
            result[output + 1] = rgb565 >> 8
        return bytes(result)
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return None


def canonical_metadata(value: dict) -> bytes:
    if type(value) is not dict or set(value) != FIELDS:
        raise ProtocolError("BAD_METADATA_FIELDS")
    if value["v"] != VERSION or type(value["v"]) is not int:
        raise ProtocolError("BAD_VERSION")
    if type(value["tx"]) is not str or not HEX_32.fullmatch(value["tx"]):
        raise ProtocolError("BAD_TRANSFER_ID")
    if type(value["track_key"]) is not str or not HEX_64.fullmatch(value["track_key"]):
        raise ProtocolError("BAD_TRACK_KEY")
    if type(value["state"]) is not str or value["state"] not in VALID_STATES:
        raise ProtocolError("BAD_STATE")
    for name, max_chars in (("source", 80), ("title", 60), ("artist", 60), ("album", 48)):
        item = value[name]
        if type(item) is not str or len(item) > max_chars or bounded_text(item, max_chars) != item:
            raise ProtocolError("BAD_TEXT")
    for name in ("position", "duration"):
        if value[name] is not None and not valid_int(value[name], 7 * 86400):
            raise ProtocolError("BAD_DURATION")
    if (value["duration"] is not None and value["position"] is not None
            and value["position"] > value["duration"]):
        raise ProtocolError("BAD_PROGRESS")
    if value["cover_len"] not in (0, COVER_RAW_BYTES) or type(value["cover_len"]) is not int:
        raise ProtocolError("BAD_COVER_SIZE")
    digest = value["cover_sha256"]
    if value["cover_len"] == 0:
        if digest is not None:
            raise ProtocolError("COVERLESS_REQUIRES_NULL_HASH")
    elif type(digest) is not str or not HEX_64.fullmatch(digest):
        raise ProtocolError("BAD_COVER_HASH")
    result = json.dumps(value, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":")).encode("utf-8")
    if len(result) > MAX_METADATA_BYTES:
        raise ProtocolError("METADATA_TOO_LONG")
    return result


@dataclass(frozen=True)
class Packet:
    tx: str
    index: int
    body: bytes
    crc32: int


@dataclass(frozen=True)
class PreparedTransfer:
    metadata: bytes
    packets: tuple[Packet, ...]
    raw_cover: bytes | None


def prepare(snapshot: MediaSnapshot, preview_jpeg: bytes | None,
            *, tx: str | None = None) -> PreparedTransfer:
    raw_cover = jpeg_to_rgb565(preview_jpeg) if preview_jpeg else None
    transfer_id = tx if tx is not None else secrets.token_hex(16)
    position = snapshot.position_seconds
    duration = snapshot.duration_seconds
    if position is not None and duration is not None:
        position = min(position, duration)
    record = {
        "v": VERSION, "tx": transfer_id,
        "state": snapshot.state if snapshot.state in VALID_STATES else "UNAVAILABLE",
        "source": bounded_text(snapshot.source, 80),
        "title": bounded_text(snapshot.title, 60),
        "artist": bounded_text(snapshot.artist, 60),
        "album": bounded_text(snapshot.album, 48),
        "position": position if valid_int(position, 604800) else None,
        "duration": duration if valid_int(duration, 604800) else None,
        "cover_len": len(raw_cover) if raw_cover else 0,
        "cover_sha256": hashlib.sha256(raw_cover).hexdigest() if raw_cover else None,
        "track_key": track_identity(snapshot)
    }
    # If an extreme multi-byte provider tag exceeds the global 512-byte
    # budget, remove optional album/source, then shorten title and artist.
    try:
        metadata = canonical_metadata(record)
    except ProtocolError as exc:
        if str(exc) != "METADATA_TOO_LONG":
            raise
        record["album"] = ""
        record["source"] = ""
        for limit in (40, 28, 16):
            record["title"] = bounded_text(record["title"], limit)
            record["artist"] = bounded_text(record["artist"], limit)
            try:
                metadata = canonical_metadata(record)
                break
            except ProtocolError as next_exc:
                if str(next_exc) != "METADATA_TOO_LONG":
                    raise
        else:
            raise ProtocolError("METADATA_TOO_LONG")
    packets = tuple(
        Packet(transfer_id, i, piece, zlib.crc32(piece) & 0xffffffff)
        for i in range(CHUNK_COUNT)
        for piece in ((raw_cover or b"")[i * CHUNK_BYTES:(i + 1) * CHUNK_BYTES],)
    ) if raw_cover else ()
    return PreparedTransfer(metadata, packets, raw_cover)


class EmulatedReceiver:
    """Strict host state machine, not a physical firmware receiver.

    'auth_verified' stands for an external, currently NONEXISTENT on-device
    endpoint's completed auth/nonce/CSRF verification. It is never a credential,
    cryptographic proof, or a route to real device traffic.
    """
    def __init__(self):
        self.pending: dict | None = None
        self.committed: tuple[dict, bytes | None] | None = None
        self.view = "PC_HEALTH"
        self.until = None
        self.recent_tx: set[str] = set()
        self.last_track = None
        self.metrics = (27, 62, 43, 68)  # independent fixed host fixture

    def fail(self, error: str):
        # Revoke the old music image too: after any invalid new transaction,
        # a caller must never accidentally re-display obsolete cover artwork.
        self.pending = None
        self.committed = None
        self.last_track = None
        self.view = "PC_HEALTH"
        self.until = None
        raise ProtocolError(error)

    def begin(self, payload: bytes, *, auth_verified: bool = False, now: float = 0.0):
        if auth_verified is not True:
            return self.fail("UNAUTHORIZED")
        if type(payload) is not bytes or len(payload) > MAX_METADATA_BYTES:
            return self.fail("OVERSIZE_METADATA")
        try:
            document = json.loads(payload.decode("utf-8"))
            if canonical_metadata(document) != payload:
                return self.fail("NONCANONICAL_METADATA")
        except (ValueError, UnicodeError, TypeError) as exc:
            return self.fail("INVALID_METADATA")
        if document["tx"] in self.recent_tx:
            return self.fail("REPLAYED_TRANSFER")
        # Experimental single-cover peak-RAM policy: release old artwork
        # BEFORE allocating the next 8192-byte staging image. Previously
        # accepted metadata/art must NOT be displayed during this transition.
        # Metrics are independent and continue unchanged.
        self.committed = None
        self.view = "PC_HEALTH"
        self.until = None
        # No new music image is committed until all tiles and hash verify.
        self.pending = {
            "document": document, "buffer": bytearray(document["cover_len"]),
            "next": 0, "started": now
        }
        return "STAGED"

    def tile(self, packet: Packet, *, auth_verified: bool = False, now: float = 0.0):
        if auth_verified is not True:
            return self.fail("UNAUTHORIZED")
        pending = self.pending
        if pending is None:
            return self.fail("NO_TRANSACTION")
        if now - pending["started"] > MAX_TRANSACTION_SECONDS or now < pending["started"]:
            return self.fail("TRANSFER_EXPIRED")
        doc = pending["document"]
        if doc["cover_len"] != COVER_RAW_BYTES:
            return self.fail("COVER_NOT_EXPECTED")
        if type(packet) is not Packet or packet.tx != doc["tx"] or type(packet.index) is not int:
            return self.fail("WRONG_TILE_ID")
        index = packet.index
        if not 0 <= index < CHUNK_COUNT:
            return self.fail("TILE_INDEX_BOUNDS")
        if type(packet.body) is not bytes or len(packet.body) != CHUNK_BYTES:
            return self.fail("TILE_LENGTH")
        if type(packet.crc32) is not int or packet.crc32 != (zlib.crc32(packet.body) & 0xffffffff):
            return self.fail("TILE_CRC")
        start = index * CHUNK_BYTES
        if index < pending["next"]:
            return "DUPLICATE" if pending["buffer"][start:start + CHUNK_BYTES] == packet.body else self.fail("CONFLICTING_RETRY")
        if index != pending["next"]:
            return self.fail("OUT_OF_ORDER")
        pending["buffer"][start:start + CHUNK_BYTES] = packet.body
        pending["next"] += 1
        return "STAGED"

    def commit(self, *, auth_verified: bool = False, now: float = 0.0):
        if auth_verified is not True:
            return self.fail("UNAUTHORIZED")
        pending = self.pending
        if pending is None:
            return self.fail("NO_TRANSACTION")
        if now < pending["started"] or now - pending["started"] > MAX_TRANSACTION_SECONDS:
            return self.fail("TRANSFER_EXPIRED")
        document = pending["document"]
        raw = bytes(pending["buffer"])
        if document["cover_len"]:
            if pending["next"] != CHUNK_COUNT:
                return self.fail("INCOMPLETE")
            if hashlib.sha256(raw).hexdigest() != document["cover_sha256"]:
                return self.fail("FINAL_SHA_MISMATCH")
        self.pending = None
        self.committed = (document, raw if raw else None)
        self.recent_tx.add(document["tx"])
        # Bound replay cache size in this host emulation. A future firmware
        # must select durable/short-lived nonce semantics separately.
        if len(self.recent_tx) > 32:
            self.recent_tx = {document["tx"]}
        is_new_playing = (document["state"] == "PLAYING" and
                          bool(document["title"]) and
                          document["track_key"] != self.last_track)
        self.last_track = document["track_key"]
        if is_new_playing:
            self.view = "NOW_PLAYING"
            self.until = now + OVERLAY_SECONDS
        elif document["state"] in ("UNAVAILABLE", "NO_SESSION", "STOPPED"):
            self.view = "PC_HEALTH"
            self.until = None
        return "COMMITTED"

    def tick(self, now: float):
        if self.pending and (now < self.pending["started"] or
                             now - self.pending["started"] > MAX_TRANSACTION_SECONDS):
            self.pending = None
            self.committed = None
            self.last_track = None
            self.view = "PC_HEALTH"
            self.until = None
        if self.until is not None and now >= self.until:
            self.view = "PC_HEALTH"
            self.until = None
        return self.view
