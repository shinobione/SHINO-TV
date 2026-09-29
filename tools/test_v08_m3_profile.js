"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const lab = require("./v08_m3_profile");
const vectors = require("./v08_crypto_vectors.json");
function run(entry, header = entry.header, body = Buffer.from(entry.body_hex, "hex"), operations = ["begin", "tile", "commit", "abort"], now = 100, epoch = BigInt("0x" + vectors.epoch_hex)) {
  const head = Buffer.from(header);
  const stream = new lab.ByteStream(Buffer.concat([head, body]), head.length);
  const table = new lab.ChallengeTable(epoch);
  const keyid = entry === vectors.entries.wrong_principal ? "other-key" : "media-test";
  table.issue(keyid, entry.nonce, 101);
  const principals = {[keyid]: {publicKey: vectors.public_key_pem, operations: new Set(operations)}};
  return {stream, table, principals, invoke: () => lab.gate1(stream, principals, table, now)};
}
test("profile 1.1 retains every public signature base and verifies real P-256", () => {
  for (const entry of Object.values(vectors.entries)) {
    const t = run(entry), request = t.invoke();
    assert.equal(crypto.createHash("sha256").update(lab.signatureBase(request)).digest("hex"), entry.base_sha256);
    assert.equal(t.stream.bodyReads, 0);
    assert.equal(t.stream.payloadAllocated, 0);
  }
});
test("RFC authority and outer OWS normalization interoperate with retained signatures", () => {
  const entry = vectors.entries.begin;
  for (const host of ["TV.TEST", "TV.TEST:80", "tv.test:80"]) {
    const t = run(entry, entry.header.replace("Host: tv.test", "hOsT:\t " + host + " \t"));
    const req = t.invoke(); assert.equal(req.fields.host, "tv.test");
    assert.equal(t.stream.bodyReads, 0); lab.gate2(t.stream, req);
  }
});
test("RFC SF inner-list and parameter spaces serialize to the original base", () => {
  const entry = vectors.entries.begin;
  const header = entry.header.replace('sig1=("@method"', 'sig1=(  "@method"')
    .replace('"content-digest")', '"content-digest"  )').replace(';alg=', ';  alg=');
  const t = run(entry, header); t.invoke(); assert.equal(t.stream.bodyReads, 0);
});
test("duplicates, invalid RFC syntax/types, policy exclusions and framing deny without body", () => {
  const e = vectors.entries.begin;
  const headers = [
    e.header.replace(';tag=', ';nonce="AAAAAAAAAAAAAAAAAAAAAA";tag='),
    e.header.replace(';alg=', '; alg="ecdsa-p256-sha256";alg='),
    e.header.replace('Signature: sig1=', 'Signature: sig1=:AAAA:, sig1='),
    e.header.replace(';tag="shino-tv-media-v2"', ';tag=%"shino-tv-media-v2"'),
    e.header.replace(';keyid="media-test"', ';keyid=@123'),
    e.header.replace(';keyid="media-test"', ';keyid=media-test'),
    e.header.replace('"@method" ', '"@method";sf '),
    e.header.replace(';alg="ecdsa-p256-sha256";keyid="media-test"', ';keyid="media-test";alg="ecdsa-p256-sha256"'),
    e.header.replace(';nonce=', ';nonce ='),
    e.header.replace('Content-Digest: sha-256=', 'Content-Digest: sha-256 ='),
    e.header.replace('Connection: close', 'Connection: keep-alive'),
    ...["Host: tv.test", "Content-Length: 999999999999", "Signature: sig1=:AAAA:",
      "Authorization: Basic x", "Transfer-Encoding: chunked", "Expect: 100-continue", "Content-Encoding: gzip"]
      .map(l => e.header.replace("\r\n\r\n", "\r\n" + l + "\r\n\r\n")),
    e.header.replace("Host: tv.test", "Host : tv.test"),
    e.header.replace("Host: tv.test", "Host: tv.test:080"),
    e.header.replace("Host: tv.test", "Host: tv.test."),
    e.header.replace("Host: tv.test", "Host: [::1]"),
    e.header.replace("Host: tv.test", "Host: tv.test:65536"),
    e.header.replace("\r\nSignature:", "\r\n Signature:"),
  ];
  for (const header of headers) {
    const t = run(e, header); assert.throws(t.invoke, lab.Rejection);
    assert.equal(t.stream.bodyReads, 0); assert.equal(t.stream.payloadAllocated, 0);
  }
});
test("operation, expiry, epoch, wrong public key and replay gates", () => {
  const e = vectors.entries.begin;
  for (const t of [run(e, e.header, undefined, ["tile"]), run(e, e.header, undefined, undefined, 101),
    run(e, e.header, undefined, undefined, 100, 2n),
    run(e, e.header.replace("/begin/", "/abort/"))]) {
    assert.throws(t.invoke, lab.Rejection); assert.equal(t.stream.bodyReads, 0);
  }
  // Deterministic distinct public point -Q, with no private key generation.
  const jwk = crypto.createPublicKey(vectors.public_key_pem).export({format:"jwk"});
  const p = BigInt("0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff");
  const y = BigInt("0x" + Buffer.from(jwk.y,"base64url").toString("hex"));
  jwk.y = Buffer.from((p-y).toString(16).padStart(64,"0"),"hex").toString("base64url");
  const t = run(e); t.principals["media-test"].publicKey = crypto.createPublicKey({key:jwk,format:"jwk"});
  assert.throws(t.invoke, lab.Rejection); assert.equal(t.stream.bodyReads, 0);
  const valid = run(e); valid.invoke();
  const replay = run(e); assert.throws(() => lab.gate1(replay.stream, valid.principals, valid.table, 100), lab.Rejection);
  assert.equal(replay.stream.bodyReads, 0);
});
test("raw duplicate SF evidence is rejected before dictionary overwrite", () => {
  for(const value of ['sig1=(), sig1=()', 'sig1=();nonce="a";nonce="b"',
    'sig1=(); nonce="a"; nonce="b"', 'sha-256=:AAAA:, sha-256=:BBBB:']) {
    assert.throws(() => lab.singleDictionary(value), lab.Rejection);
  }
  assert.equal(lab.singleDictionary('sig1=();nonce="a,b;nonce=c"').size,1,"quoted delimiters are data");
});
test("body mismatch, interruption and buffered pipeline rejected after Gate 1", () => {
  const e = vectors.entries.begin, body = Buffer.from(e.body_hex, "hex");
  for (const bytes of [Buffer.from(body).fill(1, body.length - 1), body.subarray(0, -1), Buffer.concat([body, Buffer.from("GET / HTTP/1.1\r\n")])]) {
    const t = run(e, e.header, bytes), req = t.invoke();
    assert.equal(t.stream.bodyReads, 0); assert.throws(() => lab.gate2(t.stream, req), lab.Rejection);
    assert.equal(t.stream.payloadAllocated, body.length);
  }
});
test("declared operation/transaction disagreement retains original signed malformed-body evidence", () => {
  for (const name of ["operation_mismatch", "transaction_mismatch", "epoch_mismatch"]) {
    const e = vectors.entries[name]; assert.ok(e, "required retained malformed vector");
    const t = run(e), req = t.invoke(); assert.throws(() => lab.gate2(t.stream, req), lab.Rejection);
  }
});
