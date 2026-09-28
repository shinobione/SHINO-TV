// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// SHINO V2.1 HOST-ONLY REVIEW CONTRACT. NOT INCLUDED BY THE LIVE FIRMWARE.
// There is NO real HTTP handler, Updater instance, flash writer or reboot here.
//
// This orders a prospective OEM-only signed upload. The last call to
// adapter.end(false) delegates RSA validation AND eboot scheduling to the
// ESP8266 core; INVALID RSA MUST REACH end(false) to be checked, but MUST
// never schedule eboot. The already-reviewed raw OEM SHA256 must pass BEFORE
// end(false) can be called. This class is NOT an auth/signature provider.
//
// Adapter contract:
//   bool begin(uint32_t exactSignedSize);
//   size_t write(const uint8_t*,size_t);
//   bool isFinished() const; bool hasError() const;
//   bool end(bool evenIfRemaining);
// Production integration requires independently audited Digest/CSRF intent,
// trust anchor, core signer setup and power-loss behaviour. Test adapters
// must faithfully model end(false), including RSA failure and no eboot copy.
#include "recovery/SignedOemPrecommitGate.h"
#include <cstddef>
#include <cstdint>

namespace ShinoOemPrecommit {

enum class CommitPhase : uint8_t { Idle, Streaming, CoreAccepted, Aborted };
// Forces the independently reviewed production adapter to expose an explicitly
// APPLICATION-ONLY begin method. Its implementation must use U_FLASH, never U_FS.
struct SignedApplicationOnlyTag final {};

template<class Hasher, class Pin, class Adapter>
class SignedOemCommitBarrier final {
public:
    SignedOemCommitBarrier(Adapter& adapter) : adapter_(adapter) {}
    SignedOemCommitBarrier(const SignedOemCommitBarrier&) = delete;
    SignedOemCommitBarrier& operator=(const SignedOemCommitBarrier&) = delete;

    // These booleans are assumptions SUPPLIED by a future privileged adapter,
    // not checked by this policy. Neither a GET cookie nor request-supplied
    // metadata can establish either. Only host fixtures supply them currently.
    bool begin(bool privilegedOwnerIntentValidated,
               bool coreSignedVerifierConfigured,
               uint32_t declaredTransportBytes) {
        if (phase_ != CommitPhase::Idle) return false;
        if (!privilegedOwnerIntentValidated || !coreSignedVerifierConfigured ||
            declaredTransportBytes != Pin::kTransportBytes)
            return fail();
        if (!raw_.begin(declaredTransportBytes)) return fail();
        if (!adapter_.begin(declaredTransportBytes, SignedApplicationOnlyTag{}) || adapter_.hasError())
            return fail();
        phase_ = CommitPhase::Streaming;
        return true;
    }

    bool add(uint8_t* data, size_t count) {
        if (phase_ != CommitPhase::Streaming) return false;
        // Validate before staging each chunk. Earlier chunks may already have
        // touched the temporary staging area: NOT atomic power-loss recovery.
        if (!raw_.add(data, count)) return fail();
        if (adapter_.hasError() || adapter_.write(data, count) != count ||
            adapter_.hasError()) return fail();
        return true;
    }

    bool complete(uint32_t reportedTransportBytes) {
        if (phase_ != CommitPhase::Streaming) return false;
        // EXACT, pinned raw OEM SHA256 and trailer-size verification MUST pass
        // before the single potentially committing call below.
        if (!raw_.finish(reportedTransportBytes) ||
            raw_.phase() != Phase::ExactRawAwaitingCoreSignature)
            return fail();
        if (adapter_.hasError() || !adapter_.isFinished()) return fail();

        // Core 3.1.2 validates the RSA signature inside end(false), *before*
        // eboot_command_write. It is impossible to reject a bad signature
        // before this call without running a separate independent verifier.
        // Never use end(true), unsigned exception or automatic retry.
        if (!adapter_.end(false) || adapter_.hasError()) return fail();
        phase_ = CommitPhase::CoreAccepted;
        return true;
    }

    void abort() {
        if (phase_ == CommitPhase::Streaming) {
            raw_.abort();
            fail();
        }
    }

    CommitPhase phase() const { return phase_; }
    uint32_t receivedBytes() const { return raw_.receivedBytes(); }

private:
    bool fail() {
        raw_.abort();
        phase_ = CommitPhase::Aborted;
        return false;
    }

    Adapter& adapter_;
    SignedOemPrecommitGate<Hasher, Pin> raw_;
    CommitPhase phase_ = CommitPhase::Idle;
};

} // namespace ShinoOemPrecommit
