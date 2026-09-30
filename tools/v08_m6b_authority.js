"use strict";
// Isolated HOST model. No enrollment service, entropy source or native ingress.
const crypto = require("node:crypto");
const {Rejection} = require("./v08_crypto_lab");
const check = (ok, why) => { if (!ok) throw new Rejection(why); };
const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
const MAX_EPOCH = (1n << 64n) - 1n;
function nonceOrdinal(nonce) {
  check(typeof nonce === "string" && /^[A-Za-z0-9_-]{22}$/.test(nonce), "challenge syntax");
  return [...nonce].reduce((n, c) => n * 64n + BigInt(alphabet.indexOf(c)), 0n);
}
function publicKey(value) {
  let key;
  try { key = value?.type === "public" ? value : crypto.createPublicKey(value); }
  catch { throw new Rejection("invalid enrolled public key"); }
  check(key.asymmetricKeyType === "ec" && key.asymmetricKeyDetails?.namedCurve === "prime256v1", "P-256 key required");
  return key;
}
class Authority {
  #principals = new Map();
  #challenges = new Map();
  #tickets = new WeakMap();
  #epoch;
  #high = -1n;
  #lastTime = 0;
  #capacity;
  #perPrincipal;
  constructor(epoch, roster, {capacity = 4, perPrincipal = 2} = {}) {
    check(typeof epoch === "bigint" && epoch > 0n && epoch <= MAX_EPOCH, "epoch range");
    check(Number.isSafeInteger(capacity) && capacity > 0 && capacity <= 64 &&
      Number.isSafeInteger(perPrincipal) && perPrincipal > 0 && perPrincipal <= capacity, "capacity range");
    check(roster && Object.keys(roster).length > 0 && Object.keys(roster).length <= 16, "roster bound");
    for (const [id, p] of Object.entries(roster)) {
      check(/^[a-z0-9_-]{1,24}$/.test(id) && typeof p.enabled === "boolean" &&
        typeof p.revoked === "boolean" && Array.isArray(p.roles) && Array.isArray(p.operations) &&
        p.operations.every(op => ["begin", "tile", "commit", "abort"].includes(op)), "principal contract");
      this.#principals.set(id, {key: publicKey(p.publicKey), enabled: p.enabled,
        revoked: p.revoked, media: p.roles.includes("media"), operations: new Set(p.operations), revision: 0n});
    }
    this.#epoch = epoch; this.#capacity = capacity; this.#perPrincipal = perPrincipal;
  }
  get epoch() { return this.#epoch; }
  get outstanding() { return this.#challenges.size; }
  get rosterSize() { return this.#principals.size; }
  #clock(now) {
    check(Number.isSafeInteger(now) && now >= this.#lastTime, "monotonic clock required");
    this.#lastTime = now;
  }
  #active(id, operation) {
    const p = this.#principals.get(id);
    check(p && p.enabled && !p.revoked && p.media && (!operation || p.operations.has(operation)), "inactive principal/role/operation");
    return p;
  }
  #invalidate(id) {
    for (const [nonce, c] of this.#challenges) if (c.id === id) this.#challenges.delete(nonce);
  }
  #bump(id, p) {
    if (p.revision === MAX_EPOCH) {
      p.enabled = false; p.revoked = true; this.#invalidate(id);
      throw new Rejection("principal revision exhausted");
    }
    p.revision++;
  }
  setState(id, {enabled, revoked, media}) {
    const p = this.#principals.get(id);
    check(p && [enabled, revoked, media].every(x => typeof x === "boolean"), "state contract");
    check(!p.revoked || revoked, "revocation is terminal");
    this.#bump(id, p); p.enabled = enabled; p.revoked = revoked; p.media = media;
    this.#invalidate(id);
  }
  rotateKey(id, value) {
    const p = this.#principals.get(id); check(p, "unenrolled principal");
    const key = publicKey(value); // failure preserves old key and challenges
    this.#bump(id, p); p.key = key; this.#invalidate(id);
  }
  issue(id, nonce, expiresAt, now) {
    this.#clock(now); const p = this.#active(id);
    check(p.operations.size > 0, "no media operations");
    check(Number.isSafeInteger(expiresAt) && expiresAt > now, "challenge expiry");
    const ordinal = nonceOrdinal(nonce);
    // Constant 132-bit watermark, never a history of consumed nonces. The HOST
    // issuer must supply increasing opaque values. This does not prove entropy.
    check(ordinal > this.#high, "challenge collision/reissue/order");
    check(this.#challenges.size < this.#capacity &&
      [...this.#challenges.values()].filter(c => c.id === id).length < this.#perPrincipal, "challenge capacity");
    const c = Object.freeze({id, epoch: this.#epoch, revision: p.revision, expiresAt});
    this.#challenges.set(nonce, c); this.#high = ordinal;
    return nonce;
  }
  sweepExpired(now) {
    this.#clock(now);
    for (const [nonce, c] of this.#challenges) if (now >= c.expiresAt) this.#challenges.delete(nonce);
  }
  reboot(epoch) {
    // One live model enforces increasing epochs with O(1) state. Reconstruction
    // after power loss needs an independently reviewed persistent authority.
    check(typeof epoch === "bigint" && epoch > this.#epoch && epoch <= MAX_EPOCH, "fresh monotonic epoch required");
    this.#epoch = epoch; this.#high = -1n; this.#challenges.clear(); this.#tickets = new WeakMap();
    // Clock remains one host authority monotonic domain, not a device millis().
  }
  precheck(request, now) {
    this.#clock(now); const p = this.#active(request.keyid, request.operation);
    check(request.epoch === this.#epoch, "stale epoch");
    const c = this.#challenges.get(request.nonce);
    check(c && c.id === request.keyid && c.epoch === this.#epoch && c.revision === p.revision, "challenge unknown/replayed/binding");
    check(now < c.expiresAt, "challenge expired");
    return Object.freeze({challenge: c, key: p.key});
  }
  consume(request, preliminary, now) {
    const current = this.precheck(request, now);
    check(current.challenge === preliminary.challenge && current.key === preliminary.key, "challenge changed during proof");
    // Recheck + delete + ticket publication are synchronous, without callbacks.
    this.#challenges.delete(request.nonce);
    Object.freeze(request.fields); Object.freeze(request);
    this.#tickets.set(request, {epoch: this.#epoch, revision: current.challenge.revision,
      digest: Buffer.from(request.digestBytes), body: null, bodyStarted: false});
  }
  checkAdmission(request) {
    const t = this.#tickets.get(request); const p = this.#active(request.keyid, request.operation);
    check(t && t.epoch === this.#epoch && t.revision === p.revision, "stale application admission");
    return t;
  }
  beginBody(request) {
    const t = this.checkAdmission(request); check(!t.bodyStarted, "body already attempted");
    t.bodyStarted = true;
  }
  bodyVerified(request, body) { this.checkAdmission(request).body = Buffer.from(body); }
  expectedDigest(request) { return Buffer.from(this.checkAdmission(request).digest); }
  admit(request) {
    const t = this.checkAdmission(request); check(t.body, "Gate 2 required");
    this.#tickets.delete(request);
    // HOST admission boundary only; future application mutation must share
    // this owner/critical section with revocation, rotation and reboot.
    return {principal: request.keyid, epoch: request.epoch, operation: request.operation, tx: request.tx, body: t.body};
  }
}
module.exports = {Authority, nonceOrdinal};
