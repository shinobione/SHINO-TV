// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// SHINO V2.1 HOST-ONLY BOUNDED HTTP STREAM REVIEW, NOT AN OTA WRITER.
// Never included in FirstBootBridge / FactoryRollback. No socket, FS, updater,
// signing key, firmware commit, restart or flash API. ReviewSink is exclusively
// a TEST/REVIEW receiver; production staging integration requires new review.
//
// Dependencies must be prepared independently by a future privileged UI:
// - an already challenged, single-use StrictOtaDigestGate
// - an already offered, manually confirmed ManualConsentGate
// - independently selected full-transport digest and real private AP peer
// - a separately audited SHA-256 hasher and Digest SHA-256 implementation
// These conditions are HOST FIXTURE ASSUMPTIONS here, not production proofs.
// 2KiB raw HTTP headers and fixed Content-Length body are framed separately;
// NEVER use ESP8266WebServer's ordinary buffered POST parser for this upload.
#include "boot/NativeOtaRawHeaderGate.h"
#include "boot/NativeOtaStrictDigestGate.h"
#include "boot/NativeOtaManualConsentGate.h"
#include "boot/NativeOtaRequestPolicy.h"
#include "boot/NativeOtaIntentGate.h"
#include <array>
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {

enum class StreamReviewPhase : uint8_t {
    Idle, RawHeaders, Body, BodyCompleteAwaitingReview,
    BytesAcceptedForOfflineReviewOnly, Aborted
};

// ReviewSink contract: bool beginForReview(uint32_t exactSignedBytes);
// bool acceptForReview(const uint8_t*,size_t); bool completeForReview();
// void abortReview(). No method may call the real flash Updater.
template<class DigestHash, class IncrementalSha256, class ReviewSink>
class NativeOtaStreamingReview final {
public:
    static constexpr uint32_t kHeaderDeadlineMs = 10'000u;
    static constexpr size_t kHeaderMax = RawOtaHeaderGate::kMaxHeaderBytes;
    NativeOtaStreamingReview(StrictOtaDigestGate<DigestHash>& digest,
                             ManualConsentGate& consent, ReviewSink& sink)
        : digest_(digest), consent_(consent), sink_(sink) {}
    NativeOtaStreamingReview(const NativeOtaStreamingReview&) = delete;
    NativeOtaStreamingReview& operator=(const NativeOtaStreamingReview&) = delete;

    // Username and HA1 originate in a future private owner build. Do not
    // accept either from upload headers or arbitrary client JSON.
    bool start(uint32_t privateApPeer, bool receivedOnActualPrivateAp,
               IntendedPackage selectedKind, const std::array<uint8_t,32>& selectedSignedSha256,
               const char* ownerUsername, const char* privateOwnerHa1,
               uint32_t nowMs) {
        if (phase_!=StreamReviewPhase::Idle) return false;
        if (!receivedOnActualPrivateAp || privateApPeer==0u ||
            !ownerUsername || !privateOwnerHa1 ||
            (selectedKind!=IntendedPackage::SignedExactOem &&
             selectedKind!=IntendedPackage::SignedShino))
            return fail();
        peer_=privateApPeer;
        kind_=selectedKind;
        trustedSelectedHash_=selectedSignedSha256;
        ownerUsername_=ownerUsername;
        ownerHa1_=privateOwnerHa1;
        startedAtMs_=nowMs;
        headerBytes_=0u;
        phase_=StreamReviewPhase::RawHeaders;
        return true;
    }

    // Handles arbitrary network segmentation, including headers and the first
    // payload bytes in the SAME received packet. Never buffers firmware: only
    // fixed 2KiB header and one externally supplied <=4KiB payload span.
    bool feed(const uint8_t* wire, size_t bytes, uint32_t nowMs) {
        if (phase_!=StreamReviewPhase::RawHeaders && phase_!=StreamReviewPhase::Body)
            return false;
        if (!wire || bytes==0u || !tick(nowMs)) return fail();
        size_t position=0u;
        while (position<bytes) {
            if (phase_==StreamReviewPhase::RawHeaders) {
                if (headerBytes_==kHeaderMax) return fail();
                header_[headerBytes_++]=static_cast<char>(wire[position++]);
                if (headerBytes_>=4u &&
                    header_[headerBytes_-4u]=='\r' &&
                    header_[headerBytes_-3u]=='\n' &&
                    header_[headerBytes_-2u]=='\r' &&
                    header_[headerBytes_-1u]=='\n') {
                    if (!reviewHeaders(nowMs)) return fail();
                }
            } else if (phase_==StreamReviewPhase::Body) {
                const uint32_t remaining=expectedBytes_-intent_.receivedBytes();
                const size_t available=bytes-position;
                // Receiving data beyond declared Content-Length must invalidate
                // this whole network segment; never accept a pipelined request.
                if (available>remaining) return fail();
                const size_t count=available>IntentGate::kMaxChunkBytes
                    ? IntentGate::kMaxChunkBytes:available;
                if (!intent_.acceptChunk(peer_,boundToken_,wire+position,count,nowMs))
                    return fail();
                transportSha_.add(wire+position,count);
                if (!sink_.acceptForReview(wire+position,count)) return fail();
                position+=count;
                if (intent_.receivedBytes()==expectedBytes_)
                    phase_=StreamReviewPhase::BodyCompleteAwaitingReview;
            } else {
                // Same TCP packet carried extra bytes after complete body.
                return fail();
            }
        }
        return true;
    }

    // The socket adapter MUST call tick while waiting for more data.
    bool tick(uint32_t nowMs) {
        if (phase_==StreamReviewPhase::RawHeaders) {
            if (static_cast<uint32_t>(nowMs-startedAtMs_)>=kHeaderDeadlineMs)
                return fail();
            return true;
        }
        if (phase_==StreamReviewPhase::Body ||
            phase_==StreamReviewPhase::BodyCompleteAwaitingReview) {
            if (!intent_.checkTimeout(nowMs)) return fail();
            return true;
        }
        return false;
    }

    // Only call once AFTER the socket reader has checked there is no extra
    // body/pipelined data buffered, and it has received exactly Content-Length.
    // This is an informational "bytes checked" outcome, NEVER installation.
    bool finishAfterExactFraming(uint32_t nowMs) {
        if (phase_!=StreamReviewPhase::BodyCompleteAwaitingReview) return false;
        if (!tick(nowMs) ||
            !intent_.finish(peer_,boundToken_,expectedBytes_,nowMs)) return fail();
        uint8_t calculated[32]{};
        transportSha_.end(calculated);
        uint8_t difference=0u;
        for(size_t i=0;i<sizeof(calculated);++i)
            difference|=static_cast<uint8_t>(calculated[i]^trustedSelectedHash_[i]);
        for(auto& byte:calculated) byte=0u;
        if (difference || !sink_.completeForReview()) return fail();
        wipe();
        phase_=StreamReviewPhase::BytesAcceptedForOfflineReviewOnly;
        return true;
    }

    // Disconnect, body truncation, explicit refusal and timeout are terminal.
    void disconnect() { if (phase_!=StreamReviewPhase::Idle &&
                        phase_!=StreamReviewPhase::Aborted &&
                        phase_!=StreamReviewPhase::BytesAcceptedForOfflineReviewOnly) fail(); }
    StreamReviewPhase phase() const { return phase_; }
    uint32_t receivedBodyBytes() const { return intent_.receivedBytes(); }
    size_t headerBytes() const { return headerBytes_; }

private:
    static bool parseToken(const char* token,std::array<uint8_t,16>& out) {
        if (!token) return false;
        for(size_t i=0;i<16u;++i) {
            const char h=token[2u*i],l=token[2u*i+1u];
            if (!lowerHex(h) || !lowerHex(l)) return false;
            out[i]=static_cast<uint8_t>((nibble(h)<<4u)|nibble(l));
        }
        return token[32u]=='\0';
    }
    static bool lowerHex(char c) {return (c>='0'&&c<='9')||(c>='a'&&c<='f');}
    static uint8_t nibble(char c) {
        return static_cast<uint8_t>(c<='9'?c-'0':c-'a'+10);
    }
    bool reviewHeaders(uint32_t nowMs) {
        RawOtaHeaderResult head{};
        if (!RawOtaHeaderGate::inspect(header_.data(),headerBytes_,head) ||
            head.kind!=RawOtaRequestKind::SignedTransport || !head.intentTokenPresent ||
            head.digestValueOffset+head.digestValueLength>headerBytes_ ||
            !parseToken(head.intentToken,boundToken_)) return false;
        // Strict SHA256 Digest is independently checked on the exact raw auth
        // span and binds the ACTUAL route/peer, not a client-selected URI.
        if (!digest_.verify(peer_,head.kind,
                            header_.data()+head.digestValueOffset,
                            head.digestValueLength,ownerUsername_,ownerHa1_,nowMs))
            return false;
        RequestEnvelope env{};
        env.digestAuthenticated=true; // only after strict proof has passed
        env.readCookiePresent=head.readCookiePresent;
        env.reachedFromPrivateAp=true; // future transport must independently verify AP interface
        env.peerIpv4NetworkOrder=peer_; // contract requires NETWORK ORDER
        env.method="POST"; env.host="192.168.4.1";
        env.origin="http://192.168.4.1";
        env.contentType="application/octet-stream";
        env.contentLength=head.contentLength;
        if (!PrivilegedRequestPolicy::preliminaryAccept(
                env,PrivilegedRequestKind::SignedTransport))
            return false;
        if (!consent_.consume(true,true,peer_,kind_,head.contentLength,
                              boundToken_,trustedSelectedHash_,nowMs))
            return false;
        if (!intent_.arm(peer_,boundToken_,head.contentLength,nowMs) ||
            !intent_.start(peer_,boundToken_,head.contentLength,nowMs)) return false;
        // No stage/review sink begins until EVERY previous security gate passes.
        if (!sink_.beginForReview(head.contentLength)) return false;
        expectedBytes_=head.contentLength;
        transportSha_.begin();
        phase_=StreamReviewPhase::Body;
        return true;
    }
    void wipe() {
        for(auto& b:boundToken_) b=0u;
        for(auto& b:trustedSelectedHash_) b=0u;
        for(auto& c:header_) c='\0';
        ownerUsername_=nullptr; ownerHa1_=nullptr;
    }
    bool fail() {
        intent_.abort();
        digest_.abort();
        consent_.abort();
        sink_.abortReview(); // host-only discard, no actual device flash rollback claim
        wipe();
        phase_=StreamReviewPhase::Aborted;
        return false;
    }

    StrictOtaDigestGate<DigestHash>& digest_;
    ManualConsentGate& consent_;
    ReviewSink& sink_;
    IntentGate intent_{};
    IncrementalSha256 transportSha_{};
    std::array<char,kHeaderMax> header_{};
    size_t headerBytes_=0u;
    std::array<uint8_t,16> boundToken_{};
    std::array<uint8_t,32> trustedSelectedHash_{};
    const char* ownerUsername_=nullptr;
    const char* ownerHa1_=nullptr;
    uint32_t peer_=0u,expectedBytes_=0u,startedAtMs_=0u;
    IntendedPackage kind_=IntendedPackage::SignedShino;
    StreamReviewPhase phase_=StreamReviewPhase::Idle;
};

} // namespace ShinoNativeOta
