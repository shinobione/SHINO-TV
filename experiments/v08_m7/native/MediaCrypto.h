#pragma once
// Offline native candidate. Same pinned BearSSL API on host and Xtensa.
#ifdef ESP8266
#include <bearssl/bearssl.h>
#else
#include <bearssl.h>
#endif
#include <stddef.h>
#include <stdint.h>
#include <string.h>
namespace m7 {
inline void sha(const void *p, size_t n, uint8_t out[32]) {
  br_sha256_context c;
  br_sha256_init(&c);
  br_sha256_update(&c, p, n);
  br_sha256_out(&c, out);
}
inline bool equal(const uint8_t *a, const uint8_t *b, size_t n) {
  uint8_t x = 0;
  for (size_t i = 0; i < n; ++i)
    x |= a[i] ^ b[i];
  return x == 0;
}
inline bool publicKey(const uint8_t q[65]) {
  uint8_t copy[65], one[32] = {};
  memcpy(copy, q, 65);
  one[31] = 1;
  return q[0] == 4 &&
         br_ec_p256_m15.mul(copy, 65, one, 32, BR_EC_secp256r1) == 1;
}
inline bool verify(const uint8_t q[65], const uint8_t hash[32],
                   const uint8_t sig[64]) {
  br_ec_public_key pk = {BR_EC_secp256r1, const_cast<unsigned char *>(q), 65};
  return br_ecdsa_i15_vrfy_raw(&br_ec_p256_m15, hash, 32, &pk, sig, 64) == 1;
}
inline int hex(char c) {
  return c >= '0' && c <= '9'   ? c - '0'
         : c >= 'a' && c <= 'f' ? c - 'a' + 10
                                : -1;
}
inline bool unhex(const char *s, uint8_t *p, size_t n) {
  if (strlen(s) != 2 * n)
    return false;
  for (size_t i = 0; i < n; ++i) {
    int a = hex(s[2 * i]), b = hex(s[2 * i + 1]);
    if (a < 0 || b < 0)
      return false;
    p[i] = uint8_t(a * 16 + b);
  }
  return true;
}
inline int b64(char c) {
  const char *a =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const char *p = strchr(a, c);
  return p && c ? int(p - a) : -1;
}
inline bool base64(const char *s, uint8_t *out, size_t n) {
  const size_t len = 4 * ((n + 2) / 3);
  if (strlen(s) != len)
    return false;
  size_t used = 0;
  uint32_t bits = 0;
  unsigned have = 0;
  for (size_t i = 0; i < len; ++i) {
    if (s[i] == '=') {
      for (size_t j = i; j < len; ++j)
        if (s[j] != '=')
          return false;
      break;
    }
    int v = b64(s[i]);
    if (v < 0)
      return false;
    bits = (bits << 6) | unsigned(v);
    have += 6;
    if (have >= 8) {
      have -= 8;
      if (used >= n)
        return false;
      out[used++] = uint8_t(bits >> have);
    }
  }
  return used == n && (bits & ((1u << have) - 1)) == 0 &&
         (n % 3 == 0   ? s[len - 1] != '='
          : n % 3 == 1 ? s[len - 2] == '=' && s[len - 1] == '='
                       : s[len - 2] != '=' && s[len - 1] == '=');
}
inline uint64_t be64(const uint8_t *p) {
  uint64_t n = 0;
  for (int i = 0; i < 8; ++i)
    n = (n << 8) | p[i];
  return n;
}
inline uint32_t be32(const uint8_t *p) {
  return uint32_t(p[0]) << 24 | uint32_t(p[1]) << 16 | uint32_t(p[2]) << 8 |
         p[3];
}
inline uint16_t be16(const uint8_t *p) { return uint16_t(p[0]) << 8 | p[1]; }
inline uint32_t crc(const uint8_t *p, size_t n) {
  uint32_t c = 0xffffffff;
  for (size_t i = 0; i < n; ++i) {
    c ^= p[i];
    for (int j = 0; j < 8; ++j)
      c = (c >> 1) ^ (c & 1 ? 0xedb88320 : 0);
  }
  return c ^ 0xffffffff;
}
} // namespace m7
