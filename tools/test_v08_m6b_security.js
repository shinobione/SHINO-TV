"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const lab = require("./v08_m6b_profile");
const v = require("./v08_crypto_vectors.json");
const epoch = BigInt("0x" + v.epoch_hex), e = v.entries.begin;
const nonce = n => "A".repeat(21) + "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"[n];
const principal = (extra = {}) => ({publicKey: v.public_key_pem, enabled: true, revoked: false,
  roles: ["media"], operations: ["begin", "tile", "commit", "abort"], ...extra});
function stream(entry = e, header = entry.header, body = Buffer.from(entry.body_hex, "hex")) {
  const head = Buffer.from(header); return new lab.ByteStream(Buffer.concat([head, body]), head.length);
}
function setup(entry = e, extra = {}, options = {}) {
  const id = entry === v.entries.wrong_principal ? "other-key" : "media-test";
  const a = new lab.Authority(epoch, {[id]: principal(extra), unrelated: principal()}, options);
  a.issue(id, entry.nonce, 101, 100);
  return a;
}
function deny(s, a, clock = () => 100, why) {
  assert.throws(() => lab.gate1(s, a, clock), why || lab.Rejection);
  assert.equal(s.bodyReads, 0); assert.equal(s.payloadAllocated, 0);
}
function counted(fn) {
  const original = crypto.verify; let calls = 0;
  crypto.verify = (...args) => { calls++; return original(...args); };
  try { fn(() => calls); } finally { crypto.verify = original; }
}
function differentKey() {
  const jwk = crypto.createPublicKey(v.public_key_pem).export({format: "jwk"});
  const p = BigInt("0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff");
  const y = BigInt("0x" + Buffer.from(jwk.y, "base64url").toString("hex"));
  jwk.y = Buffer.from((p-y).toString(16).padStart(64, "0"), "hex").toString("base64url");
  return crypto.createPublicKey({key: jwk, format: "jwk"});
}
test("all seven original public vectors retain real ECDSA and signature-base hashes", () => {
  for (const entry of Object.values(v.entries)) {
    const a = setup(entry), s = stream(entry), req = lab.gate1(s, a, () => 100);
    assert.equal(crypto.createHash("sha256").update(lab.signatureBase(req)).digest("hex"), entry.base_sha256);
    assert.equal(s.bodyReads, 0); assert.equal(s.payloadAllocated, 0); assert.equal(a.outstanding, 0);
  }
});
test("profile 1.1 authority OWS and SF spacing still interoperate", () => {
  for (const header of [e.header.replace("Host: tv.test", "hOsT:\t TV.TEST:80 \t"),
    e.header.replace('sig1=("@method"', 'sig1=(  "@method"').replace('"content-digest")', '"content-digest"  )').replace(';alg=', ';  alg=')]) {
    const a = setup(), s = stream(e, header), r = lab.gate1(s, a, () => 100);
    lab.gate2(s, r, a); assert.equal(a.admit(r).principal, "media-test"); assert.throws(() => a.admit(r));
  }
});
test("revoked disabled and missing media role fail issuance and Gate 1 without crypto/body", () => {
  for (const extra of [{revoked: true}, {enabled: false}, {roles: []}]) {
    const a = new lab.Authority(epoch, {"media-test": principal(extra)});
    assert.throws(() => a.issue("media-test", e.nonce, 101, 100), lab.Rejection);
    counted(calls => { deny(stream(), a); assert.equal(calls(), 0); });
  }
});
test("state changes invalidate outstanding proof, are terminal on revocation, and isolate other principal", () => {
  for (const state of [{enabled:true, revoked:true, media:true}, {enabled:false, revoked:false, media:true},
    {enabled:true, revoked:false, media:false}]) {
    const a = setup(); a.issue("unrelated", nonce(1), 101, 100); a.setState("media-test", state);
    assert.equal(a.outstanding, 1); deny(stream(), a);
    assert.equal(a.precheck({keyid:"unrelated", operation:"begin", epoch, nonce:nonce(1)}, 100).key.type, "public");
    if (state.revoked) assert.throws(() => a.setState("media-test", {enabled:true, revoked:false, media:true}));
  }
});
test("disable then enable does not revive old challenges or admission tickets", () => {
  const a = setup(), s = stream(), r = lab.gate1(s, a, () => 100);
  a.setState("media-test", {enabled:false, revoked:false, media:true});
  a.setState("media-test", {enabled:true, revoked:false, media:true});
  assert.throws(() => lab.gate2(s, r, a)); assert.equal(s.bodyReads, 0);
  assert.throws(() => a.issue("media-test", e.nonce, 101, 100));
});
test("revocation after Gate 1 prevents body and after Gate 2 prevents application admission", () => {
  for (const afterBody of [false, true]) {
    const a = setup(), s = stream(), r = lab.gate1(s, a, () => 100);
    if (afterBody) lab.gate2(s, r, a);
    a.setState("media-test", {enabled:true, revoked:true, media:true});
    assert.throws(() => afterBody ? a.admit(r) : lab.gate2(s, r, a), lab.Rejection);
    if (!afterBody) assert.equal(s.bodyReads, 0);
  }
});
test("revocation during body receipt fails final admission", () => {
  const a = setup(), s = stream(), r = lab.gate1(s, a, () => 100), read = s.read.bind(s);
  s.read = () => { const b = read(); if (s.bodyReads === 1) a.setState("media-test", {enabled:true, revoked:true, media:true}); return b; };
  assert.throws(() => lab.gate2(s, r, a)); assert.throws(() => a.admit(r));
});
test("key rotation invalidates outstanding challenges and accepted Gate 1 tickets", () => {
  const a = setup(); a.issue("unrelated", nonce(1), 101, 100);
  a.rotateKey("media-test", differentKey()); assert.equal(a.outstanding, 1); deny(stream(), a);
  const b = setup(), s = stream(), r = lab.gate1(s, b, () => 100);
  b.rotateKey("media-test", v.public_key_pem); assert.throws(() => lab.gate2(s, r, b)); assert.equal(s.bodyReads, 0);
  const c = setup(); assert.throws(() => c.rotateKey("media-test", "invalid")); assert.equal(c.outstanding, 1);
  lab.gate1(stream(), c, () => 100);
});
test("caller fixture mutations cannot change enrolled lifecycle or operations", () => {
  const p = principal(), roster = {"media-test":p}, a = new lab.Authority(epoch, roster);
  p.revoked = true; p.operations.length = 0; delete roster["media-test"];
  a.issue("media-test", e.nonce, 101, 100); lab.gate1(stream(), a, () => 100);
  assert.equal(a.rosterSize, 1); assert.throws(() => a.issue("not-enrolled", nonce(1), 101, 100));
});
test("fixed roster and global/per-principal capacity fail closed without eviction", () => {
  const a = setup(e, {}, {capacity:2, perPrincipal:1}); a.issue("unrelated", nonce(1), 101, 100);
  assert.throws(() => a.issue("media-test", nonce(2), 101, 100));
  assert.throws(() => a.issue("unrelated", nonce(2), 101, 100)); assert.equal(a.outstanding, 2);
  for (let i=0;i<100;i++) assert.throws(() => a.issue("fixture-"+i, nonce(2), 101, 100));
  assert.equal(a.rosterSize, 2); assert.equal(a.outstanding, 2);
  lab.gate1(stream(), a, () => 100); a.issue("media-test", nonce(2), 102, 100); assert.equal(a.outstanding, 2);
});
test("consumed expired revoked and cross-principal nonces cannot be reissued in an epoch", () => {
  for (const cause of ["consume", "expiry", "disable"]) {
    const a = setup();
    if (cause === "consume") lab.gate1(stream(), a, () => 100);
    if (cause === "expiry") a.sweepExpired(101);
    if (cause === "disable") { a.setState("media-test", {enabled:false, revoked:false, media:true}); a.setState("media-test", {enabled:true, revoked:false, media:true}); }
    const now = cause === "expiry" ? 101 : 100;
    assert.throws(() => a.issue("media-test", e.nonce, 102, now));
    assert.throws(() => a.issue("unrelated", e.nonce, 102, now));
  }
});
test("challenge syntax collision invalid expiry and issuer failure preserve other slots", () => {
  const a = setup();
  for (const n of [undefined, "short", "!".repeat(22), e.nonce]) assert.throws(() => a.issue("unrelated", n, 101, 100));
  assert.throws(() => a.issue("unrelated", nonce(1), 100, 100)); assert.equal(a.outstanding, 1);
  const issuer = () => { throw new Error("synthetic issuer failure"); };
  assert.throws(() => a.issue("unrelated", issuer(), 101, 100)); assert.equal(a.outstanding, 1);
  lab.gate1(stream(), a, () => 100);
});
test("increasing epoch reboot invalidates all proofs, A-B-A is denied, reconstructed A remains an external gap", () => {
  const a = setup(), s = stream(), r = lab.gate1(s, a, () => 100);
  a.issue("unrelated", nonce(1), 101, 100); a.reboot(epoch+1n); assert.equal(a.outstanding, 0);
  assert.throws(() => a.reboot(epoch)); assert.throws(() => a.reboot(epoch+1n));
  deny(stream(), a); assert.throws(() => lab.gate2(s, r, a)); assert.equal(s.bodyReads, 0);
  assert.throws(() => a.reboot(1n<<64n));
  // Explicit limitation: a newly constructed volatile model cannot prove persistent freshness.
  lab.gate1(stream(), setup(), () => 100);
});
test("monotonic clock rejects rollback; exact expiry incurs zero crypto and sweep retains watermark", () => {
  const a = setup(); counted(calls => { deny(stream(), a, () => 101); assert.equal(calls(), 0); });
  assert.equal(a.outstanding, 1); assert.throws(() => a.sweepExpired(100));
  a.sweepExpired(101); assert.equal(a.outstanding, 0); assert.throws(() => a.issue("media-test", e.nonce, 102, 101));
});
test("unknown used wrong-principal stale-epoch challenges invoke zero ECDSA", () => {
  const unknown = new lab.Authority(epoch, {"media-test":principal()});
  const used = setup(); lab.gate1(stream(), used, () => 100);
  const other = new lab.Authority(epoch, {"media-test":principal(), unrelated:principal()}); other.issue("unrelated", e.nonce, 101, 100);
  const stale = setup(); stale.reboot(epoch+1n);
  counted(calls => { for (const a of [unknown,used,other,stale]) deny(stream(), a); assert.equal(calls(), 0); });
});
test("bad signatures do not consume live challenge; valid proof consumes once", () => {
  const a = setup(), invalid = e.header.replace("Signature: sig1=:T", "Signature: sig1=:U");
  counted(calls => {
    for (let i=0;i<3;i++) { deny(stream(e, invalid), a, () => 100, /bad signature/); assert.equal(a.outstanding, 1); }
    lab.gate1(stream(), a, () => 100); assert.equal(calls(), 4); deny(stream(), a); assert.equal(calls(), 4);
  });
});
test("wrong key and operation deny without body, wrong key retains challenge", () => {
  const a = setup(); a.rotateKey("media-test", differentKey()); a.issue("media-test", nonce(1), 101, 100);
  const b = new lab.Authority(epoch, {"media-test":principal({publicKey:differentKey()})}); b.issue("media-test", e.nonce, 101, 100);
  counted(calls => { deny(stream(), b, () => 100, /bad signature/); assert.equal(calls(), 1); }); assert.equal(b.outstanding, 1);
  const c = setup(e, {operations:["tile"]}); counted(calls => { deny(stream(), c); assert.equal(calls(), 0); });
  deny(stream(v.entries.wrong_principal), setup());
});
test("post-verification recheck catches expiry revocation rotation reboot and competing consume", () => {
  for (const change of ["expiry","revocation","rotation","reboot","consume"]) {
    const a = setup(), original = crypto.verify; let calls = 0;
    crypto.verify = (...args) => {
      calls++; const valid = original(...args);
      if (change === "revocation") a.setState("media-test", {enabled:true,revoked:true,media:true});
      if (change === "rotation") a.rotateKey("media-test", v.public_key_pem);
      if (change === "reboot") a.reboot(epoch+1n);
      if (change === "consume") { crypto.verify = original; lab.gate1(stream(), a, () => 100); }
      return valid;
    };
    let tick=0;
    try { deny(stream(), a, () => change === "expiry" && tick++ ? 101 : 100); assert.equal(calls,1); }
    finally { crypto.verify = original; }
  }
});
test("crypto exception preserves live challenge and reads no body", () => {
  const a = setup(), original = crypto.verify, s = stream();
  crypto.verify = () => { throw new Error("synthetic crypto failure"); };
  try { assert.throws(() => lab.gate1(s, a, () => 100), /synthetic crypto failure/); }
  finally { crypto.verify = original; }
  assert.equal(s.bodyReads,0); assert.equal(a.outstanding,1); lab.gate1(stream(), a, () => 100);
});
test("Gate 2 valid bodies and signed mismatches preserve original vector semantics", () => {
  for (const [name, entry] of Object.entries(v.entries)) {
    const a=setup(entry), s=stream(entry), r=lab.gate1(s,a,()=>100);
    if (["operation_mismatch","transaction_mismatch","epoch_mismatch"].includes(name)) assert.throws(()=>lab.gate2(s,r,a));
    else { lab.gate2(s,r,a); a.admit(r); }
  }
});
test("changed partial trailing body burns challenge and prevents application admission", () => {
  const body=Buffer.from(e.body_hex,"hex");
  for (const b of [Buffer.from(body).fill(1,body.length-1),body.subarray(0,-1),Buffer.concat([body,Buffer.from("X")])]) {
    const a=setup(), s=stream(e,e.header,b), r=lab.gate1(s,a,()=>100);
    assert.throws(()=>lab.gate2(s,r,a)); assert.throws(()=>a.admit(r)); assert.equal(a.outstanding,0); deny(stream(),a);
  }
});
test("mutable request digest cannot replace the authenticated digest", () => {
  const body=Buffer.from(e.body_hex,"hex"); body[0]|=128;
  const a=setup(), s=stream(e,e.header,body), r=lab.gate1(s,a,()=>100);
  crypto.createHash("sha256").update(body).digest().copy(r.digestBytes);
  assert.throws(()=>lab.gate2(s,r,a), /body digest/);
});
test("Gate 2 body exposure cannot mutate the owned admitted copy, and receipt is attempted once", () => {
  const a=setup(), s=stream(), r=lab.gate1(s,a,()=>100), {body}=lab.gate2(s,r,a);
  body.fill(0); assert.throws(()=>lab.gate2(stream(),r,a), /body already attempted/);
  assert.equal(a.admit(r).body.toString("hex"),e.body_hex);
});
test("unrelated revocation and rotation preserve another principal's admission", () => {
  const a=setup(), s=stream(), r=lab.gate1(s,a,()=>100);
  a.rotateKey("unrelated",differentKey()); a.setState("unrelated",{enabled:true,revoked:true,media:true});
  lab.gate2(s,r,a); assert.equal(a.admit(r).principal,"media-test");
});
test("nonce ordinal exhaustion fails closed even after freeing capacity", () => {
  const a=setup(); a.issue("unrelated","_".repeat(22),101,100); a.sweepExpired(101);
  for (const n of [e.nonce,nonce(1),"_".repeat(22)]) assert.throws(()=>a.issue("unrelated",n,102,101));
  assert.equal(a.outstanding,0); a.reboot(epoch+1n); a.issue("unrelated",e.nonce,102,101);
});
test("malformed duplicate structured fields framing and wrong targets deny before body/crypto", () => {
  const cases = [
    ...["Host: tv.test","Content-Length: 40","Signature: sig1=:AAAA:","Transfer-Encoding: chunked","Expect: 100-continue","Authorization: Basic x"].map(l=>e.header.replace("\r\n\r\n","\r\n"+l+"\r\n\r\n")),
    e.header.replace(';tag=', ';nonce="AAAAAAAAAAAAAAAAAAAAAA";tag='),
    e.header.replace(';alg=', '; alg="ecdsa-p256-sha256";alg='),
    e.header.replace('Signature: sig1=', 'Signature: sig1=:AAAA:, sig1='),
    e.header.replace(';keyid="media-test"', ';keyid=@123'),
    e.header.replace(';tag="shino-tv-media-v2"', ';tag=%"shino-tv-media-v2"'),
    e.header.replace('"@method" ', '"@method";sf '),
    e.header.replace('Content-Digest: sha-256=', 'Content-Digest: sha-256 ='),
    e.header.replace('Host: tv.test','Host : tv.test'),
    e.header.replace('/begin/','/%62egin/'), e.header.replace('POST ','GET '),
    e.header.replace('Connection: close','Connection: keep-alive'), e.header.replace(/\r\n/g,'\n')];
  counted(calls=>{ for(const header of cases) deny(stream(e,header),setup()); assert.equal(calls(),0); });
});
