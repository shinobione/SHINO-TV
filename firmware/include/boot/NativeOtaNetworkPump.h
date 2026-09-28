// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1 compile-only prospective ESP8266 WiFiClient reader. NOT a listener.
// No WiFiServer binding, no port ownership, no HTTP response, no real Digest
// challenge issuer, no Updater/flash/FS/reboot. A future vetted single-owner
// port-80 ingress must explicitly supply a prechallenged review state.
// One bounded 512-byte read buffer; at most two reads per cooperative poll.
// Data after Content-Length is rejected by the existing review receiver.
// Success means OFFLINE REVIEW ONLY, never an application installation.
#include "boot/NativeOtaStreamingReview.h"
#include <array>
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {

enum class NetworkPumpResult : uint8_t {
    Pending, BytesReviewedOnly, Rejected
};

template<class Client, class Review>
class NativeOtaNetworkPump final {
public:
    static constexpr size_t kReadBytes = 512u;
    static constexpr size_t kReadsPerPoll = 2u;
    NativeOtaNetworkPump() = default;
    NativeOtaNetworkPump(const NativeOtaNetworkPump&) = delete;
    NativeOtaNetworkPump& operator=(const NativeOtaNetworkPump&) = delete;

    // Client is BORROWED and must belong to an independently audited,
    // unique-port listener. Review.start/consent/proof are external and
    // MUST NOT be inferred from presence of a read-only dashboard cookie.
    NetworkPumpResult poll(Client& client, Review& review, uint32_t nowMs) {
        if (result_ != NetworkPumpResult::Pending) return result_;
        if (!review.tick(nowMs)) return reject(client, review);

        for (size_t readIndex=0u; readIndex<kReadsPerPoll; ++readIndex) {
            const int available = client.available();
            if (available<0) return reject(client, review);
            if (available==0) break;
            const size_t requested=static_cast<size_t>(available)>kReadBytes
                ? kReadBytes:static_cast<size_t>(available);
            const int got=client.read(bytes_.data(),requested);
            if (got<=0 || static_cast<size_t>(got)>requested)
                return reject(client, review);
            if (!review.feed(bytes_.data(),static_cast<size_t>(got),nowMs))
                return reject(client, review);
        }

        // TCP FIN is the only end-of-body signal for the dedicated future
        // connection. Drain available queued bytes even after connected()
        // becomes false. Never accept while the peer can append more data.
        const int remaining=client.available();
        if (remaining<0) return reject(client, review);
        if (remaining==0 && !client.connected()) {
            if (!review.finishAfterExactFraming(nowMs))
                return reject(client,review);
            result_=NetworkPumpResult::BytesReviewedOnly;
            client.stop();
            return result_;
        }
        return NetworkPumpResult::Pending;
    }

    // Explicit local cancellation or transport loss is terminal and cannot
    // turn into resuming from partial staging or an implicit retry.
    void cancel(Client& client, Review& review) {
        if (result_!=NetworkPumpResult::Pending) return;
        (void)reject(client,review);
    }
    NetworkPumpResult result() const {return result_;}

private:
    NetworkPumpResult reject(Client& client,Review& review) {
        review.disconnect();
        result_=NetworkPumpResult::Rejected;
        client.stop();
        return result_;
    }

    std::array<uint8_t,kReadBytes> bytes_{};
    NetworkPumpResult result_=NetworkPumpResult::Pending;
};

} // namespace ShinoNativeOta
