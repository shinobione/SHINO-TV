// SPDX-License-Identifier: GPL-3.0-or-later
// Compile-only integration of the exact OEM SHA-256 guard with the very same
// native BearSSL SHA256 primitives provided by ESP8266 Arduino Core 3.1.2.
// Deliberately NOT included/called by FirstBootBridge or FactoryRollback:
// there is NO signed OTA route, no Updater state change and NO FLASH WRITER.
#include "recovery/SignedOemPrecommitGate.h"
#include <bearssl/bearssl_hash.h>

namespace ShinoOemPrecommit {
namespace {
struct BearSslSha256 final {
    br_sha256_context context{};
    void begin() { br_sha256_init(&context); }
    void add(const uint8_t* data, size_t len) {
        br_sha256_update(&context, data, len);
    }
    void end(uint8_t out[32]) { br_sha256_out(&context, out); }
};
} // namespace

// Explicit instantiation type-checks ALL of the real C++ guard's methods
// against the on-device BearSSL adapter at ESP8266 compile time. There is no
// callable route or helper that accepts an OTA package in this phase.
template class SignedOemPrecommitGate<BearSslSha256, ProductionV9044Pin>;
} // namespace ShinoOemPrecommit
