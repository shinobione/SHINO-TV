// V0.7 OFFLINE research candidate. No socket, firmware include, route or crypto.
// All request storage inside Gate is fixed. The verifier is an injected interface.
#include <array>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace v07lab {
constexpr size_t HEAD_MAX = 1024, LINE_MAX = 256, REQUEST_LINE_MAX = 128;
constexpr size_t FIELD_MAX = 12, FIXED = 40, PAYLOAD_MAX = 512, BODY_MAX = 552;
constexpr uint32_t REQUEST_MS = 2000, TRANSACTION_MS = 8000;
constexpr size_t POLL_BYTES = 64;

enum class Phase { idle, head, fixed, payload, end, accepted, rejected };
enum class Reason { none, busy, limit, syntax, framing, denied, replay, owner,
                    declaration, partial, trailing, timeout, injected, integrity };
enum class FailureStage { none, head, fixed, payload, verify };

struct Tx { std::array<uint8_t, 16> bytes{}; bool operator==(const Tx& b) const { return bytes == b.bytes; } };
struct RequestView {
  std::string_view method, target, host, content_digest, signature_input, signature;
  Tx tx{};
  uint64_t epoch = 0, sequence = 0;
  uint8_t operation = 0;
  uint16_t content_length = 0;
};
struct Decision { bool verified = false; uint32_t principal = 0; };
struct Verifier {
  virtual ~Verifier() = default;
  // Contract only: real implementation must verify RFC 9421 profile on the
  // actual method/target/Host and the covered RFC 9530 Content-Digest.
  virtual Decision before_body(const RequestView&) = 0;
  virtual bool after_body(const RequestView&, const uint8_t*, size_t,
                          const uint8_t*, size_t) = 0;
};
struct Pending {
  bool active = false, art = false;
  uint32_t principal = 0, terminal = 0;
  uint64_t epoch = 7, highest_sequence = 0;
  Tx tx{};
  uint32_t started_ms = 0;
};
struct Stats {
  size_t max_head = 0, max_fixed = 0, max_payload = 0;
  size_t max_live_payload_allocations = 0; // fixed arrays: always zero
  uint32_t max_handle_ms = 0, max_work_bytes = 0;
  uint32_t body_bytes_before_auth = 0, verifier_calls = 0;
};

static uint64_t be64(const uint8_t* p) {
  uint64_t result = 0;
  for (unsigned i = 0; i < 8; ++i) result = (result << 8) | p[i];
  return result;
}
static uint16_t be16(const uint8_t* p) { return static_cast<uint16_t>((p[0] << 8) | p[1]); }
static uint32_t be32(const uint8_t* p) {
  return (uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) | (uint32_t(p[2]) << 8) | p[3];
}
static uint32_t crc32(const uint8_t* data, size_t size) {
  uint32_t crc = 0xffffffffu;
  for (size_t i = 0; i < size; ++i) {
    crc ^= data[i];
    for (unsigned b = 0; b < 8; ++b) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}
static bool ci_equal(std::string_view a, std::string_view b) {
  if (a.size() != b.size()) return false;
  for (size_t i = 0; i < a.size(); ++i) {
    char c = a[i], d = b[i];
    if (c >= 'A' && c <= 'Z') c += 32;
    if (d >= 'A' && d <= 'Z') d += 32;
    if (c != d) return false;
  }
  return true;
}
static int hex(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

class Gate {
 public:
  Gate(Verifier& verifier, Pending& pending) : verifier_(verifier), pending_(pending) {}
  Stats stats{};
  FailureStage fail_at = FailureStage::none;
  Phase phase() const { return phase_; }
  Reason reason() const { return reason_; }
  const RequestView& request() const { return request_; }
  uint32_t started_ms() const { return started_; }

  bool start(uint32_t client, uint32_t now) {
    if (phase_ == Phase::head || phase_ == Phase::fixed || phase_ == Phase::payload || phase_ == Phase::end) {
      reason_ = Reason::busy;
      return false;
    }
    phase_ = Phase::head; reason_ = Reason::none; client_ = client; started_ = now;
    head_used_ = fixed_used_ = payload_used_ = line_used_ = lines_ = 0;
    work_bytes_ = 0;
    owned_ = authorized_ = false; request_ = RequestView{};
    return true;
  }

  void feed(uint32_t client, uint8_t byte, uint32_t now) {
    if (client != client_ || phase_ == Phase::idle || phase_ == Phase::rejected || phase_ == Phase::accepted) return;
    if (phase_ == Phase::end) { reject(Reason::trailing, now); return; }
    if (expired(now)) { reject(Reason::timeout, now); return; }
    if (++work_bytes_ > HEAD_MAX + BODY_MAX) { reject(Reason::limit, now); return; }
    stats.max_work_bytes = work_bytes_ > stats.max_work_bytes ? work_bytes_ : stats.max_work_bytes;
    if (phase_ == Phase::head) {
      if (fail_at == FailureStage::head) { reject(Reason::injected, now); return; }
      if (head_used_ == HEAD_MAX) { reject(Reason::limit, now); return; }
      if (byte == 0 || (byte < 32 && byte != '\r' && byte != '\n') || byte == 127 ||
          (byte == '\n' && (head_used_ == 0 || head_[head_used_ - 1] != '\r')) ||
          (head_used_ && head_[head_used_ - 1] == '\r' && byte != '\n')) {
        reject(Reason::syntax, now); return;
      }
      head_[head_used_++] = static_cast<char>(byte);
      if (byte == '\n') { line_used_ = 0; ++lines_; }
      else if (++line_used_ > (lines_ ? LINE_MAX : REQUEST_LINE_MAX) + 2 || lines_ > FIELD_MAX + 1) {
        reject(Reason::limit, now); return;
      }
      if (head_used_ > stats.max_head) stats.max_head = head_used_;
      if (head_used_ >= 4 && std::memcmp(head_.data() + head_used_ - 4, "\r\n\r\n", 4) == 0) {
        if (!parse_head()) { reject(Reason::framing, now); return; }
        if (pending_.epoch != request_.epoch) { reject(Reason::replay, now); return; }
        if (request_.operation == 1) {
          if (pending_.active || request_.sequence <= pending_.highest_sequence) {
            reject(Reason::replay, now); return;
          }
        }
        ++stats.verifier_calls;
        decision_ = verifier_.before_body(request_);
        if (!decision_.verified || decision_.principal == 0) { reject(Reason::denied, now); return; }
        authorized_ = true;
        owned_ = pending_.active && pending_.tx == request_.tx && pending_.principal == decision_.principal;
        if (request_.operation != 1 && !owned_) { reject(Reason::owner, now); return; }
        phase_ = Phase::fixed;
      }
      return;
    }
    if (!authorized_) { ++stats.body_bytes_before_auth; reject(Reason::denied, now); return; }
    if (phase_ == Phase::fixed) {
      if (fail_at == FailureStage::fixed) { reject(Reason::injected, now); return; }
      fixed_[fixed_used_++] = byte;
      if (fixed_used_ > stats.max_fixed) stats.max_fixed = fixed_used_;
      if (fixed_used_ == FIXED) {
        if (!check_fixed()) { reject(Reason::declaration, now); return; }
        phase_ = expected_payload_ ? Phase::payload : Phase::end;
      }
      return;
    }
    if (fail_at == FailureStage::payload) { reject(Reason::injected, now); return; }
    if (payload_used_ == PAYLOAD_MAX) { reject(Reason::limit, now); return; }
    payload_[payload_used_++] = byte;
    if (payload_used_ > stats.max_payload) stats.max_payload = payload_used_;
    if (payload_used_ == expected_payload_) phase_ = Phase::end;
  }

  void finish(uint32_t client, uint32_t now) {
    if (client != client_ || phase_ == Phase::idle || phase_ == Phase::rejected || phase_ == Phase::accepted) return;
    if (expired(now)) { reject(Reason::timeout, now); return; }
    if (phase_ != Phase::end) { reject(Reason::partial, now); return; }
    if (crc32(payload_.data(), payload_used_) != expected_crc_) {
      reject(Reason::integrity, now); return;
    }
    if (fail_at == FailureStage::verify ||
        !verifier_.after_body(request_, fixed_.data(), FIXED, payload_.data(), payload_used_)) {
      reject(Reason::integrity, now); return;
    }
    phase_ = Phase::accepted;
    record_duration(now);
  }

  void timeout(uint32_t now) {
    if (phase_ == Phase::head || phase_ == Phase::fixed || phase_ == Phase::payload || phase_ == Phase::end)
      if (expired(now)) reject(Reason::timeout, now);
  }

 private:
  Verifier& verifier_;
  Pending& pending_;
  std::array<char, HEAD_MAX> head_{};
  std::array<uint8_t, FIXED> fixed_{};
  std::array<uint8_t, PAYLOAD_MAX> payload_{};
  RequestView request_{};
  Decision decision_{};
  Phase phase_ = Phase::idle;
  Reason reason_ = Reason::none;
  uint32_t client_ = 0, started_ = 0, work_bytes_ = 0;
  size_t head_used_ = 0, fixed_used_ = 0, payload_used_ = 0, expected_payload_ = 0;
  size_t line_used_ = 0, lines_ = 0;
  uint32_t expected_crc_ = 0;
  bool authorized_ = false, owned_ = false;

  bool expired(uint32_t now) const {
    if (now < started_ || now - started_ > REQUEST_MS) return true;
    return owned_ && (now < pending_.started_ms || now - pending_.started_ms > TRANSACTION_MS);
  }
  void record_duration(uint32_t now) {
    uint32_t duration = now - started_;
    if (duration > stats.max_handle_ms) stats.max_handle_ms = duration;
  }
  void reject(Reason why, uint32_t now) {
    reason_ = why; phase_ = Phase::rejected; record_duration(now);
    if (owned_) {
      pending_.active = false; pending_.art = false; ++pending_.terminal;
    }
  }
  bool check_fixed() {
    if (std::memcmp(fixed_.data(), "STV7", 4) != 0 || fixed_[4] != 2 || fixed_[5] != request_.operation ||
        be16(fixed_.data() + 6) != 0 || be64(fixed_.data() + 8) != request_.epoch ||
        std::memcmp(fixed_.data() + 16, request_.tx.bytes.data(), 16) != 0) return false;
    expected_payload_ = be16(fixed_.data() + 34);
    expected_crc_ = be32(fixed_.data() + 36);
    if (expected_payload_ > PAYLOAD_MAX || expected_payload_ + FIXED != request_.content_length) return false;
    if (request_.operation == 1) return expected_payload_ >= 1 && be16(fixed_.data() + 32) == 0;
    if (request_.operation == 2) return expected_payload_ == 512; // tile index is checked by media state later
    return expected_payload_ == 0 && be16(fixed_.data() + 32) == 0;
  }
  bool parse_head() {
    std::string_view all(head_.data(), head_used_ - 4);
    size_t line_end = all.find("\r\n");
    if (line_end == std::string_view::npos || line_end > REQUEST_LINE_MAX) return false;
    std::string_view first = all.substr(0, line_end);
    size_t first_space = first.find(' '), second_space = first.find(' ', first_space + 1);
    if (first_space != 4 || first.substr(0, 4) != "POST" || second_space == std::string_view::npos ||
        first.substr(second_space + 1) != "HTTP/1.1" || first.find(' ', second_space + 1) != std::string_view::npos) return false;
    request_.method = first.substr(0, first_space);
    request_.target = first.substr(first_space + 1, second_space - first_space - 1);
    constexpr std::string_view prefix = "/api/v2/bridge/media/";
    if (request_.target.substr(0, prefix.size()) != prefix) return false;
    std::string_view rest = request_.target.substr(prefix.size());
    size_t slash = rest.find('/');
    if (slash == std::string_view::npos || rest.size() - slash - 1 != 32) return false;
    std::string_view op = rest.substr(0, slash), tx = rest.substr(slash + 1);
    request_.operation = op == "begin" ? 1 : op == "tile" ? 2 : op == "commit" ? 3 : op == "abort" ? 4 : 0;
    if (!request_.operation) return false;
    for (size_t i = 0; i < 16; ++i) {
      int hi = hex(tx[2 * i]), lo = hex(tx[2 * i + 1]);
      if (hi < 0 || lo < 0) return false;
      request_.tx.bytes[i] = static_cast<uint8_t>((hi << 4) | lo);
    }
    request_.epoch = be64(request_.tx.bytes.data());
    request_.sequence = be64(request_.tx.bytes.data() + 8);
    if (!request_.epoch || !request_.sequence) return false;
    constexpr std::array<std::string_view, 7> names = {
        "host", "content-type", "content-length", "content-digest", "signature-input", "signature", "connection"};
    std::array<std::string_view, 7> values{};
    size_t seen = 0, fields = 0, pos = line_end + 2;
    while (pos < all.size()) {
      size_t end = all.find("\r\n", pos);
      if (end == std::string_view::npos) end = all.size();
      if (end - pos > LINE_MAX || ++fields > FIELD_MAX) return false;
      std::string_view line = all.substr(pos, end - pos);
      size_t colon = line.find(':');
      if (colon == std::string_view::npos || colon == 0 || colon + 2 > line.size() || line[colon + 1] != ' ' ||
          (colon + 2 < line.size() && line[colon + 2] == ' ') || line.back() == ' ' || line.front() == ' ') return false;
      std::string_view name = line.substr(0, colon), value = line.substr(colon + 2);
      size_t slot = names.size();
      for (size_t i = 0; i < names.size(); ++i) if (ci_equal(name, names[i])) { slot = i; break; }
      if (slot == names.size() || (seen & (uint64_t(1) << slot)) || value.empty()) return false;
      seen |= (uint64_t(1) << slot); values[slot] = value;
      pos = end + 2;
    }
    if (seen != 0x7f || values[0] != "unit.invalid" ||
        values[1] != "application/vnd.shino-tv.media-wire-v2" || values[6] != "close") return false;
    std::string_view length = values[2];
    if (length.empty() || length.size() > 3 || length[0] == '0') return false;
    uint16_t parsed = 0;
    for (char c : length) {
      if (c < '0' || c > '9') return false;
      parsed = static_cast<uint16_t>(parsed * 10 + c - '0');
    }
    if (parsed < FIXED || parsed > BODY_MAX) return false;
    request_.content_length = parsed;
    request_.host = values[0]; request_.content_digest = values[3];
    request_.signature_input = values[4]; request_.signature = values[5];
    // The injected verifier must parse/validate RFC 9421 and RFC 9530 fields.
    return true;
  }
};
} // namespace v07lab
