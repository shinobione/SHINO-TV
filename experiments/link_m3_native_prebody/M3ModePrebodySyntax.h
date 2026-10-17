// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// M3-B: REJECT-ONLY candidate pre-body syntax scanner, NO device integration.
//
// This is NOT an authenticator and is NOT a complete native HTTP adapter.
// It must never be placed behind the ordinary ESP8266WebServer POST parser.
// It has no route registration, no socket owner, no HMAC/Digest verifier,
// no firmware mode mutation, no OTA, no heap allocation or secret material.
//
// Fixed-size input is one HTTP/1.1 request line and headers only. A candidate
// stops exactly after CRLFCRLF; the calling lab must NOT feed/read body bytes.
// The caller supplies an already-verified target host. Digest text and
// X-Shino-Tx are UNTRUSTED until independent cryptographic verification.
// Deliberate hard HOLD: authorizedToReadBody() is always false.
#include <cstddef>
#include <cstdint>

namespace ShinoM3 {

enum class Scan : uint8_t { More, CandidateSyntaxOnly, Reject };

struct Candidate {
    uint16_t contentLength = 0;
    char transaction[33]{};
    uint16_t authOffset = 0;
    uint16_t authLength = 0;
};

class PrebodySyntax final {
public:
    static constexpr size_t kMaxHeaderBytes = 512u;
    static constexpr size_t kMaxLineBytes = 256u;
    static constexpr uint8_t kMaxFields = 8u;
    static constexpr uint32_t kLabDeadlineMs = 1000u; // Model only, NOT an OS timing bound.
    static constexpr uint16_t kMaxCommandBytes = 240u; // M3-A proposed contract.

    explicit PrebodySyntax(const char* expectedHost) : expectedHost_(expectedHost) {}

    Scan feed(char next, uint32_t elapsedMs) {
        if (state_ != Scan::More) return state_;
        if (elapsedMs > kLabDeadlineMs || next == '\0' || used_ >= kMaxHeaderBytes)
            return reject();
        data_[used_++] = next;
        if (next == '\n') {
            if (used_ < 2 || data_[used_ - 2u] != '\r') return reject();
            const size_t lineBytes = used_ - 2u - lineStart_;
            if (lineBytes > kMaxLineBytes) return reject();
            if (lineBytes == 0u) {
                if (!parse()) return reject();
                state_ = Scan::CandidateSyntaxOnly;
                return state_;
            }
            lineStart_ = used_;
        } else if (used_ - lineStart_ > kMaxLineBytes + 2u) {
            return reject();
        }
        return Scan::More;
    }

    Scan state() const { return state_; }
    size_t consumed() const { return used_; }
    const Candidate& candidate() const { return candidate_; }
    bool authorizedToReadBody() const { return false; } // ALWAYS HOLD.

private:
    struct Span { const char* ptr; size_t n; };
    char data_[kMaxHeaderBytes]{};
    const char* expectedHost_ = nullptr;
    Candidate candidate_{};
    size_t used_ = 0u;
    size_t lineStart_ = 0u;
    Scan state_ = Scan::More;

    Scan reject() {
        candidate_ = Candidate{};
        state_ = Scan::Reject;
        return state_;
    }

    static bool same(Span a, const char* text, bool insensitive = false) {
        size_t i = 0u;
        while (text && text[i]) {
            if (i >= a.n) return false;
            char c = a.ptr[i], expected = text[i];
            if (insensitive) {
                if (c >= 'A' && c <= 'Z') c = char(c + ('a' - 'A'));
                if (expected >= 'A' && expected <= 'Z')
                    expected = char(expected + ('a' - 'A'));
            }
            if (c != expected) return false;
            ++i;
        }
        return text && i == a.n;
    }

    static bool prefix(Span a, const char* text) {
        size_t i = 0u;
        while (text[i]) {
            if (i >= a.n || a.ptr[i] != text[i]) return false;
            ++i;
        }
        return true;
    }

    static bool hex(char ch) {
        return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
    }

    static bool parseLength(Span s, uint16_t& out) {
        if (!s.n || s.n > 3u || (s.n > 1u && s.ptr[0] == '0'))
            return false;
        uint16_t value = 0;
        for (size_t i = 0u; i < s.n; ++i) {
            if (s.ptr[i] < '0' || s.ptr[i] > '9') return false;
            value = uint16_t(value * 10u + unsigned(s.ptr[i] - '0'));
            if (value > kMaxCommandBytes) return false;
        }
        if (value == 0u) return false;
        out = value;
        return true;
    }

    bool parse() {
        // Syntax pass does NOT confer authorization or permission to read body.
        if (!expectedHost_ || !*expectedHost_) return false;
        size_t pos = 0u, end = 0u;
        uint8_t seen = 0u, fields = 0u;
        bool first = true;
        Candidate parsed{};

        while (pos < used_) {
            end = pos;
            while (end + 1u < used_
                   && !(data_[end] == '\r' && data_[end + 1u] == '\n'))
                ++end;
            if (end + 1u >= used_) return false;
            if (first) {
                if (!same(Span{data_ + pos, end - pos},
                          "POST /api/v1/display/mode HTTP/1.1"))
                    return false;
                first = false;
                pos = end + 2u;
                continue;
            }
            if (end == pos) {
                if (end + 2u != used_) return false;
                constexpr uint8_t required = (1u << 6u) - 1u;
                if ((seen & required) != required) return false;
                candidate_ = parsed;
                return true;
            }
            if (++fields > kMaxFields || end - pos > kMaxLineBytes)
                return false;
            size_t colon = pos;
            while (colon < end && data_[colon] != ':') ++colon;
            if (colon == pos || colon == end || colon - pos > 32u)
                return false;
            for (size_t i = pos; i < colon; ++i) {
                const char ch = data_[i];
                if (!((ch >= 'A' && ch <= 'Z')
                      || (ch >= 'a' && ch <= 'z') || ch == '-'))
                    return false;
            }
            size_t valueStart = colon + 1u;
            if (valueStart < end && data_[valueStart] == ' ') ++valueStart;
            if (valueStart == end || data_[valueStart] == ' '
                || data_[valueStart] == '\t'
                || data_[end - 1u] == ' ') return false;
            for (size_t i = valueStart; i < end; ++i) {
                const unsigned char ch = static_cast<unsigned char>(data_[i]);
                if (ch < 32u || ch > 126u) return false; // no obs-fold/TAB
            }
            const Span name{data_ + pos, colon - pos};
            const Span value{data_ + valueStart, end - valueStart};
            uint8_t fieldId = 255u;
            if (same(name, "Host", true)) fieldId = 0u;
            else if (same(name, "Content-Type", true)) fieldId = 1u;
            else if (same(name, "Content-Length", true)) fieldId = 2u;
            else if (same(name, "Authorization", true)) fieldId = 3u;
            else if (same(name, "X-Shino-Tx", true)) fieldId = 4u;
            else if (same(name, "Connection", true)) fieldId = 5u;
            if (fieldId > 5u || (seen & (1u << fieldId)))
                return false; // reject all unknown/duplicate fields
            seen = uint8_t(seen | (1u << fieldId));

            switch (fieldId) {
                case 0u:
                    if (!same(value, expectedHost_)) return false;
                    break;
                case 1u:
                    if (!same(value, "application/json")) return false;
                    break;
                case 2u:
                    if (!parseLength(value, parsed.contentLength)) return false;
                    break;
                case 3u:
                    if (value.n < 8u || value.n > 220u
                        || !prefix(value, "Digest ")) return false;
                    parsed.authOffset = uint16_t(valueStart);
                    parsed.authLength = uint16_t(value.n);
                    break;
                case 4u: {
                    if (value.n != 32u) return false;
                    bool nonzero = false;
                    for (size_t i = 0u; i < 32u; ++i) {
                        if (!hex(value.ptr[i])) return false;
                        if (value.ptr[i] != '0') nonzero = true;
                        parsed.transaction[i] = value.ptr[i];
                    }
                    if (!nonzero) return false;
                    parsed.transaction[32] = '\0';
                    break;
                }
                case 5u:
                    if (!same(value, "close", true)) return false;
                    break;
                default: return false;
            }
            pos = end + 2u;
        }
        return false;
    }
};

} // namespace ShinoM3
