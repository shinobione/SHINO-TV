#pragma once
#include "MediaCrypto.h"
#include <limits.h>
namespace m7 {
struct Principal {
  char id[25] = {};
  uint8_t key[65] = {};
  uint64_t revision = 1;
  uint8_t ops = 0;
  bool enabled = false, revoked = false, media = false;
};
struct Challenge {
  char nonce[23] = {};
  uint64_t epoch = 0, revision = 0, serial = 0;
  uint32_t issued = 0, ttl = 0;
  uint8_t principal = 0;
  bool live = false;
};
struct Ticket {
  uint64_t epoch = 0, revision = 0, serial = 0;
  uint8_t principal = 0;
  bool valid = false;
};
class Authority {
  uint64_t epoch;
  Principal principals[16];
  Challenge challenges[4];
  uint8_t count = 0;
  char watermark[23] = {};
  bool marked = false;
  uint64_t nextSerial = 0;
  static int ordinal(char c) {
    const char *a =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-";
    const char *p = strchr(a, c);
    return p && c ? int(p - a) : -1;
  }
  static bool nonceValid(const char *n) {
    if (strlen(n) != 22)
      return false;
    for (int i = 0; i < 22; ++i)
      if (ordinal(n[i]) < 0)
        return false;
    return true;
  }
  bool newer(const char *n) const {
    if (!marked)
      return true;
    for (int i = 0; i < 22; ++i) {
      int d = ordinal(n[i]) - ordinal(watermark[i]);
      if (d)
        return d > 0;
    }
    return false;
  }
  void invalidate(uint8_t i) {
    for (auto &c : challenges)
      if (c.principal == i)
        c.live = false;
  }
  bool bump(uint8_t i) {
    auto &p = principals[i];
    invalidate(i);
    if (p.revision == UINT64_MAX) {
      p.revoked = true;
      p.enabled = false;
      return false;
    }
    ++p.revision;
    return true;
  }

public:
  uint32_t ecdsaCalls = 0;
  explicit Authority(uint64_t e) : epoch(e) {}
  bool enroll(const char *id, const uint8_t key[65], uint8_t ops,
              bool enabled = true, bool revoked = false, bool media = true) {
    size_t n = strlen(id);
    if (!epoch || !n || n > 24 || count == 16 || !publicKey(key) || !ops ||
        (ops & 0xf0))
      return false;
    for (size_t i = 0; i < n; ++i)
      if (!((id[i] >= 'a' && id[i] <= 'z') || (id[i] >= '0' && id[i] <= '9') ||
            id[i] == '_' || id[i] == '-'))
        return false;
    for (uint8_t i = 0; i < count; ++i)
      if (!strcmp(id, principals[i].id))
        return false;
    auto &p = principals[count++];
    strcpy(p.id, id);
    memcpy(p.key, key, 65);
    p.ops = ops;
    p.enabled = enabled;
    p.revoked = revoked;
    p.media = media;
    return true;
  }
  int find(const char *id) const {
    for (uint8_t i = 0; i < count; ++i)
      if (!strcmp(id, principals[i].id))
        return i;
    return -1;
  }
  bool state(uint8_t i, bool enabled, bool revoked, bool media) {
    if (i >= count || principals[i].revoked)
      return false;
    if (!bump(i))
      return false;
    auto &p = principals[i];
    p.enabled = enabled;
    p.revoked = revoked;
    p.media = media;
    return true;
  }
  bool rotate(uint8_t i, const uint8_t key[65]) {
    if (i >= count || principals[i].revoked || !publicKey(key) || !bump(i))
      return false;
    memcpy(principals[i].key, key, 65);
    return true;
  }
  bool reboot(uint64_t e) {
    if (e <= epoch)
      return false;
    epoch = e;
    for (auto &c : challenges)
      c.live = false;
    marked = false;
    return true;
  }
  bool active(uint8_t i, uint8_t op) const {
    return i < count && op >= 1 && op <= 4 && principals[i].enabled &&
           !principals[i].revoked && principals[i].media &&
           (principals[i].ops & (1u << (op - 1)));
  }
  bool issue(uint8_t i, const char *nonce, uint32_t now, uint32_t ttl) {
    if (i >= count || !principals[i].enabled || principals[i].revoked ||
        !principals[i].media || !nonceValid(nonce) || !newer(nonce) || !ttl ||
        ttl > 60000 || nextSerial == UINT64_MAX)
      return false;
    Challenge *slot = nullptr;
    unsigned own = 0;
    for (auto &c : challenges) {
      if (!c.live && !slot)
        slot = &c;
      else if (c.live && c.principal == i)
        ++own;
    }
    if (!slot || own >= 2)
      return false;
    strcpy(slot->nonce, nonce);
    slot->epoch = epoch;
    slot->revision = principals[i].revision;
    slot->serial = ++nextSerial;
    slot->principal = i;
    slot->issued = now;
    slot->ttl = ttl;
    slot->live = true;
    strcpy(watermark, nonce);
    marked = true;
    return true;
  }
  void sweep(uint32_t now) {
    for (auto &c : challenges)
      if (c.live && uint32_t(now - c.issued) >= c.ttl)
        c.live = false;
  }
  int precheck(const char *id, const char *nonce, uint64_t e, uint8_t op,
               uint32_t now, Ticket &t) const {
    t.valid = false;
    int i = find(id);
    if (i < 0 || e != epoch || !active(uint8_t(i), op))
      return -1;
    for (int j = 0; j < 4; ++j) {
      const auto &c = challenges[j];
      if (c.live && !strcmp(nonce, c.nonce) && c.principal == i &&
          c.epoch == epoch && c.revision == principals[i].revision &&
          uint32_t(now - c.issued) < c.ttl) {
        t = {epoch, c.revision, c.serial, uint8_t(i), true};
        return j;
      }
    }
    return -1;
  }
  bool proof(const Ticket &t, const uint8_t hash[32], const uint8_t sig[64]) {
    if (!t.valid || t.principal >= count)
      return false;
    ++ecdsaCalls;
    return verify(principals[t.principal].key, hash, sig);
  }
  bool consume(int slot, const Ticket &t, uint8_t op, uint32_t now) {
    if (slot < 0 || slot >= 4 || !admit(t, op))
      return false;
    auto &c = challenges[slot];
    if (!c.live || c.serial != t.serial || c.revision != t.revision ||
        c.epoch != t.epoch || uint32_t(now - c.issued) >= c.ttl)
      return false;
    c.live = false;
    return true;
  }
  bool admit(const Ticket &t, uint8_t op) const {
    return t.valid && t.epoch == epoch && active(t.principal, op) &&
           t.revision == principals[t.principal].revision;
  }
};
} // namespace m7
