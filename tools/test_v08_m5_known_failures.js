"use strict";
// Characterizations of unresolved Mission 4 findings. Passing asserts a defect.
// Public captured fixtures only; no signer, keys, enrollment or production change.
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const p = require("./v08_m3_profile");
const v = require("./v08_crypto_vectors.json");
const e = v.entries.begin, epoch = BigInt("0x" + v.epoch_hex);
const principals = () => ({"media-test": {publicKey: v.public_key_pem,
  operations: new Set(["begin", "tile", "commit", "abort"]), revoked: true}});
const stream = () => new p.ByteStream(Buffer.concat([Buffer.from(e.header),
  Buffer.from(e.body_hex, "hex")]), Buffer.byteLength(e.header));
const table = () => {const t = new p.ChallengeTable(epoch);t.issue("media-test", e.nonce, 1000);return t;};
test("KNOWN FAILURE R1: revoked existing fixture principal still accepted", () => {
  const s=stream();p.gate1(s,principals(),table(),100);assert.equal(s.bodyReads,0);
});
test("KNOWN FAILURE R2: high bit magic aliases accepted by Gate2 function", () => {
  const req=p.gate1(stream(),principals(),table(),100);
  const body=Buffer.from(e.body_hex,"hex");for(let i=0;i<4;i++)body[i]|=0x80;
  assert.equal(body.subarray(0,4).toString("hex"),"d3d4d6b7");
  p.gate2(new p.ByteStream(body,0),{...req,digestBytes:crypto.createHash("sha256").update(body).digest()});
});
test("KNOWN FAILURE R3: reissued consumed nonce admits captured signature", () => {
  const t=table();p.gate1(stream(),principals(),t,100);t.issue("media-test",e.nonce,1000);
  p.gate1(stream(),principals(),t,100);
});
test("KNOWN FAILURE R3: A/B/A epochs and unbounded principal rows", () => {
  const t=new p.ChallengeTable(epoch);t.reboot(2n);t.reboot(epoch);
  t.issue("media-test",e.nonce,1000);p.gate1(stream(),principals(),t,100);
  const many=new p.ChallengeTable(epoch);for(let i=0;i<100;i++)many.issue("fixture-"+i,e.nonce,1000);
  assert.equal(many.rows.size,100);assert.equal(many.capacityPerKey,2);
});
test("KNOWN FAILURE R4: unknown/replayed challenge invokes real crypto before denial", () => {
  const original=crypto.verify;let calls=0;
  crypto.verify=(...args)=>{calls++;return original(...args);};
  try {assert.throws(()=>p.gate1(stream(),principals(),new p.ChallengeTable(epoch),100),/challenge unknown\/replayed/);assert.equal(calls,1);}
  finally {crypto.verify=original;}
});
