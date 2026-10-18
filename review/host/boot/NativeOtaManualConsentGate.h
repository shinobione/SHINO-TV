// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1 RESEARCH ONLY. Volatile single-use, short-lived binding for a
// *separately verified* Digest-protected manual approval of one exact package.
// NO HTTP route, NO password checking, NO random generator, NO flash writer.
//
// Input proof booleans are TRUSTED ONLY IN HOST FIXTURES; they must be derived
// in a future audited network adapter, never taken from a browser JSON field.
// The future owner-controlled UI should show exact model/kind/size/digest and
// require deliberate confirmation BEFORE this gate is issued.
// Nonce bytes must come from independent hardware CSPRNG and never be logged.
// Full signed transport SHA-256 binds a selected file; it does NOT prove that
// the release is signed or compatible. Core RSA validation is independent.
#include <array>
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {

enum class IntendedPackage : uint8_t { SignedShino, SignedExactOem };
enum class ConsentPhase : uint8_t { Idle, Offered, ConsumedForReviewOnly, Aborted };

class ManualConsentGate final {
public:
    static constexpr uint32_t kLifetimeMs = 60'000;
    static constexpr uint32_t kSignedOemBytes = 494'144u + 256u + 4u;
    static constexpr uint32_t kSmallestSignedShinoBytes = 64'000u + 256u + 4u;
    ManualConsentGate()=default;
    ManualConsentGate(const ManualConsentGate&)=delete;
    ManualConsentGate& operator=(const ManualConsentGate&)=delete;

    bool offer(bool digestAuthenticated, bool requestEnvelopeAccepted,
               bool ownerDeliberatelyConfirmed, uint32_t peerNetworkOrder,
               IntendedPackage kind, uint32_t signedTransportBytes,
               const std::array<uint8_t,16>& independentlyRandomToken,
               const std::array<uint8_t,32>& selectedTransportSha256,
               uint32_t nowMs) {
        if (phase_!=ConsentPhase::Idle) return false;
        if (!digestAuthenticated || !requestEnvelopeAccepted ||
            !ownerDeliberatelyConfirmed || peerNetworkOrder==0u ||
            !validSize(kind,signedTransportBytes) ||
            allZero(independentlyRandomToken) || allZero(selectedTransportSha256))
            return fail();
        peer_=peerNetworkOrder;
        kind_=kind;
        bytes_=signedTransportBytes;
        token_=independentlyRandomToken;
        digest_=selectedTransportSha256;
        issuedAtMs_=nowMs;
        phase_=ConsentPhase::Offered;
        return true;
    }

    // Must be called exactly once from a distinct independently Digest
    // authenticated upload request; does not authorize updater commit.
    bool consume(bool digestAuthenticated, bool rawRequestPolicyAccepted,
                 uint32_t peerNetworkOrder, IntendedPackage kind,
                 uint32_t declaredSignedTransportBytes,
                 const std::array<uint8_t,16>& suppliedToken,
                 const std::array<uint8_t,32>& suppliedTransportSha256,
                 uint32_t nowMs) {
        if (phase_!=ConsentPhase::Offered) return false;
        uint8_t tokenDiff=0u,hashDiff=0u;
        for(size_t i=0;i<token_.size();++i) tokenDiff|=token_[i]^suppliedToken[i];
        for(size_t i=0;i<digest_.size();++i) hashDiff|=digest_[i]^suppliedTransportSha256[i];
        if (!digestAuthenticated || !rawRequestPolicyAccepted ||
            static_cast<uint32_t>(nowMs-issuedAtMs_)>=kLifetimeMs ||
            peerNetworkOrder!=peer_ || kind!=kind_ ||
            declaredSignedTransportBytes!=bytes_ || tokenDiff || hashDiff)
            return fail(); // Wrong guess consumes the offer. No retries.
        wipe();
        phase_=ConsentPhase::ConsumedForReviewOnly;
        return true;
    }

    void abort() {
        if (phase_==ConsentPhase::Offered) fail();
    }
    bool checkTimeout(uint32_t nowMs) {
        if (phase_!=ConsentPhase::Offered) return false;
        if (static_cast<uint32_t>(nowMs-issuedAtMs_)>=kLifetimeMs) return fail();
        return true;
    }
    ConsentPhase phase() const { return phase_; }
private:
    template<size_t N>
    static bool allZero(const std::array<uint8_t,N>& a) {
        uint8_t sum=0u;
        for(auto v:a) sum|=v;
        return sum==0u;
    }
    static bool validSize(IntendedPackage kind,uint32_t size) {
        if (kind==IntendedPackage::SignedExactOem) return size==kSignedOemBytes;
        if (kind==IntendedPackage::SignedShino)
            return size>=kSmallestSignedShinoBytes && size<=kSignedOemBytes;
        return false;
    }
    void wipe() {
        for(auto& byte:token_) byte=0u;
        for(auto& byte:digest_) byte=0u;
        peer_=0u;
        bytes_=0u;
    }
    bool fail() {
        wipe();
        phase_=ConsentPhase::Aborted;
        return false;
    }
    ConsentPhase phase_=ConsentPhase::Idle;
    IntendedPackage kind_=IntendedPackage::SignedShino;
    uint32_t peer_=0u, bytes_=0u, issuedAtMs_=0u;
    std::array<uint8_t,16> token_{};
    std::array<uint8_t,32> digest_{};
};

} // namespace ShinoNativeOta
