// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace M9ProbeStream {
// Exact algorithm shared by the target adapter and host fault-injection tests.
// Reader supplies bounded reads/eof, Hasher supplies SHA256, Seed/Observer do
// not allocate or mutate filesystem state. Short positive reads are allowed.
template<class Reader, class Hasher, class Seed, class Observer>
bool validate(Reader& file, uint32_t expectedBytes, const uint8_t expectedHash[32],
              Hasher& hash, Seed seed, Observer observe, uint32_t& checkedBytes) {
    uint8_t buffer[256];
    static_assert(sizeof(buffer) <= 512, "Unreviewed read buffer");
    uint32_t consumed = 0;
    hash.begin();
    while (consumed < expectedBytes) {
        const size_t remaining = expectedBytes - consumed;
        const size_t wanted = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
        const int got = file.read(buffer, wanted);
        if (got <= 0 || static_cast<size_t>(got) > wanted) return false;
        if (!seed(consumed, buffer, static_cast<size_t>(got))) return false;
        hash.update(buffer, static_cast<size_t>(got));
        consumed += static_cast<uint32_t>(got);
        observe();
    }
    if (file.read() != -1) return false; // Reject extra bytes even if size() lied.
    uint8_t actual[32];
    hash.end(actual);
    if (std::memcmp(actual, expectedHash, sizeof(actual)) != 0) return false;
    checkedBytes += consumed; // Count only completely validated payloads.
    return true;
}
} // namespace M9ProbeStream
