// SPDX-License-Identifier: GPL-3.0-or-later
// Host-run the SAME C++ precommit logic as dormant ESP8266 integration,
// with OpenSSL EVP as the test SHA256 backend. No HTTP, Update or flash calls.
#include "recovery/SignedOemPrecommitGate.h"
#include <openssl/evp.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef SHINO_USE_PRODUCTION_OEM_PIN
#include "test_pin.h" // Generated inside disposable test directory only.
struct TestPin final {
    static constexpr uint32_t kRawBytes = 494144u;
    static constexpr uint32_t kRsa2048Bytes = 256u;
    static constexpr uint32_t kTransportBytes = 494404u;
    static constexpr char kExpectedSha256[] = SHINO_TEST_PIN_SHA256;
    static constexpr std::array<uint8_t, 4> kExpectedEspHeader{{0xE9, 2, 2, 0x40}};
};
using OemPin = TestPin;
#else
using OemPin = ShinoOemPrecommit::ProductionV9044Pin;
#endif

struct HostOpenSslSha256 final {
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    HostOpenSslSha256() {
        if (ctx == nullptr) throw std::runtime_error("EVP_MD_CTX_new failed");
    }
    HostOpenSslSha256(const HostOpenSslSha256&) = delete;
    HostOpenSslSha256& operator=(const HostOpenSslSha256&) = delete;
    ~HostOpenSslSha256() { EVP_MD_CTX_free(ctx); }
    void begin() {
        if (EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr) != 1)
            throw std::runtime_error("EVP SHA init failed");
    }
    void add(const uint8_t* data, size_t n) {
        if (EVP_DigestUpdate(ctx, data, n) != 1)
            throw std::runtime_error("EVP SHA update failed");
    }
    void end(uint8_t out[32]) {
        unsigned int count = 0u;
        if (EVP_DigestFinal_ex(ctx, out, &count) != 1 || count != 32u)
            throw std::runtime_error("EVP SHA final failed");
    }
};
using Gate = ShinoOemPrecommit::SignedOemPrecommitGate<HostOpenSslSha256, OemPin>;
using Phase = ShinoOemPrecommit::Phase;

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "usage: signed-oem-probe <local-package> <chunk-size> <expected-pass-0-or-1>\n";
        return 2;
    }
    try {
        std::ifstream in(argv[1], std::ios::binary);
        if (!in) return 2;
        std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(in)),
                                   std::istreambuf_iterator<char>());
        const size_t chunk = static_cast<size_t>(std::stoul(argv[2]));
        const bool expectPass = std::stoi(argv[3]) == 1;
        if (chunk == 0u || bytes.size() > UINT32_MAX) return 2;

        Gate gate;
        bool accepted = gate.begin(static_cast<uint32_t>(OemPin::kTransportBytes));
        size_t at = 0u;
        if (accepted) {
            while (at < bytes.size()) {
                const size_t n = (bytes.size() - at < chunk) ? bytes.size() - at : chunk;
                if (!gate.add(bytes.data() + at, n)) {
                    accepted = false;
                    break;
                }
                at += n;
            }
        }
        if (accepted)
            accepted = gate.finish(static_cast<uint32_t>(bytes.size()));
        if (accepted && gate.phase() != Phase::ExactRawAwaitingCoreSignature) return 1;
        if (accepted && gate.finish(static_cast<uint32_t>(bytes.size()))) return 1;
        if (accepted && gate.begin(OemPin::kTransportBytes)) return 1;
        if (accepted != expectPass) {
            std::cerr << "unexpected raw gate result: accepted=" << accepted
                      << ", expected=" << expectPass << ", bytes=" << bytes.size()
                      << ", last phase=" << static_cast<int>(gate.phase()) << "\n";
            return 1;
        }

        if (expectPass) {
            Gate aborted;
            if (!aborted.begin(OemPin::kTransportBytes)) return 1;
            if (!aborted.add(bytes.data(), 1)) return 1;
            aborted.abort();
            if (aborted.phase() != Phase::Aborted) return 1;
            if (aborted.add(bytes.data() + 1, 1)) return 1;
            if (aborted.begin(OemPin::kTransportBytes)) return 1;
            Gate early;
            if (!early.begin(OemPin::kTransportBytes)) return 1;
            if (!early.add(bytes.data(), 1)) return 1;
            if (early.finish(OemPin::kTransportBytes)) return 1;
            if (early.phase() != Phase::Aborted) return 1;
            Gate lie;
            if (!lie.begin(OemPin::kTransportBytes)) return 1;
            for (size_t i = 0; i < bytes.size(); i += 4096u) {
                size_t n = (bytes.size() - i < 4096u) ? bytes.size() - i : 4096u;
                if (!lie.add(bytes.data() + i, n)) return 1;
            }
            if (lie.finish(OemPin::kTransportBytes - 1u)) return 1;
            if (lie.phase() != Phase::Aborted) return 1;
        }
        std::cout << "PASS: signed OEM raw precommit " << (accepted ? "exact" : "rejected")
                  << ", no signature acceptance/HTTP/Update/flash writer.\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << ex.what() << "\n";
        return 2;
    }
}
