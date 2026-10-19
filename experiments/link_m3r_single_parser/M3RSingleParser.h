// M3-R OFFLINE adapter: ONE M3-C buffer/parser, not M3-Q + M3-C.
// Never registered on a live server or allowed to apply a display mode.
// Precondition PROVEN ONLY by M3-P's pinned Core patch + M3-O hook:
// the exact POST request line was consumed and verified before handoff.
#pragma once
#include <cstddef>
#include <cstdint>
#include "../link_m3c_crypto/M3CAuthenticatedIngress.h"

namespace ShinoM3R {
using ShinoM3C::Gate;
using ShinoM3C::Phase;

static constexpr const char kValidatedFirstLine[] =
    "POST /api/v1/display/mode HTTP/1.1\r\n";
static constexpr size_t kWireHeadersMax = 960u;

// Single parser: the exact M3-P first line must be reintroduced into the
// SAME M3-C Gate which both parses and authenticates the received headers.
// Do NOT allocate ShinoM3Q::HeaderGuard alongside this Gate.
// No bytes of the body are read before AuthenticatedHeader.
template<class Crypto, class Client, class Clock, class Yield>
__attribute__((noinline)) Phase readAuthenticatedHeaders(
    Client& client, Gate& gate, const uint8_t key[32],
    Clock clock, Yield yield, uint32_t started) {
    if (!key || gate.phase() != Phase::Header)
        return gate.closeOrTimeout();
    for (size_t i=0u; i<sizeof(kValidatedFirstLine)-1u; ++i) {
        const uint32_t elapsed=static_cast<uint32_t>(clock()-started);
        if (elapsed >= Gate::kHeaderDeadlineMs)
            return gate.closeOrTimeout();
        if (gate.headerByte<Crypto>(kValidatedFirstLine[i],elapsed,key)
            !=Phase::Header)
            return gate.closeOrTimeout();
    }
    size_t wireUsed=0u;
    while (gate.phase()==Phase::Header) {
        const uint32_t elapsed=static_cast<uint32_t>(clock()-started);
        if (elapsed >= Gate::kHeaderDeadlineMs)
            return gate.closeOrTimeout();
        if (client.available()<=0) {
            if (!client.connected())return gate.closeOrTimeout();
            yield();
            continue;
        }
        if (wireUsed>=kWireHeadersMax)return gate.closeOrTimeout();
        const int value=client.read(); // EXACTLY ONE received byte
        if (value<0 || value>126 ||
            (value<32 && value!='\r' && value!='\n'))
            return gate.closeOrTimeout();
        ++wireUsed;
        const Phase result=gate.headerByte<Crypto>(
            static_cast<char>(value),
            static_cast<uint32_t>(clock()-started),key);
        if (result!=Phase::Header)
            return result; // only AuthenticatedHeader enables body handling
    }
    return gate.phase();
}

// Offline FIN/body experiment: no display writer and no state mutation.
// EOF must follow exactly the signed body. The caller must NOT apply modes
// from this function; Gate::VerifiedFrame is just a lab result.
template<class Crypto, class Client, class Clock, class Yield>
__attribute__((noinline)) Phase verifyFrameWithoutSideEffect(
    Client& client, Gate& gate, Clock clock, Yield yield, uint32_t started) {
    if (gate.phase()!=Phase::AuthenticatedHeader)
        return gate.closeOrTimeout();
    while (true) {
        const uint32_t elapsed=static_cast<uint32_t>(clock()-started);
        if (elapsed>=Gate::kBodyDeadlineMs)
            return gate.closeOrTimeout();
        if (gate.phase()==Phase::BodyDigestMatched) {
            if (client.available()>0)return gate.closeOrTimeout();
            if (!client.connected())
                return gate.finishAfterExactFraming(true,0u,elapsed);
            yield();
            continue;
        }
        if (gate.phase()!=Phase::AuthenticatedHeader)
            return gate.closeOrTimeout();
        if (client.available()<=0) {
            if (!client.connected())return gate.closeOrTimeout();
            yield();
            continue;
        }
        const int value=client.read();
        if (value<0 || value>255)return gate.closeOrTimeout();
        const Phase result=gate.bodyByte<Crypto>(
            static_cast<uint8_t>(value),
            static_cast<uint32_t>(clock()-started));
        if (result==Phase::Reject)return result;
    }
}
} // namespace ShinoM3R
