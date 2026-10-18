// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1 RESEARCH ONLY: incrementally checks the unsigned portion of an OEM
// signed package BEFORE any future call capable of committing an OTA.
// No HTTP route, Updater call, flash, filesystem access or reboot.
//
// Production uses SHA-256 of the immutable manufacturer application. The
// test-only Policy injection exists to run synthetic fixtures without shipping
// or redistributing proprietary OEM bytes. A digest match is not a signature,
// device compatibility, owner authorization, successful staging or recovery.
#include <array>
#include <cstddef>
#include <cstdint>

namespace ShinoOemPrecommit {

struct ProductionV9044Pin final {
    static constexpr uint32_t kRawBytes = 494144u;
    static constexpr uint32_t kRsa2048Bytes = 256u;
    static constexpr uint32_t kTransportBytes = kRawBytes + kRsa2048Bytes + 4u;
    static constexpr char kExpectedSha256[] =
        "a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718";
    static constexpr std::array<uint8_t, 4> kExpectedEspHeader{{0xE9, 2, 2, 0x40}};
};

enum class Phase : uint8_t {
    Idle, Receiving, ExactRawAwaitingCoreSignature, Aborted
};

// Hasher API: void begin(); void add(const uint8_t*,size_t);
//             void end(uint8_t out[32]); must implement real SHA-256.
// Only the first kRawBytes are hashed, never the RSA signature or trailer.
// Policy MUST come from independently pinned source, not request JSON.
template<class Hasher, class Pin = ProductionV9044Pin>
class SignedOemPrecommitGate final {
public:
    static constexpr size_t kMaxChunkBytes = 4096u;

    SignedOemPrecommitGate() = default;
    SignedOemPrecommitGate(const SignedOemPrecommitGate&) = delete;
    SignedOemPrecommitGate& operator=(const SignedOemPrecommitGate&) = delete;

    bool begin(uint32_t declaredTransportBytes) {
        if (phase_ != Phase::Idle) return false;
        if (declaredTransportBytes != Pin::kTransportBytes) return fail();
        if (!decodePin(expected_)) return fail();
        hash_.begin();
        phase_ = Phase::Receiving;
        return true;
    }

    bool add(const uint8_t* data, size_t bytes) {
        if (phase_ != Phase::Receiving) return false;
        if (data == nullptr || bytes == 0 || bytes > kMaxChunkBytes ||
            bytes > Pin::kTransportBytes - received_)
            return fail();

        const uint32_t first = received_;
        const size_t payloadBytes = (first < Pin::kRawBytes)
            ? ((Pin::kRawBytes - first < bytes) ? Pin::kRawBytes - first : bytes)
            : 0u;

        // Header can arrive split across tiny chunks: compare bytes in
        // absolute positions rather than assuming item.currentSize >= 4.
        for (size_t i = 0; i < payloadBytes && first + i < 4u; ++i)
            if (data[i] != Pin::kExpectedEspHeader[first + i]) return fail();
        if (payloadBytes) hash_.add(data, payloadBytes);

        // Keep only the final trailer length. RSA bytes are neither buffered
        // nor hashed by this OEM-exact guard; core verifier must check them.
        for (size_t i = 0; i < bytes; ++i) {
            const uint32_t offset = first + static_cast<uint32_t>(i);
            if (offset >= Pin::kTransportBytes - 4u) {
                trailer_[offset - (Pin::kTransportBytes - 4u)] = data[i];
            }
        }
        received_ += static_cast<uint32_t>(bytes);
        return true;
    }

    bool finish(uint32_t reportedTransportBytes) {
        if (phase_ != Phase::Receiving) return false;
        if (received_ != Pin::kTransportBytes ||
            reportedTransportBytes != Pin::kTransportBytes) return fail();
        const uint32_t len = uint32_t(trailer_[0]) |
                             (uint32_t(trailer_[1]) << 8u) |
                             (uint32_t(trailer_[2]) << 16u) |
                             (uint32_t(trailer_[3]) << 24u);
        if (len != Pin::kRsa2048Bytes) return fail();
        uint8_t actual[32]{};
        hash_.end(actual);
        uint8_t difference = 0u;
        for (size_t i = 0; i < sizeof(actual); ++i)
            difference |= static_cast<uint8_t>(actual[i] ^ expected_[i]);
        for (uint8_t& byte : actual) byte = 0u;
        if (difference) return fail();
        wipe();
        phase_ = Phase::ExactRawAwaitingCoreSignature;
        return true;
    }

    void abort() {
        if (phase_ == Phase::Receiving) fail();
    }

    Phase phase() const { return phase_; }
    uint32_t receivedBytes() const { return received_; }

private:
    static uint8_t nibble(char c) {
        if (c >= '0' && c <= '9') return static_cast<uint8_t>(c - '0');
        if (c >= 'a' && c <= 'f') return static_cast<uint8_t>(c - 'a' + 10);
        return 0xffu;
    }
    static bool decodePin(std::array<uint8_t, 32>& digest) {
        static_assert(sizeof(Pin::kExpectedSha256) == 65,
                      "The independently frozen OEM SHA256 must be exactly 64 hex chars");
        static_assert(Pin::kTransportBytes == Pin::kRawBytes + Pin::kRsa2048Bytes + 4u,
                      "Signed transport has unexpected trailer geometry");
        static_assert(Pin::kRsa2048Bytes == 256u,
                      "Only the reviewed RSA-2048 signed format is supported");
        for (size_t i = 0; i < digest.size(); ++i) {
            const uint8_t hi = nibble(Pin::kExpectedSha256[i * 2u]);
            const uint8_t lo = nibble(Pin::kExpectedSha256[i * 2u + 1u]);
            if (hi == 0xffu || lo == 0xffu) return false;
            digest[i] = static_cast<uint8_t>((hi << 4u) | lo);
        }
        return true;
    }
    void wipe() {
        for (uint8_t& byte : expected_) byte = 0u;
        for (uint8_t& byte : trailer_) byte = 0u;
    }
    bool fail() {
        wipe();
        phase_ = Phase::Aborted;
        return false;
    }

    Hasher hash_{};
    std::array<uint8_t, 32> expected_{};
    std::array<uint8_t, 4> trailer_{};
    uint32_t received_ = 0u;
    Phase phase_ = Phase::Idle;
};

} // namespace ShinoOemPrecommit
