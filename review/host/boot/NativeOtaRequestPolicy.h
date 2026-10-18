// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1: PURE request-envelope policy, host-tested and NOT integrated into
// HTTP server or updater. Calling this is never permission to write flash.
// digestAuthenticated is an input from a future independently audited HTTP
// Digest handler; a read cookie is intentionally NOT accepted as authority.
// A separate manual user-intent challenge, signed package verifier and the
// single-use transfer gate are REQUIRED outside this preliminary filter.
#include <cstdint>
#include <cstring>

namespace ShinoNativeOta {

enum class PrivilegedRequestKind : uint8_t { Arm, SignedTransport };

struct RequestEnvelope {
    bool digestAuthenticated = false;
    bool readCookiePresent = false;       // Informational; confers no permission.
    bool reachedFromPrivateAp = false;    // Supplied by future network adapter.
    uint32_t peerIpv4NetworkOrder = 0;   // e.g. 192.168.4.3 -> 0xC0A80403.
    const char* method = nullptr;
    const char* host = nullptr;
    const char* origin = nullptr;
    const char* contentType = nullptr;
    uint32_t contentLength = 0;
};

class PrivilegedRequestPolicy final {
public:
    // Full host+origin must match our isolated SHINO AP endpoint exactly.
    // No wildcards, localhost, home LAN, null/absent Origin, ports other
    // than the device's default port, cross-origin fetches or redirects.
    static bool preliminaryAccept(const RequestEnvelope& r,
                                  PrivilegedRequestKind kind) {
        if (!r.digestAuthenticated || !r.reachedFromPrivateAp) return false;
        if ((r.peerIpv4NetworkOrder & 0xFFFFFF00u) != 0xC0A80400u) return false;
        const uint32_t lastOctet = r.peerIpv4NetworkOrder & 0xFFu;
        if (lastOctet < 2 || lastOctet > 254) return false;
        if (!equal(r.method, "POST") ||
            !equal(r.host, "192.168.4.1") ||
            !equal(r.origin, "http://192.168.4.1")) return false;
        if (kind == PrivilegedRequestKind::Arm)
            return equal(r.contentType, "application/json") &&
                   r.contentLength >= 16 && r.contentLength <= 384;
        if (kind == PrivilegedRequestKind::SignedTransport)
            return equal(r.contentType, "application/octet-stream") &&
                   r.contentLength >= (64000u + 256u + 4u) &&
                   r.contentLength <= (494144u + 256u + 4u);
        return false;
    }

private:
    static bool equal(const char* supplied, const char* expected) {
        if (supplied == nullptr) return false;
        // Compare only expected length, stopping at the FIRST mismatch or NUL;
        // never use a fixed-length memchr that may read past a short C string.
        size_t i = 0;
        for (; expected[i] != '\0'; ++i) {
            if (supplied[i] != expected[i]) return false;
        }
        return supplied[i] == '\0';
    }
};

}  // namespace ShinoNativeOta
