#pragma once
#include "MediaAuthority.h"
#include "MediaProfile.h"
#include "MediaReceiver.h"
#include <stdio.h>
namespace m7 {
struct Request {
  char target[81] = {}, keyid[25] = {}, nonce[23] = {};
  uint8_t tx[16] = {}, digest[32] = {}, signature[64] = {}, op = 0;
  uint64_t epoch = 0;
  uint16_t length = 0;
};
class Ingress {
  char headers[1025] = {};
  uint16_t used = 0, lineBytes = 0;
  unsigned fields = 0;
  uint32_t started = 0;
  std::unique_ptr<uint8_t[]> body;
  uint16_t received = 0;
  Ticket ticket;
  uint8_t proofDigest[32] = {};
  int proofSlot = -1;
  Request request;
  const char *expectedHost;
  uint32_t (*clock)();
  enum Phase { Idle, Headers, Proof, Body, Done } phase = Idle;
  M8R_NOINLINE bool parse() {
    char *end = strstr(headers, "\r\n");
    if (!end)
      return false;
    *end = 0;
    const char *names[] = {"begin", "tile", "commit", "abort"};
    char prefix[48];
    bool target = false;
    for (unsigned i = 0; i < 4; ++i) {
      snprintf(prefix, sizeof prefix, "POST /api/v2/bridge/media/%s/",
               names[i]);
      size_t n = strlen(prefix);
      if (!strncmp(headers, prefix, n) && strlen(headers) == n + 32 + 9 &&
          !strcmp(headers + n + 32, " HTTP/1.1")) {
        char tx[33];
        memcpy(tx, headers + n, 32);
        tx[32] = 0;
        if (!unhex(tx, request.tx, 16))
          return false;
        request.op = uint8_t(i + 1);
        request.epoch = be64(request.tx);
        if (!request.epoch || !be64(request.tx + 8))
          return false;
        size_t tlen = n - 5 + 32;
        if (tlen >= sizeof request.target)
          return false;
        memcpy(request.target, headers + 5, tlen);
        request.target[tlen] = 0;
        target = true;
        break;
      }
    }
    if (!target)
      return false;
    const char *namesH[] = {"host",           "content-type", "content-length",
                            "content-digest", "connection",   "signature-input",
                            "signature"};
    char *values[7] = {};
    char *p = end + 2;
    while (*p) {
      char *e = strstr(p, "\r\n");
      if (!e)
        return false;
      *e = 0;
      if (!*p)
        break;
      char *colon = strchr(p, ':');
      if (!colon || colon == p)
        return false;
      *colon = 0;
      if (!((p[0] >= 'a' && p[0] <= 'z') || (p[0] >= 'A' && p[0] <= 'Z')))
        return false;
      for (char *c = p; *c; ++c) {
        if (*c >= 'A' && *c <= 'Z')
          *c += 32;
        if (!((*c >= 'a' && *c <= 'z') || (*c >= '0' && *c <= '9') ||
              *c == '-'))
          return false;
      }
      char *v = colon + 1;
      while (*v == ' ' || *v == '\t')
        ++v;
      size_t n = strlen(v);
      while (n && (v[n - 1] == ' ' || v[n - 1] == '\t'))
        v[--n] = 0;
      if (!n)
        return false;
      for (size_t i = 0; i < n; ++i)
        if (uint8_t(v[i]) < 32 || uint8_t(v[i]) > 126)
          return false;
      int j = 0;
      for (; j < 7; ++j)
        if (!strcmp(p, namesH[j]))
          break;
      if (j == 7 || values[j])
        return false;
      values[j] = v;
      p = e + 2;
    }
    for (auto v : values)
      if (!v)
        return false;
    if (!normalizeAuthority(values[0]) || strcmp(values[0], expectedHost) ||
        strcmp(values[1], "application/vnd.shino-tv.media-wire-v2") ||
        strcmp(values[4], "close"))
      return false;
    size_t n = strlen(values[2]);
    if (!n || n > 3 || values[2][0] == '0')
      return false;
    unsigned len = 0;
    for (size_t i = 0; i < n; ++i) {
      if (values[2][i] < '0' || values[2][i] > '9')
        return false;
      len = len * 10 + unsigned(values[2][i] - '0');
    }
    if (len < 40 || len > 552 ||
        (request.op == 2   ? len != 552
         : request.op >= 3 ? len != 40
                           : len < 41))
      return false;
    request.length = uint16_t(len);
    if (strncmp(values[3], "sha-256=:", 9) || strlen(values[3]) != 54 ||
        values[3][53] != ':')
      return false;
    char encoded[89];
    memcpy(encoded, values[3] + 9, 44);
    encoded[44] = 0;
    if (!base64(encoded, request.digest, 32))
      return false;
    char canonicalInput[257];
    if (!signatureInput(values[5], canonicalInput))
      return false;
    values[5] = canonicalInput;
    const char *start =
        "sig1=(\"@method\" \"@request-target\" \"@authority\" \"content-type\" "
        "\"content-length\" "
        "\"content-digest\");alg=\"ecdsa-p256-sha256\";keyid=\"";
    if (strncmp(values[5], start, strlen(start)))
      return false;
    const char *key = values[5] + strlen(start);
    const char *quote = strchr(key, '"');
    if (!quote || quote - key < 1 || quote - key > 24)
      return false;
    memcpy(request.keyid, key, size_t(quote - key));
    request.keyid[quote - key] = 0;
    for (const char *c = request.keyid; *c; ++c)
      if (!((*c >= 'a' && *c <= 'z') || (*c >= '0' && *c <= '9') || *c == '-' ||
            *c == '_'))
        return false;
    if (strncmp(quote, "\";nonce=\"", 9))
      return false;
    const char *nonce = quote + 9;
    const char *suffix = "\";tag=\"shino-tv-media-v2\"";
    if (strlen(nonce) != 22 + strlen(suffix) || strcmp(nonce + 22, suffix))
      return false;
    memcpy(request.nonce, nonce, 22);
    request.nonce[22] = 0;
    for (auto c : request.nonce) {
      if (!c)
        break;
      if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
            (c >= '0' && c <= '9') || c == '_' || c == '-'))
        return false;
    }
    const size_t signatureLength = strlen(values[6]);
    if (strncmp(values[6], "sig1=:", 6) || signatureLength < 93 ||
        signatureLength > 95 || values[6][signatureLength - 1] != ':')
      return false;
    // Signature is not itself covered. Match the host SF decoded-byte value,
    // including omitted padding, then verify the exact 64 raw bytes.
    memcpy(encoded, values[6] + 6, 86);
    for (size_t i = 86; i < signatureLength - 7; ++i)
      if (values[6][6 + i] != '=')
        return false;
    int last = b64(encoded[85]);
    if (last < 0)
      return false;
    encoded[85] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
            [last & 0x30];
    encoded[86] = '=';
    encoded[87] = '=';
    encoded[88] = 0;
    if (!base64(encoded, request.signature, 64))
      return false;
    br_sha256_context hash;
    br_sha256_init(&hash);
    const char *components[] = {"@method",        "@request-target",
                                "@authority",     "content-type",
                                "content-length", "content-digest"};
    const char *vals[] = {"POST",    request.target, values[0],
                          values[1], values[2],      values[3]};
    for (unsigned i = 0; i < 6; ++i) {
      br_sha256_update(&hash, "\"", 1);
      br_sha256_update(&hash, components[i], strlen(components[i]));
      br_sha256_update(&hash, "\": ", 3);
      br_sha256_update(&hash, vals[i], strlen(vals[i]));
      br_sha256_update(&hash, "\n", 1);
    }
    const char *params = "\"@signature-params\": ";
    br_sha256_update(&hash, params, strlen(params));
    br_sha256_update(&hash, values[5] + 5, strlen(values[5] + 5));
    br_sha256_out(&hash, proofDigest);
    proofSlot = authority.precheck(request.keyid, request.nonce, request.epoch,
                                  request.op, clock(), ticket);
    return proofSlot >= 0;
  }
  bool reject(const char *reason) {
    ++rejected;
    outcome = reason;
    phase = Done;
    body.reset();
    return false;
  }

public:
  Authority &authority;
  Receiver &receiver;
  const char *outcome = "IDLE";
  unsigned bodyReads = 0, bodyAllocations = 0, maxPollReads = 0;
  uint32_t accepted=0,rejected=0;
  bool gate1Passed = false;
  Ingress(Authority &a, Receiver &r, const char *host, uint32_t (*c)())
      : expectedHost(host), clock(c), authority(a), receiver(r) {}
  void cancel() { reject("OWNER_CLOSED"); }
  bool needsProof() const { return phase == Proof; }
  // Called by the shallow owner on a later service poll, after parse returns.
  // No client reference: this phase cannot read TCP body bytes.
  M8R_NOINLINE bool verifyHeaders() {
    if (phase != Proof) return false;
    if (uint32_t(clock() - started) >= 2000 ||
        !authority.admit(ticket, request.op)) return reject("GATE1_STALE");
    Ticket fresh;
    const int slot = authority.precheck(request.keyid, request.nonce, request.epoch,
                                       request.op, clock(), fresh);
    if (slot != proofSlot || fresh.serial != ticket.serial ||
        fresh.revision != ticket.revision || fresh.epoch != ticket.epoch ||
        !authority.proof(ticket, proofDigest, request.signature) ||
        !authority.consume(slot, ticket, request.op, clock())) return reject("GATE1");
    gate1Passed = true;
    if (uint32_t(clock() - started) >= 2000 ||
        !authority.admit(ticket, request.op)) return reject("GATE1_STALE");
    body.reset(new (std::nothrow) uint8_t[request.length]);
    if (!body) {
#ifdef ESP8266
      ++m8::runtimeStats.allocationFailures;
#endif
      return reject("ALLOCATION");
    }
    ++bodyAllocations;
#ifdef ESP8266
    m8::sampleResources();
#endif
    phase = Body;
    outcome = "BODY";
    return true;
  }
  // Trusted single-owner scheduler/provisioning seams, never HTTP routes.
  void service() {
    const uint32_t now = clock();
    authority.sweep(now);
    receiver.tick(now);
  }
  unsigned bodyBytes() const { return body ? request.length : 0; }
  unsigned phaseCode() const { return unsigned(phase); }
  bool reboot(uint64_t epoch) {
    if (!authority.reboot(epoch))
      return false;
    cancel();
    receiver.reboot();
    return true;
  }
  bool begin(const char *line, uint32_t start) {
    body.reset();
    received = 0;
    ticket = {};
    proofSlot = -1;
    memset(proofDigest, 0, sizeof proofDigest);
    request = {};
    used = 0;
    fields = 0;
    lineBytes = 0;
    started = start;
    bodyReads = 0;
    bodyAllocations = 0;
    gate1Passed = false;
    outcome = "HEADERS";
    size_t n = strlen(line);
    if (n + 2 > 130)
      return reject("LINE");
    bool shape = false;
    const char *operations[] = {"begin", "tile", "commit", "abort"};
    char prefix[48];
    for (auto operation : operations) {
      snprintf(prefix, sizeof prefix, "POST /api/v2/bridge/media/%s/",
               operation);
      size_t p = strlen(prefix);
      if (n == p + 32 + 9 && !strncmp(line, prefix, p) &&
          !strcmp(line + p + 32, " HTTP/1.1")) {
        char tx[33];
        uint8_t binary[16];
        memcpy(tx, line + p, 32);
        tx[32] = 0;
        shape = unhex(tx, binary, 16) && be64(binary) && be64(binary + 8);
        break;
      }
    }
    if (!shape)
      return reject("LINE");
    memcpy(headers, line, n);
    headers[n] = '\r';
    headers[n + 1] = '\n';
    used = uint16_t(n + 2);
    headers[used] = 0;
    phase = Headers;
    return true;
  }
  template <class Client> M8R_NOINLINE bool poll(Client &client) {
    unsigned reads = 0; // <=64 socket bytes per poll, including headers/body.
    if (phase != Headers && phase != Body)
      return false;
    if (uint32_t(clock() - started) >= 2000)
      return reject("DEADLINE");
    if (phase == Body && !authority.admit(ticket, request.op))
      return reject("REVOKED");
    while (reads < 64 && client.available() > 0) {
      if (uint32_t(clock() - started) >= 2000)
        return reject("DEADLINE");
      if (phase == Headers) {
        if (used == 1024)
          return reject("HEADER_CAP");
        int v = client.read();
        if (v < 0)
          break;
        ++reads;
        ++lineBytes;
        if (v == 0 || v > 127 || lineBytes > 256)
          return reject("HEADER_SYNTAX");
        headers[used++] = char(v);
        headers[used] = 0;
        if (v == 10) {
          if (used < 2 || headers[used - 2] != '\r')
            return reject("CRLF");
          lineBytes = 0;
          if (used >= 4 && !memcmp(headers + used - 4, "\r\n\r\n", 4)) {
            if (!parse())
              return reject("GATE1");
            // Commit bounded proof state and RETURN. The owner verifies on a
            // later poll; parser/receiver frames are no longer live at ECDSA.
            phase = Proof;
            outcome = "PROOF";
            maxPollReads = reads > maxPollReads ? reads : maxPollReads;
            return true;
          } else if (++fields > 12)
            return reject("FIELD_CAP");
        } else if (used >= 2 && headers[used - 2] == '\r')
          return reject("CRLF");
      } else {
        if (!authority.admit(ticket, request.op))
          return reject("REVOKED");
        int v = client.read();
        if (v < 0)
          break;
        body[received++] = uint8_t(v);
        ++reads;
        ++bodyReads;
      }
      if (phase == Body && received == request.length) {
        if (client.available() > 0)
          return reject("TRAILING");
        uint8_t digest[32];
        sha(body.get(), received, digest);
        Record r;
        if (!equal(digest, request.digest, 32) ||
            !wire(body.get(), received, request.op, request.tx, request.epoch,
                  r) ||
            !authority.admit(ticket, request.op))
          return reject("GATE2");
        if (uint32_t(clock() - started) >= 2000)
          return reject("DEADLINE");
        bool ok = receiver.receive(r, ticket.principal, clock());
        if(ok) ++accepted; else ++rejected;
        outcome = receiver.outcome;
        phase = Done;
        body.reset();
        maxPollReads = reads > maxPollReads ? reads : maxPollReads;
        (void)ok;
        return false;
      }
    }
    maxPollReads = reads > maxPollReads ? reads : maxPollReads;
    if (!client.connected() && client.available() == 0)
      return reject("PARTIAL");
    return true;
  }
};
} // namespace m7
