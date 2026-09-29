"use strict";
// Profile 1.1 HOST RESEARCH adapter. Never used by firmware or a live sender.
// RFC parsing/serialization is delegated to pinned structured-headers 2.0.3.
const sf = require("../experiments/v08_protocol/node_modules/structured-headers/cjs/index.cjs");
const crypto = require("node:crypto");
const old = require("./v08_crypto_lab");
const fail = reason => { throw new old.Rejection(reason); };
const check = (ok, reason) => { if (!ok) fail(reason); };
const names = ["host", "content-type", "content-length", "content-digest",
  "connection", "signature-input", "signature"];

function authority(value) {
  const m = /^([A-Za-z0-9.-]+)(?::([1-9][0-9]{0,4}))?$/.exec(value);
  check(m && m[1].length <= 253, "authority grammar");
  const host = m[1].toLowerCase();
  check(host.split(".").every(label => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)), "DNS labels");
  if (/^[0-9.]+$/.test(host)) {
    check(host.split(".").length === 4 && host.split(".").every(x =>
      /^(0|[1-9][0-9]{0,2})$/.test(x) && Number(x) <= 255), "IPv4 canonical");
  }
  check(!m[2] || Number(m[2]) <= 65535, "port bound");
  // Direct origin-form cleartext HTTP only. No forwarded scheme/authority.
  return host + (m[2] && m[2] !== "80" ? ":" + m[2] : "");
}

function singleDictionary(raw) {
  // RFC parsers can overwrite duplicates. Reject before Map construction.
  // This one-member profile forbids all component parameters; parameter keys
  // therefore share the single outer-list scope. Quoted text is skipped.
  let quoted = false, escaped = false;
  const params = new Set();
  for (let i = 0; i < raw.length; i++) {
    const c = raw[i];
    if (quoted) {
      if (escaped) escaped = false;
      else if (c === "\\") escaped = true;
      else if (c === '"') quoted = false;
      continue;
    }
    if (c === '"') quoted = true;
    else if (c === ',') fail("multiple/duplicate SF members");
    else if (c === ';') {
      const m = /^ *([a-z*][a-z0-9_.*-]*)/.exec(raw.slice(i + 1));
      check(m && !params.has(m[1]), "duplicate/malformed SF parameter");
      params.add(m[1]);
    }
  }
  try { return sf.parseDictionary(raw); }
  catch { fail("RFC Structured Field syntax"); }
}

function gate1(stream, principals, challenges, now) {
  const fixed = Buffer.alloc(1024);
  let used = 0, line = 0, first = true, done = false;
  while (used < fixed.length) {
    const b = stream.read();
    check(b !== null, "partial header");
    fixed[used++] = b; line++;
    check(line <= (first ? 130 : 256), "line cap");
    check(b >= 32 && b <= 126 || b === 9 || b === 13 || b === 10, "ASCII/control");
    if (b === 10) { check(used >= 2 && fixed[used - 2] === 13, "CRLF"); line = 0; first = false; }
    if (used >= 4 && fixed.subarray(used - 4, used).equals(Buffer.from("\r\n\r\n"))) { done = true; break; }
  }
  check(done, "header cap");
  const raw = fixed.subarray(0, used).toString("ascii");
  check(!/\r(?!\n)|(?<!\r)\n/.test(raw), "CRLF");
  const lines = raw.slice(0, -4).split("\r\n");
  const requestLine = lines.shift();
  check(lines.length <= 12, "field count");
  const fields = Object.create(null);
  for (const l of lines) {
    const m = /^([A-Za-z][A-Za-z0-9-]*):([\x20\x09]*)([\x20-\x7e\x09]*)$/.exec(l);
    check(m, "field syntax/obs-fold");
    const name = m[1].toLowerCase();
    check(names.includes(name) && !Object.hasOwn(fields, name), "unknown/duplicate field");
    fields[name] = m[3].replace(/^[ \t]+|[ \t]+$/g, "");
    check(fields[name].length > 0, "empty field");
  }
  check(Object.keys(fields).length === names.length, "required fields");
  fields.host = authority(fields.host);
  check(fields.host === authority(stream.expectedHost), "authority binding");
  for (const name of ["signature-input", "signature", "content-digest"]) {
    const parsed = singleDictionary(fields[name]);
    check(parsed.size === 1, "one SF member");
    if (name === "signature-input") {
      const entry = parsed.get("sig1");
      check(entry && Array.isArray(entry[0]) &&
        entry[0].every(item => typeof item[0] === "string" && item[1].size === 0), "covered components");
      check([...entry[1].keys()].join(",") === "alg,keyid,nonce,tag" &&
        [...entry[1].values()].every(v => typeof v === "string"), "parameter types/order");
      const keyid = entry[1].get("keyid");
      check(Object.hasOwn(principals, keyid), "unregistered principal");
      let key;
      try { const supplied = principals[keyid].publicKey;
        key = supplied?.type === "public" ? supplied : crypto.createPublicKey(supplied); }
      catch { fail("invalid registered public key"); }
      check(key.asymmetricKeyType === "ec" && key.asymmetricKeyDetails?.namedCurve === "prime256v1", "registered P-256 key required");
    } else {
      const entry = parsed.get(name === "signature" ? "sig1" : "sha-256");
      check(entry && entry[0] instanceof ArrayBuffer && entry[1].size === 0, "byte sequence without params");
    }
    const serialized = sf.serializeDictionary(parsed);
    // content-digest is covered WITHOUT ;sf. Require its exact canonical value;
    // do not rewrite a signed raw field into a different signature base.
    if (name === "content-digest") check(serialized === fields[name], "canonical raw digest");
    fields[name] = serialized;
  }
  const header = requestLine + "\r\n" + names.map(n => n + ": " + fields[n]).join("\r\n") + "\r\n\r\n";
  const canonical = Buffer.from(header, "ascii");
  // Reuse the retained real-crypto and lifecycle gates; this internal stream
  // contains headers only. The external stream remains at the body boundary.
  return old.gate1(new old.ByteStream(canonical, canonical.length, fields.host), principals, challenges, now);
}
module.exports = {gate1, authority, singleDictionary, PROFILE: "media-http-profile-1.1", ...
  Object.fromEntries(["ByteStream", "ChallengeTable", "gate2", "signatureBase", "Rejection"].map(k => [k, old[k]]))};
