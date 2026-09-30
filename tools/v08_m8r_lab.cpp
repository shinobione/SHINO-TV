// Same native header/crypto implementation and real pinned owner over loopback.
#define main inheritedMain
#include "v08_m6a_socket_lab.cpp"
#undef main
#include "fixtures.inc"
#include <MediaIngress.h>
#include <sstream>
static const uint64_t epoch = 0x1122334455667788ULL;
static std::string decode(const char *hex) {
  size_t n = strlen(hex) / 2;
  std::string b(n, '\0');
  if (n && !m7::unhex(hex, reinterpret_cast<uint8_t *>(b.data()), n))
    throw std::runtime_error("hex");
  return b;
}
static std::string raw(const Fixture &f) {
  return std::string(f.header) + decode(f.body);
}
static uint32_t clockNow() { return host_ms; }
static double nativeWorstUs = 0;
static size_t nativeMaxReads = 0;
struct Bytes {
  std::string bytes;
  size_t at = 0;
  int available() { return int(bytes.size() - at); }
  int read() { return available() ? uint8_t(bytes[at++]) : -1; }
  bool connected() { return false; }
};
static bool drive(m7::Ingress &ingress, std::string input) {
  auto n = input.find("\r\n");
  if (n == input.npos)
    return false;
  std::string line = input.substr(0, n);
  Bytes b{input.substr(n + 2)};
  if (!ingress.begin(line.c_str(), host_ms))
    return false;
  for (int i = 0; i < 40; ++i)
    if (!(ingress.needsProof() ? ingress.verifyHeaders() : ingress.poll(b)))
      return ingress.gate1Passed;
  return false;
}
static void nativeTransact(m7::Ingress &ingress, const std::string &input) {
  clearOwner();
  Peer p;
  p.send(input);
  arrival();
  for (int i = 0; i < 50; ++i) {
    auto before = bytesRead.load();
    nativeWorstUs = std::max(nativeWorstUs, poll());
    nativeMaxReads = std::max(nativeMaxReads, bytesRead.load() - before);
    check(bytesRead.load() - before <= 64,
          "media total socket bytes/poll <=64");
    if (!server.client())
      break;
  }
  check(!server.client(), "media closes terminal owner");
  check(ingress.maxPollReads <= 64, "native ingress work counter");
}
static void setup(m7::Authority &authority, const char *key) {
  uint8_t p[65];
  check(m7::unhex(key, p, 65) && authority.enroll("media-test", p, 15),
        "valid synthetic/public provisioning");
}
int main(int argc, char **argv) {
  if (argc > 1 && std::string(argv[1]) == "headers") {
    uint8_t key[65];
    m7::unhex(retainedKey, key, 65);
    std::string hex;
    while (std::getline(std::cin, hex)) {
      m7::Authority a(epoch);
      a.enroll("media-test", key, 15);
      a.issue(0, begin.nonce, 100, 1000);
      m7::Receiver r;
      m7::Ingress i(a, r, "tv.test", clockNow);
      host_ms = 100;
      std::cout << (drive(i, decode(hex.c_str())) ? 1 : 0) << '\n';
    }
    return 0;
  }
  if (argc > 1 && std::string(argv[1]) == "wire") {
    uint8_t tx[16];
    m7::unhex("11223344556677880000000000000001", tx, 16);
    std::string line;
    while (std::getline(std::cin, line)) {
      auto b = decode(line.c_str());
      m7::Record r;
      m7::Metadata meta;
      bool ok = m7::wire(reinterpret_cast<const uint8_t *>(b.data()), b.size(),
                         1, tx, epoch, r) &&
                m7::metadata(r, meta);
      std::cout << (ok ? 1 : 0) << '\n';
    }
    return 0;
  }
  // Run every inherited Mission 6A legacy assertion with media seam null.
  std::ostringstream historical;
  auto *saved = std::cout.rdbuf(historical.rdbuf());
  int result = inheritedMain();
  std::cout.rdbuf(saved);
  if (result)
    return result;
  const int legacyChecks = checks;
  checks = 0;
  failed = 0;
  server.begin();
  host_ms = 100;
  {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    check(a.issue(0, begin.nonce, host_ms, 1000), "retained issue");
    nativeTransact(i, raw(begin));
    check(i.gate1Passed && i.bodyReads == 371 && r.pending && a.ecdsaCalls == 1,
          "retained Begin real P256 Gate1 before bounded body");
    auto mutations = r.mutations, calls = a.ecdsaCalls;
    nativeTransact(i, raw(begin));
    check(!i.gate1Passed && !i.bodyReads && !i.bodyAllocations &&
              a.ecdsaCalls == calls && r.mutations == mutations,
          "used challenge zero ECDSA/body/state");
    check(a.issue(0, commit.nonce, host_ms, 1000), "retained commit issue");
    nativeTransact(i, raw(commit));
    check(r.sink.commits == 1 && !r.pending && !strcmp(i.outcome, "COMMITTED"),
          "retained signed coverless Begin Commit");
    nativeTransact(i, raw(tile));
    check(!i.bodyReads && !i.bodyAllocations && a.ecdsaCalls == 2,
          "unknown challenge zero ECDSA");
  }
  for (auto width : {0, 32, 48}) {
    m7::Authority a(epoch);
    setup(a, syntheticKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = 200;
    Fixture *list = width == 0 ? group0 : width == 32 ? group32 : group48;
    int tiles = width * width * 2 / 512;
    for (int n = 0; n < tiles + 2; ++n) {
      check(a.issue(0, list[n].nonce, host_ms, 1000),
            "signed flow challenge issuance");
      nativeTransact(i, raw(list[n]));
      check(i.gate1Passed, "signed flow Gate1");
      if (n == 0)
        check(r.pending, "native Begin staging");
    }
    check(r.sink.commits == 1 && !r.pending && !strcmp(i.outcome, "COMMITTED"),
          "signed 0/32/48 native complete flow");
    check(bool(r.sink.image) == (width != 0), "sink image variant");
  }
  // Retained public mismatches have genuine proofs, then Gate2 denies with no
  // mutation.
  for (auto *f :
       {&operation_mismatch, &transaction_mismatch, &epoch_mismatch}) {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = 300;
    check(a.issue(0, f->nonce, host_ms, 1000), "mismatch challenge");
    nativeTransact(i, raw(*f));
    check(i.gate1Passed && i.bodyReads && r.mutations == 0 &&
              !strcmp(i.outcome, "GATE2"),
          "real proof then target/binary Gate2 mismatch");
  }
  for (auto kind : {"bad_signature", "wrong_key", "revoked", "disabled", "role",
                    "operation", "unknown", "expired", "partial", "trailing",
                    "digest", "magic", "header", "http10", "query", "alias"}) {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = 400;
    std::string k = kind, input = raw(begin);
    if (k != "unknown")
      check(a.issue(0, begin.nonce, host_ms, k == "expired" ? 1 : 1000),
            "adversarial challenge");
    if (k == "expired")
      ++host_ms;
    if (k == "revoked")
      a.state(0, true, true, true);
    if (k == "disabled")
      a.state(0, false, false, true);
    if (k == "role")
      a.state(0, true, false, false);
    if (k == "operation") {
      a = m7::Authority(epoch);
      uint8_t key[65];
      m7::unhex(retainedKey, key, 65);
      check(a.enroll("media-test", key, 4) &&
                a.issue(0, begin.nonce, host_ms, 1000),
            "operation-limited enrollment");
    }
    if (k == "wrong_key") {
      uint8_t key[65];
      m7::unhex(syntheticKey, key, 65);
      a = m7::Authority(epoch);
      check(a.enroll("media-test", key, 15) &&
                a.issue(0, begin.nonce, host_ms, 1000),
            "wrong public key provisioning");
    }
    if (k == "bad_signature") {
      auto p = input.find("Signature: sig1=:") + 17;
      input[p] = input[p] == 'A' ? 'B' : 'A';
    }
    if (k == "trailing")
      input += 'X';
    if (k == "digest")
      input.back() ^= 1;
    if (k == "magic")
      input[input.find("\r\n\r\n") + 4] = char(0xd3);
    if (k == "header")
      input.insert(input.find("\r\n\r\n") + 2, "Content-Length: 371\r\n");
    if (k == "http10")
      input.replace(input.find("HTTP/1.1"), 8, "HTTP/1.0");
    if (k == "query")
      input.insert(input.find(" HTTP/1.1"), "?x=1");
    if (k == "alias")
      input.replace(input.find("media"), 5, "%6dedia");
    if (k == "partial") {
      clearOwner();
      Peer p;
      input.pop_back();
      p.send(input);
      p.fin();
      arrival();
      for (int n = 0; n < 40; ++n)
        poll();
      check(!server.client() && i.bodyReads == 370 && !r.mutations,
            "partial FIN denied before state");
    } else
      nativeTransact(i, input);
    check(!r.mutations && !r.pending && !r.sink.commits,
          "adversarial no media mutation");
    if (k == "unknown" || k == "revoked" || k == "expired" || k == "role" ||
        k == "disabled" || k == "operation")
      check(!a.ecdsaCalls && !i.bodyReads && !i.bodyAllocations,
            "cheap denial zero ECDSA/body/allocation");
    if (k == "wrong_key" || k == "bad_signature")
      check(a.ecdsaCalls == 1 && !i.bodyReads && !i.bodyAllocations,
            "wrong proof no body allocation/read");
    if (k == "digest" || k == "magic" || k == "trailing")
      check(i.gate1Passed &&
                !strcmp(i.outcome, k == "trailing" ? "TRAILING" : "GATE2"),
            "post-proof Gate2/framing refusal");
  }
  // Absolute deadline and body lifecycle invalidation across incremental polls.
  for (bool wrap : {false, true}) {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = wrap ? UINT32_MAX - 100 : 100;
    auto start = host_ms;
    clearOwner();
    Peer p;
    p.send("POST /api/v2/bridge/media/begin/11223344556677880000000000000001 "
           "HTTP/1.1\r\nHost: tv.test\r\n");
    arrival();
    poll();
    poll();
    host_ms = start + 1999u;
    poll();
    check(bool(server.client()), "absolute1999 retain");
    host_ms = start + 2000u;
    poll();
    check(!server.client() && !i.bodyReads && !r.mutations,
          "absolute2000/wrap header deadline");
  }
  {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = 100;
    check(a.issue(0, begin.nonce, 100, 1000), "revocation receipt issue");
    clearOwner();
    Peer p;
    p.send(begin.header);
    arrival();
    for (int n = 0; n < 20 && !i.gate1Passed; ++n)
      poll();
    check(i.gate1Passed && !i.bodyReads,
          "headers-only proof consumes no TCP body");
    a.state(0, true, true, true);
    p.send(decode(begin.body));
    arrival();
    poll();
    check(!server.client() && !i.bodyReads && !r.mutations,
          "revoked after proof reads zero body");
  }
  // New return-to-owner boundary: stale authority/challenge never starts EC,
  // never allocates or reads a body, even if the peer already sent one.
  for (auto kind : {"revoke", "expire", "rotate", "epoch", "deadline"}) {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = 100;
    check(a.issue(0, begin.nonce, 100, 1000), "split-phase challenge");
    clearOwner();
    Peer p;
    p.send(begin.header + decode(begin.body));
    arrival();
    for (int n = 0; n < 30 && !i.needsProof(); ++n) poll();
    check(i.needsProof() && !i.bodyReads && !i.bodyAllocations && !a.ecdsaCalls,
          "parse returns with proof state and zero body/EC");
    std::string k(kind);
    if (k == "revoke") a.state(0, true, true, true);
    if (k == "expire") host_ms = 1100;
    if (k == "rotate") {
      uint8_t key[65];
      check(m7::unhex(retainedKey, key, 65) && a.rotate(0, key),
            "same-key split-phase rotation");
    }
    if (k == "epoch") a.reboot(epoch + 1);
    if (k == "deadline") host_ms = 2100;
    poll();
    check(!server.client() && !i.bodyReads && !i.bodyAllocations &&
              !a.ecdsaCalls && !r.mutations,
          "stale split-phase proof denied before EC/body/mutation");
  }
  // Profile 1.1 normalizations retain the original real signature base.
  for (int variant = 0; variant < 4; ++variant) {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = 100;
    check(a.issue(0, begin.nonce, 100, 1000), "profile1.1 challenge");
    auto input = raw(begin);
    if (variant == 0)
      input.replace(input.find("Host: tv.test"), 13, "hOsT:\t TV.TEST:80 \t");
    if (variant == 1) {
      input.replace(input.find("sig1=(\"@method\""), 15, "sig1=(  \"@method\"");
      input.replace(input.find(";alg="), 5, ";  alg=");
    }
    if (variant == 2)
      input.replace(input.find("Content-Type: "), 14, "Content-Type:\t");
    if (variant == 3) {
      auto pos = input.find("Signature: sig1=:") + 17;
      input.erase(pos + 86, 2);
    }
    nativeTransact(i, input);
    check(i.gate1Passed && r.pending,
          "native HTTP OWS authority SF spaces/raw signature normalization");
  }
  // Direct native authority final recheck + bounded issuer/reboot policy.
  {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    check(a.issue(0, begin.nonce, 0, 1000), "authority issue");
    m7::Ticket t;
    int slot = a.precheck("media-test", begin.nonce, epoch, 1, 0, t);
    check(slot >= 0, "native precheck");
    check(a.consume(slot, t, 1, 0) && !a.consume(slot, t, 1, 0),
          "single consume");
    check(!a.issue(0, begin.nonce, 0, 1000), "nonce never reissued");
    check(a.reboot(epoch + 1) && !a.reboot(epoch) && !a.admit(t, 1),
          "A B A and stale ticket denied");
    check(a.issue(0, begin.nonce, UINT32_MAX - 10, 30), "wrap challenge");
    check(a.precheck("media-test", begin.nonce, epoch + 1, 1, 19, t) < 0,
          "wrapped exact expiry");
  }
  {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    uint8_t hash[32], sig[64];
    m7::unhex(
        "398da6590952dbcf99eaba3ed1b01948db65bfaf1bd50162af70a5f4a38cddc4",
        hash, 32);
    const char *p = strstr(begin.header, "Signature: sig1=:") + 17;
    char encoded[89];
    memcpy(encoded, p, 88);
    encoded[88] = 0;
    check(m7::base64(encoded, sig, 64), "retained raw signature");
    check(a.issue(0, begin.nonce, 0, 1000), "final recheck challenge");
    m7::Ticket t;
    int slot = a.precheck("media-test", begin.nonce, epoch, 1, 0, t);
    check(a.proof(t, hash, sig),
          "real BearSSL signature before lifecycle race");
    check(a.state(0, false, false, true) && a.state(0, true, false, true) &&
              !a.consume(slot, t, 1, 0),
          "disable enable invalidates old proof");
    check(a.issue(0, tile.nonce, 0, 1000), "rotation challenge");
    slot = a.precheck("media-test", tile.nonce, epoch, 2, 0, t);
    uint8_t key[65];
    m7::unhex(retainedKey, key, 65);
    check(a.rotate(0, key) && !a.consume(slot, t, 2, 0),
          "same-key rotation revision invalidates proof");
    check(a.state(0, true, true, true) && !a.state(0, true, false, true),
          "terminal native revocation");
  }
  {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    uint8_t key[65];
    m7::unhex(retainedKey, key, 65);
    check(a.enroll("peer", key, 15) && a.enroll("third", key, 15),
          "fixed additional principal rows");
    check(a.issue(0, begin.nonce, 0, 10) && a.issue(0, tile.nonce, 0, 10) &&
              !a.issue(0, commit.nonce, 0, 10),
          "per-principal2 bounded cap");
    check(a.issue(1, commit.nonce, 0, 10) &&
              a.issue(1, operation_mismatch.nonce, 0, 10) &&
              !a.issue(2, transaction_mismatch.nonce, 0, 10),
          "global4 bounded cap");
    a.sweep(10);
    check(a.issue(2, transaction_mismatch.nonce, 10, 10) &&
              !a.issue(0, begin.nonce, 10, 10),
          "sweep frees capacity without nonce rollback");
    check(a.find("absent") < 0, "unknown principal has no allocated row");
  }
  // Idle partial media headers yield the real owner to ready legacy at >30ms.
  {
    m7::Authority a(epoch);
    setup(a, retainedKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = 0;
    clearOwner();
    Peer p;
    p.send("POST /api/v2/bridge/media/begin/11223344556677880000000000000001 "
           "HTTP/1.1\r\nHost: tv.test\r\n");
    arrival();
    poll();
    poll();
    Peer ready;
    ready.send(req("/api/v1/bridge/status", auth));
    arrival();
    host_ms = 30;
    poll();
    check(bool(server.client()), "media ready legacy exact30 retained");
    auto before = stops.load();
    host_ms = 31;
    poll();
    check(!server.client() && stops == before + 1 && !i.bodyReads &&
              !r.mutations,
          "media ready legacy31 one terminal close");
    poll();
    poll();
    check(status(ready.receive(), 200),
          "competing legacy actual parser/handler response");
  }
  // Stage/duplicate/ownership/abort/deadline/pointer move use the SAME native
  // Gate2/wire/receiver, with an explicit trusted public-test admission seam.
  {
    auto b = decode(group32[0].body);
    m7::Record rec;
    uint8_t tx[16];
    memcpy(tx, b.data() + 16, 16);
    m7::Receiver r;
    check(m7::wire(reinterpret_cast<const uint8_t *>(b.data()), b.size(), 1, tx,
                   epoch, rec) &&
              r.receive(rec, 0, UINT32_MAX - 100u),
          "direct Begin");
    auto *pointer = r.stagedPointer();
    for (int n = 1; n <= 4; ++n) {
      b = decode(group32[n].body);
      check(m7::wire(reinterpret_cast<const uint8_t *>(b.data()), b.size(), 2,
                     tx, epoch, rec) &&
                r.receive(rec, 0, 20),
            "direct native Tile");
      auto mutations = r.mutations;
      check(r.receive(rec, 0, 20) && !strcmp(r.outcome, "DUPLICATE") &&
                r.mutations == mutations,
            "identical duplicate no mutation");
      check(!r.receive(rec, 1, 20) && r.pending,
            "wrong principal cannot alter pending");
    }
    b = decode(group32[5].body);
    check(m7::wire(reinterpret_cast<const uint8_t *>(b.data()), b.size(), 3, tx,
                   epoch, rec) &&
              r.receive(rec, 0, 30) && r.sink.image.get() == pointer,
          "Commit moves original allocation no full-image copy");
    m7::Receiver timeout;
    b = decode(group32[0].body);
    m7::wire(reinterpret_cast<const uint8_t *>(b.data()), b.size(), 1, tx,
             epoch, rec);
    timeout.receive(rec, 0, UINT32_MAX - 100u);
    check(timeout.tick(7899) && timeout.pending, "8000 exact retained");
    check(!timeout.tick(7900) && !timeout.pending,
          "8001 wrapped absolute timeout");
  }
  // Signed Abort terminates an owned pending transaction, with Gate1/2.
  {
    m7::Authority a(epoch);
    setup(a, syntheticKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = 100;
    check(a.issue(0, group32[0].nonce, 100, 1000), "abort Begin challenge");
    nativeTransact(i, raw(group32[0]));
    check(a.issue(0, group32[6].nonce, 100, 1000), "abort challenge");
    nativeTransact(i, raw(group32[6]));
    check(!r.pending && !r.sink.image && !strcmp(i.outcome, "INTERRUPTED"),
          "signed Abort");
  }
  {
    m7::Authority a(epoch);
    setup(a, syntheticKey);
    m7::Receiver r;
    m7::Ingress i(a, r, "tv.test", clockNow);
    server.setOfflineMedia(&i);
    host_ms = 100;
    check(a.issue(0, group32[0].nonce, 100, 1000),
          "failed Gate2 preservation Begin");
    nativeTransact(i, raw(group32[0]));
    auto before = r.mutations;
    auto *pointer = r.stagedPointer();
    check(a.issue(0, group32[1].nonce, 100, 1000),
          "failed Gate2 preservation Tile");
    auto altered = raw(group32[1]);
    altered.back() ^= 1;
    nativeTransact(i, altered);
    check(r.pending && r.mutations == before && r.stagedPointer() == pointer &&
              !strcmp(i.outcome, "GATE2"),
          "failed authenticated Gate2 preserves existing staging");
  }
  server.setOfflineMedia(nullptr);
  clearOwner();
  server.getServer().close();
  check(contexts == destroyed && liveSockets == 0,
        "native composition balanced contexts zero descriptors");
  std::cout << "{\"legacy_checks\":" << legacyChecks << ",\"checks\":" << checks
            << ",\"failed\":" << failed
            << ",\"live_descriptors\":" << liveSockets
            << ",\"contexts_created\":" << contexts
            << ",\"contexts_destroyed\":" << destroyed
            << ",\"authority_bytes\":" << sizeof(m7::Authority)
            << ",\"ingress_bytes\":" << sizeof(m7::Ingress)
            << ",\"receiver_bytes\":" << sizeof(m7::Receiver)
            << ",\"sha_context_bytes\":" << sizeof(br_sha256_context)
            << ",\"max_media_poll_bytes\":" << nativeMaxReads
            << ",\"worst_media_poll_us\":" << nativeWorstUs << "}\n";
  return failed ? 1 : 0;
}
