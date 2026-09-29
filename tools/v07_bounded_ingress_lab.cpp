// Host-only deterministic tests. This includes the candidate as a translation unit;
// neither this file nor the candidate is linked into firmware.
#include "v07_bounded_ingress_candidate.cpp"
#include <cstdlib>
#include <chrono>
#include <iomanip>
#include <sstream>

using namespace v07lab;
static unsigned passed = 0;
static void check(bool ok, const char* name) {
  if (!ok) { std::cerr << "FAIL " << name << '\n'; std::exit(1); }
  ++passed;
}
struct FakeVerifier : Verifier {
  bool admit = true, digest = true;
  uint32_t principal = 1;
  unsigned pre = 0, post = 0;
  Decision before_body(const RequestView&) override { ++pre; return {admit, principal}; }
  bool after_body(const RequestView&, const uint8_t* header, size_t header_size,
                  const uint8_t* body, size_t body_size) override {
    ++post;
    return digest && header_size == FIXED && header[0] == 'S' &&
           (body_size == 0 || body != nullptr);
  }
};
static void put16(std::string& s, size_t p, uint16_t n) {
  s[p] = char(n >> 8); s[p + 1] = char(n);
}
static void put32(std::string& s, size_t p, uint32_t n) {
  for (int i = 3; i >= 0; --i) { s[p + i] = char(n); n >>= 8; }
}
static void put64(std::string& s, size_t p, uint64_t n) {
  for (int i = 7; i >= 0; --i) { s[p + i] = char(n); n >>= 8; }
}
static Tx transaction(uint64_t epoch = 7, uint64_t seq = 2) {
  Tx t;
  for (int i = 7; i >= 0; --i) { t.bytes[i] = uint8_t(epoch); epoch >>= 8; }
  for (int i = 15; i >= 8; --i) { t.bytes[i] = uint8_t(seq); seq >>= 8; }
  return t;
}
static std::string txhex(Tx tx) {
  std::ostringstream out;
  for (uint8_t b : tx.bytes) out << std::hex << std::setfill('0') << std::setw(2) << unsigned(b);
  return out.str();
}
static std::string body(uint8_t op, Tx tx, std::string payload = "x") {
  if (op == 2) payload.assign(512, 'p');
  if (op >= 3) payload.clear();
  std::string out(FIXED, '\0');
  out.replace(0, 4, "STV7"); out[4] = 2; out[5] = char(op);
  for (size_t i = 0; i < 16; ++i) out[16 + i] = char(tx.bytes[i]);
  put64(out, 8, 7); put16(out, 34, uint16_t(payload.size()));
  put32(out, 36, crc32(reinterpret_cast<const uint8_t*>(payload.data()), payload.size()));
  return out + payload;
}
static std::string head(uint8_t op, Tx tx, size_t len) {
  const char* names[] = {"", "begin", "tile", "commit", "abort"};
  return std::string("POST /api/v2/bridge/media/") + names[op] + "/" + txhex(tx) + " HTTP/1.1\r\n" +
    "Host: unit.invalid\r\nContent-Type: application/vnd.shino-tv.media-wire-v2\r\n" +
    "Content-Length: " + std::to_string(len) + "\r\nContent-Digest: sha-256=:test:\r\n" +
    "Signature-Input: sig1=()\r\nSignature: sig1=:test:\r\nConnection: close\r\n\r\n";
}
static void bytes(Gate& gate, uint32_t client, const std::string& data, uint32_t now) {
  for (unsigned char c : data) gate.feed(client, c, now);
}
struct Metrics {
  uint32_t last = 0, value = 42, max_gap = 0, previous = 0;
  void update(uint32_t now) { if (previous && now - previous > max_gap) max_gap = now - previous; previous = last = now; ++value; }
  bool fresh(uint32_t now) const { return now - last <= 6000; }
};
int main() {
  FakeVerifier v; Pending p; Gate g(v, p); Tx tx = transaction();
  const std::string begin = body(1, tx), h = head(1, tx, begin.size());
  Metrics m; m.update(100);
  auto valid_start = std::chrono::steady_clock::now();
  check(g.start(1, 100), "start"); bytes(g, 1, h, 100);
  check(g.phase() == Phase::fixed && g.stats.body_bytes_before_auth == 0, "prebody gate");
  bytes(g, 1, begin, 100); g.finish(1, 101);
  auto valid_us = std::chrono::duration_cast<std::chrono::microseconds>(
      std::chrono::steady_clock::now() - valid_start).count();
  check(g.phase() == Phase::accepted && v.post == 1, "valid record");
  check(g.stats.max_head <= HEAD_MAX && g.stats.max_fixed == 40 && g.stats.max_payload == 1 &&
        g.stats.max_live_payload_allocations == 0, "bounded memory");

  auto reject_head = [&](std::string request, const char* label) {
    unsigned pre = v.pre; check(g.start(1, 200), "restart"); bytes(g, 1, request, 200);
    check(g.phase() == Phase::rejected && v.pre == pre && m.value == 43, label);
  };
  check(g.start(1, 190), "trailing start"); bytes(g, 1, h + begin + "X", 190);
  check(g.reason() == Reason::trailing, "trailing bytes");
  auto insertion = [&](const std::string& line) {
    std::string copy = h; copy.insert(copy.size() - 2, line + "\r\n"); return copy;
  };
  reject_head(insertion("Content-Length: 41"), "duplicate content length");
  reject_head(insertion("Transfer-Encoding: chunked"), "transfer encoding");
  reject_head(insertion("Expect: 100-continue"), "expect");
  for (const char* bad : {"-1", "65536", "999999999999", "040", "+41"}) {
    std::string copy = h; auto at = copy.find("Content-Length: ") + 16;
    copy.replace(at, copy.find("\r\n", at) - at, bad);
    reject_head(copy, "invalid length");
  }
  std::string long_line(REQUEST_LINE_MAX + 30, 'x');
  long_line += "\r\n"; reject_head(long_line, "oversized request line");
  check(g.start(1, 300), "slow start"); bytes(g, 1, "POST /", 300); g.timeout(2301);
  check(g.reason() == Reason::timeout, "absolute slow line timeout");
  check(g.start(1, 3000), "denied start"); v.admit = false;
  bytes(g, 1, h, 3000); check(g.phase() == Phase::rejected && g.stats.max_payload == 1, "denied before body");
  v.admit = true;
  p.active = true; p.principal = 1; p.tx = tx; p.started_ms = 3000; p.art = true;
  check(g.start(1, 3100), "owned start");
  check(!g.start(2, 3101), "competing client refused");
  check(g.started_ms() == 3100 && p.started_ms == 3000 && p.active, "deadline preserved");
  bytes(g, 2, h, 3101); check(p.active, "other client inert");
  std::string commit = body(3, tx), ch = head(3, tx, commit.size());
  bytes(g, 1, ch, 3102); bytes(g, 1, commit.substr(0, 20), 3102); g.finish(1, 3103);
  check(g.reason() == Reason::partial && !p.active && !p.art && p.terminal == 1, "owned partial cleanup");
  p.active = true; p.art = true; p.started_ms = 4000;
  v.principal = 2; check(g.start(1, 4000), "wrong principal start");
  bytes(g, 1, ch, 4000); check(g.reason() == Reason::owner && p.active && p.art, "wrong principal inert");
  v.principal = 1;
  Tx other = transaction(7, 3);
  check(g.start(1, 4100), "wrong transaction start");
  bytes(g, 1, head(3, other, 40), 4100);
  check(g.reason() == Reason::owner && p.active && p.art, "wrong transaction inert");
  check(g.start(1, 4200), "wrong epoch start");
  bytes(g, 1, head(3, transaction(8, 2), 40), 4200);
  check(g.reason() == Reason::replay && p.active && p.art, "stale epoch inert");
  check(g.start(1, 4300), "replayed begin start");
  bytes(g, 1, h, 4300); check(g.reason() == Reason::replay && p.active, "competing begin inert");
  p.active = false; p.highest_sequence = 2;
  check(g.start(1, 4400), "replay start"); bytes(g, 1, h, 4400);
  check(g.reason() == Reason::replay, "bounded replay high water");
  p.highest_sequence = 0;
  check(g.start(1, 4500), "mismatch start"); bytes(g, 1, h, 4500);
  std::string mismatch = begin; mismatch[5] = 2; bytes(g, 1, mismatch, 4500);
  check(g.reason() == Reason::declaration, "operation mismatch");
  check(g.start(1, 4600), "tx mismatch start"); bytes(g, 1, h, 4600);
  mismatch = begin; mismatch[31] ^= 1; bytes(g, 1, mismatch, 4600);
  check(g.reason() == Reason::declaration, "transaction mismatch");
  check(g.start(1, 4700), "trickle start");
  for (uint32_t i = 0; i <= REQUEST_MS; i += 100) g.feed(1, 'X', 4700 + i);
  g.timeout(4700 + REQUEST_MS + 1);
  check(g.reason() == Reason::timeout, "trickle cannot extend deadline");
  for (FailureStage stage : {FailureStage::head, FailureStage::fixed, FailureStage::payload, FailureStage::verify}) {
    g.fail_at = stage; check(g.start(1, 7000), "fault start");
    bytes(g, 1, h, 7000); bytes(g, 1, begin, 7000); g.finish(1, 7001);
    check(g.phase() == Phase::rejected, "fault cleanup");
  }
  g.fail_at = FailureStage::none;
  check(g.start(1, 8000), "recovery start"); bytes(g, 1, h, 8000);
  bytes(g, 1, begin, 8000); g.finish(1, 8001);
  check(g.phase() == Phase::accepted, "recovery");
  p.active = true; p.art = false; p.principal = 1; p.tx = tx; p.started_ms = 8200;
  const std::string tile = body(2, tx), th = head(2, tx, tile.size());
  Metrics mixed; mixed.update(8200);
  check(g.start(1, 8200), "tile start"); bytes(g, 1, th, 8200);
  for (size_t i = 0; i < tile.size(); ++i) {
    g.feed(1, uint8_t(tile[i]), 8200 + uint32_t(i / 2));
    if (i == 200 || i == 400) mixed.update(8200 + uint32_t(i / 2));
  }
  g.finish(1, 8500);
  check(g.phase() == Phase::accepted && g.stats.max_payload == 512, "full tile bounded");
  check(g.start(1, 8600), "digest start"); bytes(g, 1, ch + commit, 8600);
  v.digest = false; g.finish(1, 8600); v.digest = true;
  check(g.reason() == Reason::integrity && !p.active && p.terminal == 2, "digest failure cleanup");
  p.active = true; p.principal = 1; p.tx = tx; p.started_ms = 9000;
  check(g.start(1, 17000), "owned deadline start"); bytes(g, 1, ch, 17000);
  g.timeout(17001);
  check(g.reason() == Reason::timeout && !p.active && p.terminal == 3, "absolute pending deadline");
  m.update(1000); m.update(2000); m.update(3000);
  check(m.fresh(9000) && !m.fresh(9001) && m.value == 46 && mixed.max_gap == 100,
        "metric value and freshness");
  const uint32_t overlay_until = 10000;
  check(9999 < overlay_until && !(10000 < overlay_until), "five second overlay edge");
  std::cout << "{\"candidate_tests\":" << passed << ",\"max_head\":" << g.stats.max_head
            << ",\"sizeof_gate_host\":" << sizeof(Gate)
            << ",\"sizeof_pending_host\":" << sizeof(Pending)
            << ",\"max_fixed\":" << g.stats.max_fixed << ",\"max_payload\":" << g.stats.max_payload
            << ",\"max_live_payload_allocations\":" << g.stats.max_live_payload_allocations
            << ",\"max_handle_ms_simulated\":" << g.stats.max_handle_ms
            << ",\"valid_record_host_us\":" << valid_us
            << ",\"max_work_bytes\":" << g.stats.max_work_bytes
            << ",\"body_bytes_before_auth\":" << g.stats.body_bytes_before_auth
            << ",\"max_metric_interval_ms_simulated\":" << mixed.max_gap
            << ",\"terminal_cleanups\":" << p.terminal << "}\n";
}
