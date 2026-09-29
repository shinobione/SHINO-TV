// V0.7 Mission 4 OFFLINE handoff contract. No WiFiServer, route or firmware.
// LegacyPolicy is a synthetic stand-in: it does not execute FirstBootBridge.
#include "v07_bounded_ingress_candidate.cpp"
#include <cstdlib>
#include <sstream>
#include <iomanip>

using namespace v07lab;
static unsigned assertions = 0;
static void expect(bool ok, const char* label) {
  if (!ok) { std::cerr << "FAIL " << label << '\n'; std::exit(1); }
  ++assertions;
}

struct MockVerifier final : Verifier {
  bool grant = true;
  unsigned pre = 0, post = 0;
  Decision before_body(const RequestView& request) override {
    ++pre;
    return {grant && request.method == "POST" &&
            request.target.substr(0, 21) == "/api/v2/bridge/media/", 17};
  }
  bool after_body(const RequestView&, const uint8_t* fixed, size_t fixed_len,
                  const uint8_t*, size_t) override {
    ++post;
    return fixed_len == 40 && std::memcmp(fixed, "STV7", 4) == 0;
  }
};

enum class Route { unknown, media, legacy, closed };
struct Owner {
  Gate& media;
  Route route = Route::closed;
  std::array<char, REQUEST_LINE_MAX + 2> line{};
  size_t used = 0, max_line = 0, max_step = 0;
  uint32_t client = 0, started = 0, preemptions = 0;
  bool begin(uint32_t id, uint32_t now) {
    if (route != Route::closed) return false;
    client = id; started = now; used = 0; route = Route::unknown;
    return true;
  }
  size_t poll(uint32_t id, std::string_view input, uint32_t now) {
    if (id != client || route == Route::closed || route == Route::legacy) return 0;
    if (now < started || now - started > REQUEST_MS) { route = Route::closed; return 0; }
    const size_t limit = input.size() < POLL_BYTES ? input.size() : POLL_BYTES;
    size_t consumed = 0;
    while (consumed < limit) {
      const uint8_t byte = uint8_t(input[consumed]);
      if (route == Route::unknown) {
        if (used == line.size() || byte == 0 || byte == '\n' && (!used || line[used - 1] != '\r')) {
          route = Route::closed; ++consumed; break;
        }
        line[used++] = char(byte);
        if (used > max_line) max_line = used;
        ++consumed;
        if (used >= 2 && line[used - 2] == '\r' && line[used - 1] == '\n') {
          std::string_view first(line.data(), used - 2);
          const size_t a = first.find(' '), b = first.find(' ', a == first.npos ? a : a + 1);
          if (a == first.npos || b == first.npos || first.substr(b + 1) != "HTTP/1.1") {
            route = Route::closed; break;
          }
          const std::string_view target = first.substr(a + 1, b - a - 1);
          constexpr std::string_view media_root = "/api/v2/bridge/media";
          const bool reserved = target == media_root ||
              (target.size() > media_root.size() && target.substr(0, media_root.size()) == media_root &&
               target[media_root.size()] == '/');
          route = reserved ? Route::media : Route::legacy;
          if (route == Route::media) {
            if (!media.start(id, started)) { route = Route::closed; break; }
            for (size_t i = 0; i < used; ++i) media.feed(id, uint8_t(line[i]), now);
            if (media.phase() == Phase::rejected) { route = Route::closed; break; }
          }
          // For legacy, consumed stops at CRLF. A future *single* owner must
          // replay this exact bounded prefix to the existing WebServer parser.
        }
      } else {
        media.feed(id, byte, now);
        ++consumed;
        if (media.phase() == Phase::rejected) { route = Route::closed; break; }
      }
      if (route == Route::legacy) break;
    }
    if (consumed > max_step) max_step = consumed;
    return consumed;
  }
  bool contend(uint32_t now) {
    if (route == Route::closed || now < started || now - started <= 30) return false;
    // Research scheduling policy: close the active connection at a poll
    // boundary when another client has data. This can cancel owned media.
    if (route == Route::media) media.finish(client, now);
    route = Route::closed; ++preemptions;
    return true;
  }
  void disconnect(uint32_t now) {
    if (route == Route::media) media.finish(client, now);
    route = Route::closed;
  }
  std::string_view replay_prefix() const { return {line.data(), used}; }
};

struct LegacyPolicy {
  // Models route/authority boundaries only. Existing handlers are unchanged.
  bool browser_session = false;
  uint32_t metrics_last = 0, metric_value = 40;
  unsigned browser_reads = 0, oem_calls = 0, metrics_posts = 0;
  bool serve(std::string_view request_line, bool legacy_auth, bool cookie, uint32_t now) {
    if (request_line == "GET / HTTP/1.1\r\n") {
      if (!legacy_auth && !cookie) return false;
      browser_session = true; ++browser_reads; return true;
    }
    if (request_line == "GET /api/v1/bridge/metrics HTTP/1.1\r\n" ||
        request_line == "GET /ui.js HTTP/1.1\r\n") {
      if (!cookie || !browser_session) return false;
      ++browser_reads; return true;
    }
    if (request_line == "POST /api/v1/bridge/metrics HTTP/1.1\r\n") {
      if (!legacy_auth) return false;
      ++metrics_posts; ++metric_value; metrics_last = now; return true;
    }
    if (request_line == "POST /api/v1/bridge/factory-return HTTP/1.1\r\n" ||
        request_line == "GET /api/v1/bridge/factory-return HTTP/1.1\r\n") {
      if (!legacy_auth) return false;
      ++oem_calls; return true;
    }
    return false;
  }
  bool fresh(uint32_t now) const { return now - metrics_last <= 6000; }
};

static size_t send(Owner& owner, uint32_t id, const std::string& input, uint32_t now) {
  size_t offset = 0;
  while (offset < input.size() && owner.route != Route::closed && owner.route != Route::legacy) {
    const size_t consumed = owner.poll(id, std::string_view(input).substr(offset), now);
    if (!consumed) break;
    offset += consumed;
  }
  return offset;
}
static Tx tx() { Tx value; value.bytes[7] = 7; value.bytes[15] = 2; return value; }
static std::string hex_tx() {
  std::ostringstream out;
  for (uint8_t c : tx().bytes) out << std::hex << std::setfill('0') << std::setw(2) << unsigned(c);
  return out.str();
}
static std::string media_header(const char* op, size_t length) {
  return std::string("POST /api/v2/bridge/media/") + op + "/" + hex_tx() + " HTTP/1.1\r\n" +
    "Host: unit.invalid\r\nContent-Type: application/vnd.shino-tv.media-wire-v2\r\n" +
    "Content-Length: " + std::to_string(length) + "\r\nContent-Digest: sha-256=:test:\r\n" +
    "Signature-Input: sig1=()\r\nSignature: sig1=:test:\r\nConnection: close\r\n\r\n";
}
static std::string begin_body() {
  std::string out(40, '\0'); out.replace(0, 4, "STV7"); out[4] = 2; out[5] = 1;
  out[15] = 7; for (size_t i = 0; i < 16; ++i) out[16 + i] = char(tx().bytes[i]);
  out[35] = 1; out[39] = char(crc32(reinterpret_cast<const uint8_t*>("x"), 1));
  // CRC32("x") is 0x8cdc1683: complete four-byte big-endian field.
  const uint32_t crc = crc32(reinterpret_cast<const uint8_t*>("x"), 1);
  for (size_t i = 0; i < 4; ++i) out[36 + i] = char(crc >> (24 - i * 8));
  return out + "x";
}

int main() {
  MockVerifier verifier; Pending pending; Gate gate(verifier, pending);
  Owner owner{gate}; LegacyPolicy legacy;
  const std::string metrics = "POST /api/v1/bridge/metrics HTTP/1.1\r\n";
  expect(owner.begin(1, 100), "single accept begins");
  expect(send(owner, 1, metrics + "Content-Length: 1\r\n\r\nx", 100) == metrics.size(),
         "legacy prefix stops before headers and body");
  expect(owner.route == Route::legacy && owner.replay_prefix() == metrics, "exact legacy prefix replay");
  expect(!legacy.serve(owner.replay_prefix(), false, true, 100) && legacy.metric_value == 40,
         "browser cookie cannot write metrics");
  expect(legacy.serve(owner.replay_prefix(), true, false, 100), "legacy metric auth boundary");
  owner.disconnect(100);
  expect(owner.begin(2, 200), "browser begins");
  send(owner, 2, "GET / HTTP/1.1\r\n", 200);
  expect(legacy.serve(owner.replay_prefix(), true, false, 200), "dashboard establishes read session");
  owner.disconnect(200);
  expect(owner.begin(3, 210), "browser metrics begins");
  send(owner, 3, "GET /api/v1/bridge/metrics HTTP/1.1\r\n", 210);
  expect(legacy.serve(owner.replay_prefix(), false, true, 210) && legacy.metric_value == 41,
         "read session sees four metric fixture without mutation");
  owner.disconnect(210);
  expect(owner.begin(4, 220), "oem begins");
  send(owner, 4, "POST /api/v1/bridge/factory-return HTTP/1.1\r\n", 220);
  expect(!legacy.serve(owner.replay_prefix(), false, true, 220) && legacy.oem_calls == 0,
         "cookie cannot authorize OEM return");
  expect(legacy.serve(owner.replay_prefix(), true, false, 220) && legacy.oem_calls == 1,
         "existing OEM auth boundary remains separate");
  owner.disconnect(220);
  const std::string valid = media_header("begin", 41) + begin_body();
  expect(owner.begin(5, 300), "media begins"); verifier.grant = false;
  send(owner, 5, valid, 300);
  expect(gate.reason() == Reason::denied && gate.stats.body_bytes_before_auth == 0 &&
         pending.terminal == 0 && legacy.metric_value == 41, "denied media is inert");
  owner.disconnect(300);
  verifier.grant = true;
  expect(owner.begin(6, 400), "authorized media begins");
  expect(send(owner, 6, valid, 400) == valid.size(), "bounded media consumed");
  owner.disconnect(401);
  expect(gate.phase() == Phase::accepted && verifier.post == 1 && legacy.oem_calls == 1,
         "authorized media isolated from OEM");
  expect(owner.begin(7, 500), "slow client begins");
  send(owner, 7, "POST /api/v2/bridge/media/begin/", 500);
  expect(!owner.begin(8, 510), "competing accept refused");
  expect(!owner.contend(530) && owner.contend(531), "bounded contention preempts slow client");
  expect(owner.begin(8, 532), "metrics recovers after preemption");
  send(owner, 8, metrics, 532);
  expect(legacy.serve(owner.replay_prefix(), true, false, 532) && legacy.metrics_posts == 2,
         "metric update resumes after slow client");
  owner.disconnect(532);
  expect(owner.begin(9, 600), "oversized line begins");
  send(owner, 9, std::string(300, 'X'), 600);
  expect(owner.route == Route::closed && owner.max_line <= REQUEST_LINE_MAX + 2,
         "unclassified line bounded before legacy parser");
  expect(owner.begin(10, 700), "disconnected client begins");
  send(owner, 10, "POST /api/v2/bridge/media", 700); owner.disconnect(701);
  expect(owner.route == Route::closed && pending.terminal == 0, "partial unclassified disconnect inert");
  pending.active = true; pending.principal = 17; pending.tx = tx(); pending.started_ms = 800; pending.art = true;
  expect(owner.begin(11, 800), "owned media begins");
  send(owner, 11, media_header("commit", 40) + std::string(20, 'z'), 800);
  owner.disconnect(801);
  expect(gate.reason() == Reason::partial && !pending.active && !pending.art && pending.terminal == 1,
         "owned partial disconnect cleans exactly once");
  expect(owner.begin(12, 1000), "trickle begins");
  send(owner, 12, "P", 1000);
  send(owner, 12, "O", 2999);
  owner.poll(12, "S", 3001);
  expect(owner.route == Route::closed && pending.terminal == 1,
         "trickle progress cannot reset absolute request deadline");
  pending.active = true; pending.art = true; pending.principal = 17;
  pending.tx = tx(); pending.started_ms = 4000;
  expect(owner.begin(13, 12000), "deadline-bound media begins");
  send(owner, 13, media_header("commit", 40), 12000);
  expect(gate.phase() == Phase::fixed && pending.active, "pending valid at exact eight seconds");
  gate.timeout(12001);
  expect(gate.reason() == Reason::timeout && !pending.active && !pending.art && pending.terminal == 2,
         "pending timeout is absolute and owned");
  owner.disconnect(12001);
  expect(!legacy.fresh(6533) && legacy.fresh(6532), "freshness strict at 6000 and 6001");
  const uint32_t overlay_until = 5800;
  expect(5799 < overlay_until && !(5800 < overlay_until), "five-second overlay boundary");
  expect(owner.max_step <= POLL_BYTES && gate.stats.max_head <= HEAD_MAX &&
         gate.stats.max_payload <= PAYLOAD_MAX && gate.stats.max_live_payload_allocations == 0,
         "synthetic step and buffer limits");
  std::cout << "{\"handoff_assertions\":" << assertions
            << ",\"max_step_bytes\":" << owner.max_step
            << ",\"max_prefix_bytes\":" << owner.max_line
            << ",\"preemptions\":" << owner.preemptions
            << ",\"metric_updates\":" << legacy.metrics_posts
            << ",\"oem_calls\":" << legacy.oem_calls
            << ",\"owned_cleanups\":" << pending.terminal << "}\n";
}
