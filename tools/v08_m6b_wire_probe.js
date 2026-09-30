"use strict";
// Function-level authenticated-body differential, NOT a forged signed vector.
// Python supplies a matching digest and already-proven request context. This
// bypass is solely in this probe; no production route imports the candidate.
const fs = require("node:fs"), crypto = require("node:crypto");
const lab = require("./v08_m6b_security"), v = require("./v08_crypto_vectors.json");
const results = JSON.parse(fs.readFileSync(0, "utf8")).map(hex => {
  const body = Buffer.from(hex, "hex"), digest = crypto.createHash("sha256").update(body).digest();
  const request = {length:body.length, epoch:BigInt("0x"+v.epoch_hex), tx:v.tx, operation:"begin", digestBytes:digest};
  const context = {beginBody(){}, bodyVerified(){}, expectedDigest(){ return digest; }};
  try { lab.gate2(new lab.ByteStream(body,0),request,context); return true; }
  catch(error) { if (!(error instanceof lab.Rejection)) throw error; return false; }
});
process.stdout.write(JSON.stringify(results));
