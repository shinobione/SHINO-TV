// SPDX-License-Identifier: GPL-3.0-or-later
// HOST ONLY: exercise the actual C++ ordering barrier with an OpenSSL-backed
// fake core that emulates the important ESP8266 Updater.end(false) contract:
// RSA/SHA-256 verification BEFORE "eboot scheduled". Not a device/core test.
#include "recovery/SignedOemCommitBarrier.h"
#include <openssl/evp.h>
#include <openssl/pem.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#ifndef SHINO_USE_PRODUCTION_OEM_PIN
#include "test_pin.h" // Created in a disposable host-only fixture directory.
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

struct HostSha256 final {
    EVP_MD_CTX* ctx = EVP_MD_CTX_new();
    HostSha256() {
        if (ctx == nullptr) throw std::runtime_error("SHA context allocation failed");
    }
    HostSha256(const HostSha256&) = delete;
    HostSha256& operator=(const HostSha256&) = delete;
    ~HostSha256() { EVP_MD_CTX_free(ctx); }
    void begin() {
        if (EVP_DigestInit_ex(ctx, EVP_sha256(), nullptr) != 1)
            throw std::runtime_error("SHA init failed");
    }
    void add(const uint8_t* data, size_t n) {
        if (EVP_DigestUpdate(ctx, data, n) != 1)
            throw std::runtime_error("SHA update failed");
    }
    void end(uint8_t out[32]) {
        unsigned int written = 0u;
        if (EVP_DigestFinal_ex(ctx, out, &written) != 1 || written != 32u)
            throw std::runtime_error("SHA finalize failed");
    }
};

struct HostSignedCore final {
    EVP_PKEY* publicKey = nullptr;
    bool failBegin = false;
    bool shortWrite = false;
    bool failStage = false;
    bool fault = false;
    bool signedOnly = true;
    bool scheduled = false;
    uint32_t expectedSize = 0u;
    int beginCalls = 0;
    int endCalls = 0;
    std::vector<uint8_t> staged{};

    explicit HostSignedCore(EVP_PKEY* key) : publicKey(key) {}
    bool begin(uint32_t exactSignedBytes, ShinoOemPrecommit::SignedApplicationOnlyTag) {
        ++beginCalls;
        if (failBegin || !signedOnly || exactSignedBytes != OemPin::kTransportBytes) {
            fault = true;
            return false;
        }
        expectedSize = exactSignedBytes;
        staged.reserve(expectedSize);
        return true;
    }
    size_t write(const uint8_t* bytes, size_t len) {
        if (fault || expectedSize == 0u || len > expectedSize - staged.size()) {
            fault = true;
            return 0u;
        }
        if (failStage) { fault = true; return 0u; }
        const size_t written = shortWrite && len > 0u ? len - 1u : len;
        staged.insert(staged.end(), bytes, bytes + written);
        if (written != len) fault = true;
        return written;
    }
    bool hasError() const { return fault; }
    bool isFinished() const { return !fault && staged.size() == expectedSize; }

    bool end(bool evenIfRemaining) {
        ++endCalls;
        if (evenIfRemaining || fault || !signedOnly || publicKey == nullptr ||
            !isFinished() || staged.size() != OemPin::kTransportBytes) {
            fault = true;
            return false;
        }
        // Mirror core signed-format framing: RAW || RSA256 bytes || u32 LE.
        const uint32_t n = OemPin::kTransportBytes;
        const uint32_t tail = n - 4u;
        const uint32_t signatureLength = uint32_t(staged[tail]) |
            (uint32_t(staged[tail+1u]) << 8u) |
            (uint32_t(staged[tail+2u]) << 16u) |
            (uint32_t(staged[tail+3u]) << 24u);
        if (signatureLength != 256u) { fault = true; return false; }
        using Ctx = std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)>;
        Ctx context(EVP_MD_CTX_new(), EVP_MD_CTX_free);
        if (!context ||
            EVP_DigestVerifyInit(context.get(), nullptr, EVP_sha256(), nullptr, publicKey) != 1 ||
            EVP_DigestVerifyUpdate(context.get(), staged.data(), OemPin::kRawBytes) != 1 ||
            EVP_DigestVerifyFinal(context.get(), staged.data()+OemPin::kRawBytes, 256u) != 1) {
            fault = true;
            return false; // An invalid signature MUST NOT schedule eboot.
        }
        scheduled = true;
        return true;
    }
};
using Barrier = ShinoOemPrecommit::SignedOemCommitBarrier<HostSha256, OemPin, HostSignedCore>;
using CommitPhase = ShinoOemPrecommit::CommitPhase;

int main(int argc, char** argv) {
    // mode: success, rsa_invalid, raw_invalid, unsigned, wrong_size,
    // denied, signer_off, begin_fail, short_write, stage_fail, abort,
    // wrong_total, oversized_chunk, duplicate.
    if (argc != 5) {
        std::cerr << "usage: <package> <public PEM> <mode> <chunk size>\n";
        return 2;
    }
    try {
        std::ifstream in(argv[1], std::ios::binary);
        if (!in) return 2;
        std::vector<uint8_t> package((std::istreambuf_iterator<char>(in)),
                                      std::istreambuf_iterator<char>());
        const std::string mode(argv[3]);
        const size_t chunk = std::stoul(argv[4]);
        if (!chunk || package.size() > UINT32_MAX) return 2;
        struct FileCloser { void operator()(std::FILE* f) const { if (f) std::fclose(f); } };
        std::unique_ptr<std::FILE, FileCloser> file(std::fopen(argv[2], "rb"));
        if (!file) return 2;
        std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)> key(
            PEM_read_PUBKEY(file.get(), nullptr, nullptr, nullptr), EVP_PKEY_free);
        if (!key) return 2;

        HostSignedCore core(key.get());
        core.failBegin = mode == "begin_fail";
        core.shortWrite = mode == "short_write";
        core.failStage = mode == "stage_fail";
        Barrier barrier(core);
        const bool privileged = mode != "denied";
        const bool verifier = mode != "signer_off";
        const uint32_t declared = mode == "wrong_size"
            ? OemPin::kTransportBytes - 1u : OemPin::kTransportBytes;
        bool accepted = barrier.begin(privileged, verifier, declared);
        if (mode == "abort" && accepted) {
            if (!package.empty() && !barrier.add(package.data(), 1u)) return 1;
            barrier.abort();
            accepted = false;
        } else if (accepted) {
            for (size_t at=0; at<package.size(); at+=chunk) {
                const size_t n = package.size()-at < chunk ? package.size()-at : chunk;
                if (!barrier.add(package.data()+at,n)) {
                    accepted = false; break;
                }
            }
            if (accepted) {
                const uint32_t finalSize = mode == "wrong_total"
                    ? OemPin::kTransportBytes - 1u : static_cast<uint32_t>(package.size());
                accepted = barrier.complete(finalSize);
            }
        }
        // Verify no retry, duplicate completion or second arm succeeds.
        if (barrier.complete(OemPin::kTransportBytes)) return 1;
        if (barrier.begin(true, true, OemPin::kTransportBytes)) return 1;
        const bool happy = mode == "success" || mode == "duplicate";
        const bool rsaBad = mode == "rsa_invalid";
        if ((accepted != happy) || (core.scheduled != happy) ||
            core.endCalls != ((happy || rsaBad) ? 1 : 0)) {
            std::cerr << "FAIL " << mode << " accepted=" << accepted
                      << " scheduled=" << core.scheduled << " endCalls=" << core.endCalls
                      << " beginCalls=" << core.beginCalls
                      << " phase=" << int(barrier.phase()) << '\n';
            return 1;
        }
        if (happy && barrier.phase() != CommitPhase::CoreAccepted) return 1;
        if (!happy && barrier.phase() != CommitPhase::Aborted) return 1;
        if ((mode == "denied" || mode == "signer_off" || mode == "wrong_size") &&
            core.beginCalls != 0) return 1;
        std::cout << "PASS " << mode << " core_end_calls=" << core.endCalls
                  << " eboot_scheduled=" << core.scheduled
                  << " accepted=" << accepted
                  << " HOST_EMULATION_ONLY NO_DEVICE_WRITER\n";
        return 0;
    } catch(const std::exception& ex) {
        std::cerr << ex.what() << '\n';
        return 2;
    }
}
