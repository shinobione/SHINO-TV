"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const lab = require("./v08_crypto_lab");

const fixture = JSON.parse(fs.readFileSync(
  path.join(__dirname, "v08_crypto_vectors.json"), "utf8"));
const epoch = BigInt("0x" + fixture.epoch_hex);
const publicKey = fixture.public_key_pem;

function streamFor(entry, header = entry.header, body = Buffer.from(entry.body_hex, "hex")) {
  const head = Buffer.from(header, "ascii");
  return new lab.ByteStream(Buffer.concat([head, body]), head.length);
}
function tableFor(entry, expiresAt = 101) {
  const table = new lab.ChallengeTable(epoch);
  table.issue("media-test", entry.nonce, expiresAt);
  return table;
}
function principal(operations = ["begin", "tile", "commit", "abort"]) {
  return {"media-test": {publicKey, operations: new Set(operations)}};
}
function rejectedWithoutBody(stream, principals, table, now = 100) {
  assert.throws(() => lab.gate1(stream, principals, table, now), lab.Rejection);
  assert.equal(stream.bodyReads, 0);
  assert.equal(stream.payloadAllocated, 0);
}

test("fixed public vectors verify with real ECDSA-P256-SHA256 and fixed signature bases", () => {
  for (const entry of Object.values(fixture.entries)) {
    const stream = streamFor(entry);
    const table = new lab.ChallengeTable(epoch);
    table.issue(entry.operation === "begin" && entry === fixture.entries.wrong_principal ?
      "other-key" : "media-test", entry.nonce, 101);
    const principals = entry === fixture.entries.wrong_principal ?
      {"other-key": {publicKey, operations: new Set(["begin"])}} : principal();
    const request = lab.gate1(stream, principals, table, 100);
    assert.equal(stream.bodyReads, 0, "Gate 1 read body");
    assert.equal(stream.payloadAllocated, 0, "Gate 1 allocated body");
    assert.equal(crypto.createHash("sha256").update(lab.signatureBase(request))
      .digest("hex"), entry.base_sha256);
  }
});

test("valid Begin, Tile and Commit records pass both gates", () => {
  for (const name of ["begin", "tile", "commit"]) {
    const entry = fixture.entries[name];
    const stream = streamFor(entry);
    const request = lab.gate1(stream, principal(), tableFor(entry), 100);
    assert.equal(stream.bodyReads, 0);
    const accepted = lab.gate2(stream, request);
    assert.equal(accepted.body.length, Number(request.fields["content-length"]));
    assert.equal(stream.bodyReads, accepted.body.length);
  }
});

test("duplicates and malformed RFC fields fail before consuming body", () => {
  const entry = fixture.entries.begin;
  const cases = [
    entry.header.replace("\r\n\r\n", "\r\nContent-Length: 40\r\n\r\n"),
    entry.header.replace("\r\n\r\n", "\r\nauthorization: Basic abc\r\n\r\n"),
    entry.header.replace("\r\n\r\n", "\r\nSignature: sig1=:AAAA:\r\n\r\n"),
    entry.header.replace("\r\n\r\n", "\r\nhost: tv.test\r\n\r\n"),
    entry.header.replace("Content-Length: ", "Content-Length: +"),
    entry.header.replace("Content-Length: ", "Content-Length: 0"),
    entry.header.replace("sha-256=:", "sha-512=:"),
    entry.header.replace("Content-Digest: sha-256=:", "Content-Digest: sha-256=:A, sha-256=:"),
    entry.header.replace(";tag=\"shino-tv-media-v2\"", ";nonce=\"AAAAAAAAAAAAAAAAAAAAAA\";tag=\"shino-tv-media-v2\""),
    entry.header.replace(";tag=\"shino-tv-media-v2\"", ";tag=\"shino-tv-media-v2\", sig1=(\"@method\")"),
    entry.header.replace("sig1=(\"@method\"", "sig1=(\"@METHOD\""),
    entry.header.replace("Connection: close", "Connection: keep-alive"),
    entry.header.replace("\r\n\r\n", "\r\nTransfer-Encoding: chunked\r\n\r\n"),
    entry.header.replace("\r\n\r\n", "\r\nExpect: 100-continue\r\n\r\n"),
    entry.header.replace("\r\n\r\n", "\r\nContent-Encoding: gzip\r\n\r\n"),
    entry.header.replace("Host: tv.test", "Host: other.test"),
    entry.header.replace("Content-Length: 371", "Content-Length: 999999999999"),
  ];
  for (const header of cases) rejectedWithoutBody(streamFor(entry, header), principal(), tableFor(entry));
  const tile = fixture.entries.tile;
  rejectedWithoutBody(streamFor(tile,
    tile.header.replace("Content-Length: 552", "Content-Length: 41")),
  principal(), tableFor(tile));
});

test("target grammar, signature tampering, and header caps fail before body", () => {
  const entry = fixture.entries.begin;
  const replacements = [
    ["POST ", "GET "], [" HTTP/1.1", " HTTP/1.0"],
    ["/begin/", "/Begin/"], [fixture.tx, "A" + fixture.tx.slice(1)],
    [fixture.tx + " HTTP", fixture.tx + "?x=1 HTTP"],
    ["/media/begin/", "/media/%62egin/"],
    [fixture.tx + " HTTP", "00000000000000000000000000000000 HTTP"],
    ["Content-Digest: sha-256=:", "Content-Digest: sha-256=:A"],
    ["Content-Type: ", "Content-Type: x"],
    ["Signature: sig1=:", "Signature: sig1=:A"],
  ];
  for (const [from, to] of replacements) {
    const header = entry.header.replace(from, to);
    assert.notEqual(header, entry.header);
    rejectedWithoutBody(streamFor(entry, header), principal(), tableFor(entry));
  }
  const overlong = "POST /" + "a".repeat(2000) + " HTTP/1.1\r\n\r\n";
  rejectedWithoutBody(streamFor(entry, overlong), principal(), tableFor(entry));
  rejectedWithoutBody(streamFor(entry, entry.header.slice(0, -2), Buffer.alloc(0)),
    principal(), tableFor(entry));
});

test("replay, exact expiry, stale boot epoch and restricted role deny at Gate 1", () => {
  const entry = fixture.entries.begin;
  const table = tableFor(entry);
  lab.gate1(streamFor(entry), principal(), table, 100);
  rejectedWithoutBody(streamFor(entry), principal(), table);
  rejectedWithoutBody(streamFor(entry), principal(), tableFor(entry, 100), 100);
  const stale = tableFor(entry);
  stale.reboot(epoch + 1n);
  rejectedWithoutBody(streamFor(entry), principal(), stale);
  const tile = fixture.entries.tile;
  rejectedWithoutBody(streamFor(tile), principal(["begin"]), tableFor(tile));
  const other = fixture.entries.wrong_principal;
  rejectedWithoutBody(streamFor(other), principal(), tableFor(other));
});

test("signed digest declaration does not authenticate changed or partial body", () => {
  const entry = fixture.entries.begin;
  const changed = Buffer.from(entry.body_hex, "hex");
  changed[changed.length - 1] ^= 1;
  const stream = streamFor(entry, entry.header, changed);
  const request = lab.gate1(stream, principal(), tableFor(entry), 100);
  assert.equal(stream.bodyReads, 0);
  assert.throws(() => lab.gate2(stream, request), lab.Rejection);
  const partial = streamFor(entry, entry.header, changed.subarray(0, 42));
  const request2 = lab.gate1(partial, principal(), tableFor(entry), 100);
  assert.throws(() => lab.gate2(partial, request2), lab.Rejection);
  const extra = streamFor(entry, entry.header,
    Buffer.concat([Buffer.from(entry.body_hex, "hex"), Buffer.from("X")]));
  const request3 = lab.gate1(extra, principal(), tableFor(entry), 100);
  assert.throws(() => lab.gate2(extra, request3), lab.Rejection);
});

test("valid signed declarations with conflicting binary operation, tx or epoch fail Gate 2", () => {
  for (const name of ["operation_mismatch", "transaction_mismatch", "epoch_mismatch"]) {
    const entry = fixture.entries[name];
    const stream = streamFor(entry);
    const request = lab.gate1(stream, principal(), tableFor(entry), 100);
    assert.equal(stream.bodyReads, 0);
    assert.throws(() => lab.gate2(stream, request), lab.Rejection);
  }
});

test("challenge table is bounded and reboot invalidates the old epoch", () => {
  const table = new lab.ChallengeTable(epoch, 1);
  table.issue("media-test", fixture.entries.begin.nonce, 101);
  assert.throws(() => table.issue("media-test", fixture.entries.tile.nonce, 101), lab.Rejection);
  assert.throws(() => table.reboot(epoch), lab.Rejection);
  table.sweepExpired(100);
  assert.throws(() => table.issue("media-test", fixture.entries.tile.nonce, 101), lab.Rejection);
  table.sweepExpired(101);
  table.issue("media-test", fixture.entries.tile.nonce, 102);
  table.reboot(epoch + 1n);
  assert.equal(table.rows.size, 0);
});
