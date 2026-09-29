"""Isolated V0.7 HTTP ingress POLICY MODEL, not a device server or verifier.

Synthetic Decision values stand for a separately reviewed, standards-based
cryptographic verifier. This module opens no socket and accesses no secrets.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import re
import struct
import zlib


MAX_REQUEST_LINE = 128
MAX_HEADER_LINE = 256
MAX_HEADER_BYTES = 1024
MAX_FIELDS = 12
MAX_BODY = 552
READ_QUANTUM = 64
REQUEST_MS = 2000  # synthetic candidate limit; no native timing claim
TRANSACTION_MS = 8000
MEDIA_PREFIX = "/api/v2/bridge/media/"
OPERATIONS = {"begin": 1, "tile": 2, "commit": 3, "abort": 4}
BODY_HEADER = struct.Struct(">4sBBHQ16sHHI")
TARGET = re.compile(rb"/api/v2/bridge/media/(begin|tile|commit|abort)/([0-9a-f]{32})\Z")
DIGEST = re.compile(rb"sha-256=:([A-Za-z0-9+/]{43}=):\Z")
ALLOWED = {b"host", b"content-type", b"content-length", b"content-digest",
           b"signature-input", b"signature", b"connection"}


class IngressError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class ByteSource:
    """Deterministic finite byte source; it is not TCP or ESP Wi-Fi."""
    def __init__(self, data: bytes, *, time_ms=0, chunk=64, delay_ms=0):
        self.data = data
        self.position = 0
        self.time_ms = time_ms
        self.chunk = chunk
        self.delay_ms = delay_ms
        self.read_calls = 0
        self.bytes_read = 0

    def read(self, maximum: int, deadline_ms: int) -> bytes:
        self.read_calls += 1
        self.time_ms += self.delay_ms
        if self.time_ms > deadline_ms:
            raise IngressError("ABSOLUTE_TIMEOUT")
        amount = min(maximum, self.chunk, len(self.data) - self.position)
        part = self.data[self.position:self.position + amount]
        self.position += amount
        self.bytes_read += amount
        return part

    @property
    def remaining(self):
        return len(self.data) - self.position


@dataclass(frozen=True)
class Decision:
    """Test-injected result only. Construction is not authentication."""
    principal: str
    method: str
    target: str
    host: str
    epoch: int
    operation: int
    transaction: bytes
    body_digest: bytes


@dataclass
class PendingFixture:
    principal: str | None = None
    epoch: int | None = None
    transaction: bytes | None = None
    started_ms: int | None = None
    art: bytes | None = None
    terminal_count: int = 0
    highest_sequence: int = 0

    def owns(self, decision: Decision) -> bool:
        return (self.principal, self.epoch, self.transaction) == (
            decision.principal, decision.epoch, decision.transaction)

    def cancel_owned(self, decision: Decision):
        if self.owns(decision):
            self.principal = self.epoch = self.transaction = self.started_ms = self.art = None
            self.terminal_count += 1


@dataclass(frozen=True)
class ValidatedRecord:
    principal: str
    operation: int
    transaction: bytes
    record_header: bytes
    payload: bytes


def _exact(source: ByteSource, amount: int, deadline: int) -> bytes:
    out = bytearray()
    while len(out) < amount:
        part = source.read(min(READ_QUANTUM, amount - len(out)), deadline)
        if not part:
            raise IngressError("PARTIAL_OR_FIN")
        out.extend(part)
    return bytes(out)


def _head(source: ByteSource, deadline: int):
    # One fixed bounded workspace; rejected clients never read a body byte.
    out = bytearray()
    while not out.endswith(b"\r\n\r\n"):
        if len(out) >= MAX_HEADER_BYTES:
            raise IngressError("HEADER_TOO_LONG")
        byte = source.read(1, deadline)
        if not byte:
            raise IngressError("PARTIAL_HEADER")
        out.extend(byte)
    lines = bytes(out[:-4]).split(b"\r\n")
    if not lines or len(lines[0]) > MAX_REQUEST_LINE or any(len(line) > MAX_HEADER_LINE for line in lines[1:]):
        raise IngressError("LINE_TOO_LONG")
    if len(lines) - 1 > MAX_FIELDS:
        raise IngressError("TOO_MANY_FIELDS")
    if any(not line or line[:1] in (b" ", b"\t") or b"\x00" in line for line in lines):
        raise IngressError("BAD_HEADER_SYNTAX")
    parts = lines[0].split(b" ")
    if len(parts) != 3 or parts[0] != b"POST" or parts[2] != b"HTTP/1.1":
        raise IngressError("BAD_REQUEST_LINE")
    match = TARGET.fullmatch(parts[1])
    if not match:
        raise IngressError("BAD_TARGET")
    fields = {}
    for line in lines[1:]:
        if b":" not in line:
            raise IngressError("BAD_HEADER_SYNTAX")
        name, value = line.split(b":", 1)
        if (not name or not re.fullmatch(rb"[A-Za-z-]+", name) or
                name.lower() not in ALLOWED or name.lower() in fields or
                not value.startswith(b" ") or value.startswith(b"  ") or
                value[1:] != value[1:].strip(b" \t")):
            raise IngressError("BAD_OR_DUPLICATE_FIELD")
        fields[name.lower()] = value[1:]
    if set(fields) != ALLOWED or fields[b"connection"] != b"close" or fields[b"content-type"] != b"application/vnd.shino-tv.media-wire-v2":
        raise IngressError("BAD_FIELDS")
    raw_length = fields[b"content-length"]
    if not raw_length or len(raw_length) > 3 or not raw_length.isascii() or not re.fullmatch(rb"[1-9][0-9]*", raw_length):
        raise IngressError("BAD_CONTENT_LENGTH")
    length = int(raw_length)
    if not 40 <= length <= MAX_BODY:
        raise IngressError("BAD_CONTENT_LENGTH")
    digest_match = DIGEST.fullmatch(fields[b"content-digest"])
    if digest_match is None or not fields[b"signature-input"] or not fields[b"signature"]:
        raise IngressError("BAD_DIGEST_OR_PROOF_FIELDS")
    try:
        digest = base64.b64decode(digest_match.group(1), validate=True)
    except ValueError as exc:
        raise IngressError("BAD_DIGEST_OR_PROOF_FIELDS") from exc
    if len(digest) != 32:
        raise IngressError("BAD_DIGEST_OR_PROOF_FIELDS")
    operation = OPERATIONS[match.group(1).decode("ascii")]
    transaction = bytes.fromhex(match.group(2).decode("ascii"))
    epoch = int.from_bytes(transaction[:8], "big")
    if epoch == 0 or int.from_bytes(transaction[8:], "big") == 0:
        raise IngressError("BAD_TRANSACTION")
    return parts[1].decode("ascii"), fields, length, digest, operation, transaction, epoch


def inspect(head_source: ByteSource, body_source: ByteSource, verifier, pending: PendingFixture,
            *, expected_host="unit.invalid", current_epoch=7) -> ValidatedRecord:
    """Return a validated record; deliberately never dispatch to media/firmware."""
    request_started = head_source.time_ms
    header_deadline = request_started + REQUEST_MS
    target, fields, content_length, digest, operation, transaction, epoch = _head(head_source, header_deadline)
    if fields[b"host"] != expected_host.encode("ascii"):
        raise IngressError("WRONG_HOST")
    # The external verifier MUST independently authenticate actual method,
    # target, host, declaration, epoch, principal and covered Content-Digest.
    # This callback is a test double here; no signature parsing occurs.
    decision = verifier("POST", target, expected_host, operation, transaction, epoch, digest, fields)
    if (type(decision) is not Decision or not decision.principal or
            (decision.method, decision.target, decision.host, decision.epoch,
             decision.operation, decision.transaction, decision.body_digest) !=
            ("POST", target, expected_host, epoch, operation, transaction, digest)):
        raise IngressError("DENIED")
    if epoch != current_epoch:
        raise IngressError("STALE_EPOCH")
    if operation == 1:
        if pending.transaction is not None:
            raise IngressError("BUSY")
        if int.from_bytes(transaction[8:], "big") <= pending.highest_sequence:
            raise IngressError("REPLAY")
    elif not pending.owns(decision):
        raise IngressError("WRONG_OWNER_OR_TRANSACTION")
    deadline = header_deadline
    if pending.owns(decision):
        deadline = min(deadline, pending.started_ms + TRANSACTION_MS)
    try:
        fixed = _exact(body_source, BODY_HEADER.size, deadline)
        magic, version, body_op, flags, body_epoch, body_tx, index, payload_len, crc = BODY_HEADER.unpack(fixed)
        if (magic, version, flags, body_op, body_epoch, body_tx) != (b"STV7", 2, 0, operation, epoch, transaction):
            raise IngressError("DECLARATION_MISMATCH")
        if payload_len != content_length - BODY_HEADER.size or payload_len > 512:
            raise IngressError("LENGTH_MISMATCH")
        if (operation == 1 and not 1 <= payload_len <= 512 or
                operation == 2 and payload_len != 512 or
                operation in (3, 4) and (payload_len != 0 or index != 0)):
            raise IngressError("OPERATION_SHAPE")
        payload = _exact(body_source, payload_len, deadline)
        if body_source.remaining or (zlib.crc32(payload) & 0xffffffff) != crc:
            raise IngressError("TRAILING_OR_CRC")
        body_hash = hashlib.sha256()
        body_hash.update(fixed)
        body_hash.update(payload)
        if body_hash.digest() != digest:
            raise IngressError("BODY_DIGEST_MISMATCH")
        return ValidatedRecord(decision.principal, operation, transaction, fixed, payload)
    except IngressError:
        pending.cancel_owned(decision)
        raise
