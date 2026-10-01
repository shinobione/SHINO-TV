#pragma once
#include "MediaCrypto.h"
#include <ArduinoJson.h>
#include <memory>
#include <new>
#ifdef SHINO_ARTWORK_DISPLAY_PILOT
#include <display/ArtworkPilot.h>
#endif
namespace m7 {
// Inert sink owns the single image allocation after Commit; no LCD API.
struct DisplaySink {
  std::unique_ptr<uint8_t[]> image;
  char metadata[513] = {};
  unsigned commits = 0;
#ifdef SHINO_ARTWORK_DISPLAY_PILOT
  // Extent/provenance travel with the owning allocation, never with staging.
  size_t committedBytes = 0;
  uint32_t revision = 0;
  bool committed = false;
  ArtworkPilot::Caption caption;
  ArtworkPilot::View borrow() const {
    return ArtworkPilot::committedView(image.get(), committedBytes, caption,
                                       committed, revision);
  }
#endif
  void clear() {
    image.reset();
    metadata[0] = 0;
#ifdef SHINO_ARTWORK_DISPLAY_PILOT
    committedBytes = 0;
    committed = false;
    caption = ArtworkPilot::Caption{};
    ++revision;
#endif
  }
};
struct Record {
  uint8_t op = 0, tx[16] = {};
  uint64_t epoch = 0;
  uint16_t index = 0, length = 0;
  const uint8_t *payload = nullptr;
};
inline bool wire(const uint8_t *b, size_t n, uint8_t op, const uint8_t tx[16],
                 uint64_t epoch, Record &r) {
  if (n < 40 || n > 552 || memcmp(b, "STV7", 4) || b[4] != 2 || b[5] != op ||
      be16(b + 6) || be64(b + 8) != epoch || memcmp(b + 16, tx, 16) ||
      be64(tx) != epoch || !be64(tx + 8))
    return false;
  r.op = op;
  r.epoch = epoch;
  memcpy(r.tx, tx, 16);
  r.index = be16(b + 32);
  r.length = be16(b + 34);
  r.payload = b + 40;
  return r.length == n - 40 && be32(b + 36) == crc(r.payload, r.length) &&
         (op == 2 ? r.length == 512 && r.index <= 8
                  : r.index == 0 && (op == 1 ? r.length >= 1 && r.length <= 512
                                             : r.length == 0));
}
// Strict UTF-8, codepoint count, no C0/C1/surrogates. Matches retained text
// contract.
inline bool text(const char *s, size_t max, size_t bytes) {
  size_t count = 0, at = 0;
  const auto *p = reinterpret_cast<const uint8_t *>(s);
  while (at < bytes) {
    uint32_t c = p[at++];
    unsigned more = 0;
    uint32_t min = 0;
    if (c >= 0x80) {
      if (c >= 0xc2 && c <= 0xdf) {
        more = 1;
        c &= 31;
        min = 0x80;
      } else if (c >= 0xe0 && c <= 0xef) {
        more = 2;
        c &= 15;
        min = 0x800;
      } else if (c >= 0xf0 && c <= 0xf4) {
        more = 3;
        c &= 7;
        min = 0x10000;
      } else
        return false;
      if (more > bytes - at) return false;
      for (unsigned i = 0; i < more; ++i) {
        if ((p[at] & 0xc0) != 0x80)
          return false;
        c = (c << 6) | (p[at++] & 63);
      }
      if (c < min)
        return false;
    }
    if (c < 32 || (c >= 0x7f && c <= 0x9f) || (c >= 0xd800 && c <= 0xdfff) ||
        c > 0x10ffff || ++count > max)
      return false;
  }
  return true;
}
struct Metadata {
  char canonical[513] = {};
  uint16_t cover = 0;
  uint8_t tiles = 0;
  uint8_t digest[32] = {};
#ifdef SHINO_ARTWORK_DISPLAY_PILOT
  ArtworkPilot::Caption caption;
#endif
};
// Hard cap for the temporary JSON document; allocated only after Gate2.
// Fixed arena reuses only its newest block; all storage dies before staging.
class JsonArena final : public ArduinoJson::Allocator {
  std::unique_ptr<uint8_t[]> bytes;
  struct Header { size_t size, previous; };
#ifdef M8R_ARENA_TEST_PROFILE
  // Pinned Xtensa max_align_t is 8; GCC x86 -m32 reports 16. The dedicated
  // profile uses the linked native alignment, not the host's larger default.
  static constexpr size_t alignment = 8;
#else
  static constexpr size_t alignment = alignof(max_align_t);
#endif
  static constexpr size_t prefix = (sizeof(Header)+alignment-1)&~(alignment-1);
  size_t used = 0, peak = 0;
  bool denied = false;

public:
#ifdef SHINO_M8_METADATA_ARENA_BYTES
  static constexpr size_t capacity = SHINO_M8_METADATA_ARENA_BYTES;
#else
  static constexpr size_t capacity = sizeof(void *) == 8 ? 8192 : 2048;
#endif
  static_assert(capacity >= prefix, "bounded arena header must fit");
#ifdef M8R_ARENA_TEST_PROFILE
  inline static size_t lastUsage = 0, maxUsage = 0;
  inline static bool lastDenied = false, denyBackingAllocation = false;
#endif
  JsonArena() : bytes(new(std::nothrow) uint8_t[capacity]) {
#ifdef M8R_ARENA_TEST_PROFILE
    if (denyBackingAllocation) bytes.reset();
#endif
#ifdef ESP8266
    if(!bytes) ++m8::runtimeStats.allocationFailures;
    m8::sampleResources();
#endif
  }
  ~JsonArena() {
#ifdef ESP8266
    m8::runtimeStats.arenaLast=uint32_t(peak);
    if(peak>m8::runtimeStats.arenaMax)m8::runtimeStats.arenaMax=uint32_t(peak);
    if(denied)++m8::runtimeStats.arenaDenials;
#endif
#ifdef M8R_ARENA_TEST_PROFILE
    lastUsage = peak;
    if (peak > maxUsage) maxUsage = peak;
    lastDenied = denied;
#endif
  }
  void *allocate(size_t n) override {
    size_t aligned =
        (used + alignment - 1) & ~(alignment - 1);
    if (!bytes || n > capacity - prefix || aligned > capacity - n - prefix) {
      denied = true;
      return nullptr;
    }
    auto *p = bytes.get() + aligned;
    Header h{n, used};
    memcpy(p, &h, sizeof h);
    used = aligned + prefix + n;
    if (used > peak) peak = used;
    return p + prefix;
  }
  // Reclaim only the newest block; older nodes stay put until arena teardown.
  void deallocate(void *p) override {
    if (!p) return;
    Header h;
    memcpy(&h, static_cast<uint8_t *>(p) - prefix, sizeof h);
    if (static_cast<uint8_t *>(p) + h.size == bytes.get() + used)
      used = h.previous;
  }
  void *reallocate(void *p, size_t n) override {
    if (!p)
      return allocate(n);
    Header h;
    memcpy(&h, static_cast<uint8_t *>(p) - prefix, sizeof h);
    const size_t offset = size_t(static_cast<uint8_t *>(p) - bytes.get());
    if (offset + h.size == used && n <= capacity - offset) {
      used = offset + n;
      h.size = n;
      memcpy(static_cast<uint8_t *>(p) - prefix, &h, sizeof h);
      if (used > peak) peak = used;
      return p;
    }
    if (n <= h.size) return p;
    void *next = allocate(n);
    if (next)
      memcpy(next, p, h.size);
    return next;
  }
};
M8R_NOINLINE inline bool metadata(const Record &r, Metadata &out) {
  JsonArena arena;
  JsonDocument d(&arena);
  auto err = deserializeJson(d, r.payload, r.length,
                             DeserializationOption::NestingLimit(2));
  if (err || d.overflowed() || !d.is<JsonObject>() || d.size() != 16)
    return false;
  for (JsonPair pair : d.as<JsonObject>()) {
    if (pair.key().size() != strlen(pair.key().c_str())) return false;
    if (pair.value().is<const char *>()) {
      JsonString s=pair.value().as<JsonString>();
      if (s.size()!=strlen(s.c_str())) return false;
    }
  }
  static const char *const names[] = {
      "album",      "artist",       "cover_len", "cover_sha256", "duration",
      "height",     "pixel_format", "position",  "source",       "state",
      "tile_count", "title",        "track_key", "tx",           "v",
      "width"};
  for (auto name : names)
    if (d[name].isUnbound())
      return false;
  if (!d["v"].is<int>() || d["v"].as<int>() != 2)
    return false;
  for (auto name : {"width", "height", "cover_len", "tile_count"})
    if (!d[name].is<unsigned>())
      return false;
  unsigned w = d["width"], h = d["height"], len = d["cover_len"],
           tiles = d["tile_count"];
  if ((w != 0 && w != 32 && w != 48) || h != w || len != w * w * 2 ||
      tiles != len / 512)
    return false;
  if (!d["pixel_format"].is<const char *>() ||
      strcmp(d["pixel_format"], w ? "RGB565LE" : "NONE"))
    return false;
  const char *states[] = {"PLAYING", "PAUSED", "STOPPED", "NO_SESSION",
                          "UNAVAILABLE"};
  bool state = false;
  if (!d["state"].is<const char *>())
    return false;
  for (auto s : states)
    if (!strcmp(d["state"], s))
      state = true;
  if (!state)
    return false;
  const char *texts[] = {"source", "title", "artist", "album"};
  const size_t limits[] = {80, 60, 60, 48};
  for (unsigned i = 0; i < 4; ++i)
    if (!d[texts[i]].is<const char *>() ||
        !text(d[texts[i]], limits[i], d[texts[i]].as<JsonString>().size()))
      return false;
  for (auto name : {"position", "duration"})
    if (!d[name].isNull() &&
        (!d[name].is<unsigned>() || d[name].as<unsigned>() > 604800))
      return false;
  if (!d["position"].isNull() && !d["duration"].isNull() &&
      d["position"].as<unsigned>() > d["duration"].as<unsigned>())
    return false;
  uint8_t tmp[32];
  if (!d["track_key"].is<const char *>() || !unhex(d["track_key"], tmp, 32) ||
      !d["tx"].is<const char *>() || !unhex(d["tx"], tmp, 16) ||
      memcmp(tmp, r.tx, 16))
    return false;
  if (w) {
    if (!d["cover_sha256"].is<const char *>() ||
        !unhex(d["cover_sha256"], out.digest, 32))
      return false;
  } else if (!d["cover_sha256"].isNull())
    return false;
  // Canonical schema is alphabetic. Preserve parsed order and compare exact
  // serialization: duplicate fields/escapes/whitespace/coercions cannot pass.
  size_t field = 0;
  for (JsonPair pair : d.as<JsonObject>())
    if (strcmp(pair.key().c_str(), names[field++]))
      return false;
  size_t n = serializeJson(d, out.canonical, sizeof out.canonical);
  if (n != r.length || memcmp(out.canonical, r.payload, n))
    return false;
  out.cover = uint16_t(len);
  out.tiles = uint8_t(tiles);
#ifdef SHINO_ARTWORK_DISPLAY_PILOT
  // Copy bounded presentation text only after every metadata check passes.
  // No LCD calls and no retained JsonDocument/string pointers in ingress.
  ArtworkPilot::captionText(out.caption.title, d["title"].as<const char*>());
  ArtworkPilot::captionText(out.caption.artist, d["artist"].as<const char*>());
  out.caption.state = ArtworkPilot::stateFrom(d["state"].as<const char*>());
#endif
  return true;
}
class Receiver {
  std::unique_ptr<uint8_t[]> staging;
  Metadata meta;
  uint8_t tx[16] = {}, owner = 0, next = 0;
  uint32_t started = 0;
  void terminal() {
    pending = false;
    staging.reset();
    sink.clear();
  }

public:
  DisplaySink sink;
  bool pending = false;
  uint64_t highest = 0;
  unsigned mutations = 0;
  const char *outcome = "IDLE";
  bool tick(uint32_t now) {
    if (pending && uint32_t(now - started) > 8000) {
      terminal();
      ++mutations;
      outcome = "EXPIRED";
      return false;
    }
    return true;
  }
  void cancelPrincipal(uint8_t i) {
    if (pending && owner == i) {
      terminal();
      ++mutations;
      outcome = "REVOKED";
    }
  }
  void reboot() {
    terminal();
    highest = 0;
    ++mutations;
    outcome = "REBOOT";
  }
  const uint8_t *stagedPointer() const { return staging.get(); }
  unsigned stagedBytes() const { return staging ? meta.cover : 0; }
  unsigned imageBytes() const { return sink.image ? meta.cover : 0; }
  M8R_NOINLINE bool receive(const Record &r, uint8_t principal, uint32_t now) {
    if (r.op == 1) {
      if (pending) {
        outcome = "BUSY";
        return false;
      }
      uint64_t seq = be64(r.tx + 8);
      if (seq <= highest) {
        outcome = "REPLAY";
        return false;
      }
      Metadata parsed;
      if (!metadata(r, parsed)) {
        outcome = "BAD_METADATA";
        return false;
      }
      // Accepted Begin crosses the unchanged high-water/rollback boundary.
      highest = seq;
      sink.clear();
      ++mutations;
      meta = parsed;
      memcpy(tx, r.tx, 16);
      owner = principal;
      next = 0;
      started = now;
      staging.reset(parsed.cover ? new (std::nothrow) uint8_t[parsed.cover]
                                 : nullptr);
      if (parsed.cover && !staging) {
#ifdef ESP8266
        ++m8::runtimeStats.allocationFailures;
#endif
        terminal();
        outcome = "ALLOCATION_FAILED";
        return false;
      }
      pending = true;
#ifdef ESP8266
      m8::sampleResources();
#endif
      outcome = "STAGED";
      return true;
    }
    if (!pending || owner != principal || memcmp(tx, r.tx, 16)) {
      outcome = "NO_MATCHING_TRANSACTION";
      return false;
    }
    if (!tick(now))
      return false;
    if (r.op == 4) {
      terminal();
      ++mutations;
      outcome = "INTERRUPTED";
      return true;
    }
    if (r.op == 2) {
      if (!staging || r.index >= meta.tiles) {
        terminal();
        ++mutations;
        outcome = "BAD_ENVELOPE";
        return false;
      }
      auto *at = staging.get() + r.index * 512;
      if (r.index < next) {
        if (!memcmp(at, r.payload, 512)) {
          outcome = "DUPLICATE";
          return true;
        }
        terminal();
        ++mutations;
        outcome = "CONFLICT";
        return false;
      }
      if (r.index != next) {
        terminal();
        ++mutations;
        outcome = "OUT_OF_ORDER";
        return false;
      }
      memcpy(at, r.payload, 512);
      ++next;
      ++mutations;
      outcome = "STAGED";
      return true;
    }
    if (next != meta.tiles) {
      terminal();
      ++mutations;
      outcome = "INCOMPLETE";
      return false;
    }
    uint8_t hash[32];
    if (staging) {
      sha(staging.get(), meta.cover, hash);
      if (!equal(hash, meta.digest, 32)) {
        terminal();
        ++mutations;
        outcome = "FINAL_SHA_MISMATCH";
        return false;
      }
    }
    sink.image = std::move(staging);
    memcpy(sink.metadata, meta.canonical, sizeof meta.canonical);
    ++sink.commits;
#ifdef SHINO_ARTWORK_DISPLAY_PILOT
    sink.committedBytes = meta.cover;
    sink.caption = meta.caption;
    sink.committed = true;
    ++sink.revision;
#endif
    pending = false;
    ++mutations;
    outcome = "COMMITTED";
    return true;
  }
};
} // namespace m7
