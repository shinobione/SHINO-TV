#pragma once
#include <stdint.h>
#include <string.h>
namespace m7 {
// Narrow profile 1.1 authority grammar. Normalize only the signed authority,
// never the request target or covered raw Content-Digest.
inline bool normalizeAuthority(char *s) {
  char *colon = strchr(s, ':');
  if (colon && strchr(colon + 1, ':'))
    return false;
  size_t n = colon ? size_t(colon - s) : strlen(s);
  if (!n || n > 253)
    return false;
  if (colon) {
    const char *p = colon + 1;
    size_t len = strlen(p);
    if (!len || len > 5 || p[0] == '0')
      return false;
    unsigned port = 0;
    for (size_t i = 0; i < len; ++i) {
      if (p[i] < '0' || p[i] > '9')
        return false;
      port = port * 10 + unsigned(p[i] - '0');
    }
    if (port > 65535)
      return false;
    if (port == 80)
      *colon = 0;
  }
  bool numeric = true;
  unsigned labels = 0;
  size_t start = 0;
  for (size_t i = 0; i < n; ++i) {
    char &c = s[i];
    if (c >= 'A' && c <= 'Z')
      c += 32;
    if (c != '.' && (c < '0' || c > '9'))
      numeric = false;
    if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' ||
          c == '.'))
      return false;
  }
  for (size_t i = 0; i <= n; ++i)
    if (i == n || s[i] == '.') {
      size_t len = i - start;
      if (!len || len > 63 || s[start] == '-' || s[i - 1] == '-')
        return false;
      ++labels;
      if (numeric) {
        if (len > 3 || (len > 1 && s[start] == '0'))
          return false;
        unsigned v = 0;
        for (size_t j = start; j < i; ++j)
          v = v * 10 + unsigned(s[j] - '0');
        if (v > 255)
          return false;
      }
      start = i + 1;
    }
  return !numeric || labels == 4;
}
// Exact one-member/ordered-parameter profile. Only permitted SF spaces are
// canonicalized. Full RFC Structured Fields extensions remain excluded.
inline bool signatureInput(const char *raw, char out[257]) {
  size_t used = 0;
  bool quoted = false, list = false;
  for (size_t i = 0; raw[i]; ++i) {
    char c = raw[i];
    if (used == 256)
      return false;
    if (c == '\\' || c == '\t')
      return false;
    if (c == '"')
      quoted = !quoted;
    if (!quoted) {
      if (c == '(')
        list = true;
      else if (c == ')')
        list = false;
      if (c == ' ') {
        size_t next = i;
        while (raw[next] == ' ')
          ++next;
        char prev = used ? out[used - 1] : 0;
        if (prev == '(' || prev == ';' || (list && raw[next] == ')')) {
          i = next - 1;
          continue;
        }
        if (list && prev == '"' && raw[next] == '"') {
          out[used++] = ' ';
          i = next - 1;
          continue;
        }
        return false;
      }
    }
    out[used++] = c;
  }
  out[used] = 0;
  return !quoted && !list;
}
} // namespace m7
