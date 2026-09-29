"use strict";

// Host-only, deliberately narrow RFC 9421/9530/8941 profile laboratory.
// This is not a native parser, sender, key provisioning path or production verifier.
const crypto = require("node:crypto");

const PREFIX = "/api/v2/bridge/media/";
const COMPONENTS = [
  "@method", "@request-target", "@authority",
  "content-type", "content-length", "content-digest",
];
const CONTENT_TYPE = "application/vnd.shino-tv.media-wire-v2";
const TAG = "shino-tv-media-v2";
const OP = Object.freeze({begin: 1, tile: 2, commit: 3, abort: 4});
const MAX_LINE = 130;
const MAX_FIELD_LINE = 256;
const MAX_HEADER = 1024;
const MAX_FIELDS = 12;
const ALLOWED = new Set([
  "host", "content-type", "content-length", "content-digest",
  "connection", "signature-input", "signature",
]);

class Rejection extends Error {
  constructor(reason) { super(reason); this.name = "Rejection"; }
}
function requireThat(ok, reason) {
  if (!ok) throw new Rejection(reason);
}
function exactBase64(value, size) {
  requireThat(/^[A-Za-z0-9+/]+={0,2}$/.test(value), "base64 syntax");
  const decoded = Buffer.from(value, "base64");
  requireThat(decoded.length === size && decoded.toString("base64") === value, "base64 canonical");
  return decoded;
}
function canonicalDigest(body) {
  return "sha-256=:" + crypto.createHash("sha256").update(body).digest("base64") + ":";
}
function signatureInput(keyid, nonce) {
  return 'sig1=("' + COMPONENTS.join('" "') +
    '");alg="ecdsa-p256-sha256";keyid="' + keyid +
    '";nonce="' + nonce + '";tag="' + TAG + '"';
}
function signatureBase(request) {
  const fields = request.fields;
  const values = [
    request.method, request.target, fields.host,
    fields["content-type"], fields["content-length"], fields["content-digest"],
  ];
  return Buffer.from(COMPONENTS.map((name, i) => '"' + name + '": ' + values[i])
    .concat(['"@signature-params": ' + request.signatureInput.slice(5)])
    .join("\n"), "ascii");
}
function readHeaders(stream) {
  const storage = Buffer.alloc(MAX_HEADER);
  let used = 0;
  let lineBytes = 0;
  let firstLine = true;
  while (used < MAX_HEADER) {
    const byte = stream.read();
    requireThat(byte !== null, "partial header");
    storage[used++] = byte;
    lineBytes++;
    requireThat(lineBytes <= (firstLine ? MAX_LINE : MAX_FIELD_LINE), "line cap");
    if (byte === 10) {
      requireThat(used >= 2 && storage[used - 2] === 13, "CRLF");
      lineBytes = 0;
      firstLine = false;
    }
    if (used >= 4 &&
        storage[used - 4] === 13 && storage[used - 3] === 10 &&
        storage[used - 2] === 13 && storage[used - 1] === 10) {
      break;
    }
  }
  requireThat(used <= MAX_HEADER &&
    storage.subarray(used - 4, used).equals(Buffer.from([13, 10, 13, 10])),
    "header cap");
  const raw = storage.subarray(0, used);
  requireThat(raw.every(b => b <= 127 && b !== 0), "header ascii");
  const value = raw.toString("ascii");
  requireThat(!/(?<!\r)\n|\r(?!\n)/.test(value), "CRLF");
  const lines = value.slice(0, -4).split("\r\n");
  requireThat(lines[0].length + 2 <= MAX_LINE, "request line cap");
  const first = /^POST (\S+) HTTP\/1\.1$/.exec(lines.shift());
  requireThat(first !== null, "request line");
  const target = first[1];
  requireThat(target.startsWith(PREFIX), "media namespace");
  const match = /^\/api\/v2\/bridge\/media\/(begin|tile|commit|abort)\/([0-9a-f]{32})$/.exec(target);
  requireThat(match !== null, "target grammar");
  const epoch = BigInt("0x" + match[2].slice(0, 16));
  const sequence = BigInt("0x" + match[2].slice(16));
  requireThat(epoch !== 0n && sequence !== 0n, "epoch/sequence");
  requireThat(lines.length <= MAX_FIELDS, "field count");
  const fields = Object.create(null);
  for (const line of lines) {
    requireThat(line.length + 2 <= MAX_FIELD_LINE, "field line cap");
    const parsed = /^([A-Za-z][A-Za-z0-9-]*): ([\x21-\x7e](?:[\x20-\x7e]*[\x21-\x7e])?)$/.exec(line);
    requireThat(parsed !== null, "field syntax");
    const name = parsed[1].toLowerCase();
    requireThat(ALLOWED.has(name) && !Object.hasOwn(fields, name), "unknown/duplicate field");
    fields[name] = parsed[2];
  }
  requireThat(Object.keys(fields).length === 7, "required fields");
  requireThat(fields.connection === "close" && fields.host === stream.expectedHost &&
    fields["content-type"] === CONTENT_TYPE, "required field value");
  const len = fields["content-length"];
  requireThat(/^(?:[1-9][0-9]*)$/.test(len) && len.length <= 3, "length syntax");
  const length = Number(len);
  requireThat(length >= 40 && length <= 552, "length bound");
  requireThat(match[1] === "tile" ? length === 552 :
    (match[1] === "commit" || match[1] === "abort" ? length === 40 : length >= 41),
  "operation length");
  const digest = /^sha-256=:([A-Za-z0-9+/]+={0,2}):$/.exec(fields["content-digest"]);
  requireThat(digest !== null, "digest grammar");
  const digestBytes = exactBase64(digest[1], 32);
  const input = fields["signature-input"];
  const si = /^sig1=\("@method" "@request-target" "@authority" "content-type" "content-length" "content-digest"\);alg="ecdsa-p256-sha256";keyid="([a-z0-9_-]{1,24})";nonce="([A-Za-z0-9_-]{22})";tag="shino-tv-media-v2"$/.exec(input);
  requireThat(si !== null, "signature-input grammar");
  const sig = /^sig1=:([A-Za-z0-9+/]+={0,2}):$/.exec(fields.signature);
  requireThat(sig !== null, "signature grammar");
  const signatureBytes = exactBase64(sig[1], 64);
  return {
    method: "POST", target, operation: match[1], tx: match[2], epoch,
    sequence, fields, length, digestBytes, keyid: si[1], nonce: si[2],
    signatureInput: input, signatureBytes,
  };
}
class ByteStream {
  constructor(raw, headerEnd, expectedHost = "tv.test") {
    this.raw = Buffer.from(raw);
    this.headerEnd = headerEnd;
    this.expectedHost = expectedHost;
    this.offset = 0;
    this.bodyReads = 0;
    this.payloadAllocated = 0;
  }
  read() {
    if (this.offset >= this.raw.length) return null;
    if (this.offset >= this.headerEnd) this.bodyReads++;
    return this.raw[this.offset++];
  }
}
class ChallengeTable {
  constructor(epoch, capacityPerKey = 2) {
    this.epoch = epoch;
    this.capacityPerKey = capacityPerKey;
    this.rows = new Map();
  }
  issue(keyid, nonce, expiresAt) {
    requireThat(/^[A-Za-z0-9_-]{22}$/.test(nonce), "challenge syntax");
    const list = this.rows.get(keyid) || new Map();
    requireThat(!list.has(nonce) && list.size < this.capacityPerKey, "challenge capacity");
    list.set(nonce, expiresAt);
    this.rows.set(keyid, list);
  }
  consume(keyid, nonce, now) {
    const list = this.rows.get(keyid);
    requireThat(list && list.has(nonce), "challenge unknown/replayed");
    const expiresAt = list.get(nonce);
    requireThat(now < expiresAt, "challenge expired");
    list.delete(nonce);
  }
  sweepExpired(now) {
    for (const list of this.rows.values()) {
      for (const [nonce, expiresAt] of list) {
        if (now >= expiresAt) list.delete(nonce);
      }
    }
  }
  reboot(epoch) {
    requireThat(epoch !== 0n && epoch !== this.epoch, "new epoch required");
    this.epoch = epoch;
    this.rows.clear();
  }
}
function gate1(stream, principals, challenges, now) {
  const request = readHeaders(stream);
  requireThat(request.epoch === challenges.epoch, "stale epoch");
  const principal = principals[request.keyid];
  requireThat(principal && principal.operations.has(request.operation), "principal/operation");
  const verified = crypto.verify("sha256", signatureBase(request),
    {key: principal.publicKey, dsaEncoding: "ieee-p1363"}, request.signatureBytes);
  requireThat(verified, "bad signature");
  challenges.consume(request.keyid, request.nonce, now);
  return request;
}
function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function gate2(stream, request) {
  const body = Buffer.alloc(request.length);
  stream.payloadAllocated = body.length;
  for (let i = 0; i < body.length; i++) {
    const byte = stream.read();
    requireThat(byte !== null, "partial body");
    body[i] = byte;
  }
  requireThat(stream.offset === stream.raw.length, "trailing bytes already received");
  requireThat(crypto.timingSafeEqual(
    crypto.createHash("sha256").update(body).digest(), request.digestBytes), "body digest");
  requireThat(body.toString("ascii", 0, 4) === "STV7" && body[4] === 2 &&
    body[5] === OP[request.operation] && body.readUInt16BE(6) === 0, "record header");
  requireThat(body.readBigUInt64BE(8) === request.epoch &&
    body.subarray(16, 32).toString("hex") === request.tx, "record identity");
  const index = body.readUInt16BE(32);
  const payloadLength = body.readUInt16BE(34);
  requireThat(payloadLength === body.length - 40 &&
    body.readUInt32BE(36) === crc32(body.subarray(40)), "record length/CRC");
  requireThat(request.operation === "tile" ?
    (payloadLength === 512 && index <= 8) :
    (index === 0 && (request.operation === "begin" ?
      payloadLength >= 1 && payloadLength <= 512 : payloadLength === 0)),
    "operation shape");
  return {request, body};
}
module.exports = {
  ByteStream, ChallengeTable, Rejection, canonicalDigest, signatureInput,
  signatureBase, gate1, gate2, crc32, CONTENT_TYPE, TAG,
};
