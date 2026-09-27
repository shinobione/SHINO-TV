// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// SHINO // TV V2.1: HOST-TESTABLE TRANSFER INTENT GATE, NOT AN OTA WRITER.
//
// No registration in ESP8266WebServer and no calls to Updater/flash/filesystem.
// It only validates single-use, peer-bound, time-bounded transfer accounting.
// Possession of a token, a matching digest, or BytesComplete does NOT prove a
// signed release, authorize Update.begin(), or authorize hardware flashing.
// Only a separately designed privileged Digest action may ever arm a future
// device-side instance; the caller must supply an independently generated
// unpredictable 128-bit token and an independently approved exact size.
#include <array>
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {

enum class TransferPhase : uint8_t {
    Idle, Armed, Streaming, BytesCompleteAwaitingSignatureCheck, Aborted
};

class IntentGate final {
public:
    static constexpr uint32_t kArmLifetimeMs = 60'000;
    static constexpr uint32_t kStreamInactivityMs = 15'000;
    static constexpr uint32_t kMinSignedTransportBytes = 64'000 + 256 + 4;
    static constexpr uint32_t kMaxSignedTransportBytes = 494'144 + 256 + 4;
    static constexpr size_t kMaxChunkBytes = 4096;

    // An arm() call is NOT a security authorization. The privileged HTTP
    // handler and cryptographic trust decisions do not exist in this phase.
    // Exactly one intent per gate instance. After any failure/complete, a
    // distinct instance and a fresh independently approved action are needed.
    bool arm(uint32_t peerIPv4, const std::array<uint8_t, 16>& token,
             uint32_t expectedSignedTransportBytes, uint32_t nowMs) {
        if (phase_ != TransferPhase::Idle || peerIPv4 == 0 ||
            expectedSignedTransportBytes < kMinSignedTransportBytes ||
            expectedSignedTransportBytes > kMaxSignedTransportBytes) return false;
        uint8_t nonzero = 0;
        for (uint8_t byte : token) nonzero |= byte;
        if (nonzero == 0) return false;
        peer_ = peerIPv4;
        token_ = token;
        expected_ = expectedSignedTransportBytes;
        received_ = 0;
        armedAtMs_ = nowMs;
        lastChunkMs_ = nowMs;
        phase_ = TransferPhase::Armed;
        return true;
    }

    bool start(uint32_t peerIPv4, const std::array<uint8_t, 16>& token,
               uint32_t declaredTransportBytes, uint32_t nowMs) {
        if (phase_ != TransferPhase::Armed) return false;
        if (expired(nowMs) || !sameBinding(peerIPv4, token) ||
            declaredTransportBytes != expected_) return fail();
        phase_ = TransferPhase::Streaming;
        lastChunkMs_ = nowMs;
        return true;
    }

    // For a future upload handler, only counts bytes; intentionally does NOT
    // write, buffer, validate or cryptographically accept the supplied data.
    bool acceptChunk(uint32_t peerIPv4, const std::array<uint8_t, 16>& token,
                     const uint8_t* bytes, size_t count, uint32_t nowMs) {
        if (phase_ != TransferPhase::Streaming) return false;
        if (expired(nowMs) || !sameBinding(peerIPv4, token) || bytes == nullptr ||
            count == 0 || count > kMaxChunkBytes || count > expected_ - received_)
            return fail();
        received_ += static_cast<uint32_t>(count);
        lastChunkMs_ = nowMs;
        return true;
    }

    bool finish(uint32_t peerIPv4, const std::array<uint8_t, 16>& token,
                uint32_t reportedTransportBytes, uint32_t nowMs) {
        if (phase_ != TransferPhase::Streaming) return false;
        if (expired(nowMs) || !sameBinding(peerIPv4, token) ||
            reportedTransportBytes != expected_ || received_ != expected_)
            return fail();
        phase_ = TransferPhase::BytesCompleteAwaitingSignatureCheck;
        wipeToken();
        return true;
    }

    // A power interruption cannot be simulated as recovery here. A disconnect
    // must move to Aborted and cannot auto-retry or arm itself again.
    void abort() {
        if (phase_ == TransferPhase::Armed || phase_ == TransferPhase::Streaming) fail();
    }

    bool checkTimeout(uint32_t nowMs) {
        if (phase_ == TransferPhase::Armed || phase_ == TransferPhase::Streaming)
            return expired(nowMs) ? fail() : true;
        return false;
    }

    TransferPhase phase() const { return phase_; }
    uint32_t receivedBytes() const { return received_; }
    uint32_t expectedSignedTransportBytes() const { return expected_; }

private:
    bool sameBinding(uint32_t peerIPv4, const std::array<uint8_t, 16>& supplied) const {
        if (peerIPv4 != peer_) return false;
        uint8_t difference = 0;
        for (size_t i = 0; i < token_.size(); ++i) difference |= token_[i] ^ supplied[i];
        return difference == 0;
    }

    bool expired(uint32_t nowMs) const {
        // Unsigned subtraction handles millis() wrap for these short deadlines.
        if (static_cast<uint32_t>(nowMs - armedAtMs_) >= kArmLifetimeMs) return true;
        if (phase_ == TransferPhase::Streaming &&
            static_cast<uint32_t>(nowMs - lastChunkMs_) >= kStreamInactivityMs) return true;
        return false;
    }

    void wipeToken() { for (uint8_t& byte : token_) byte = 0; }

    bool fail() {
        phase_ = TransferPhase::Aborted;
        wipeToken();
        return false;
    }

    TransferPhase phase_ = TransferPhase::Idle;
    std::array<uint8_t, 16> token_{};
    uint32_t peer_ = 0;
    uint32_t expected_ = 0;
    uint32_t received_ = 0;
    uint32_t armedAtMs_ = 0;
    uint32_t lastChunkMs_ = 0;
};

}  // namespace ShinoNativeOta
