// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
namespace M9StageAConfig {
constexpr size_t BYTES = 85;
// Exact blank seed is stronger than permissive JSON parsing: no unknown keys,
// credentials, duplicate keys, trailing bytes, or migration semantics survive.
template<class Reader, class Seed> bool validate(Reader& file, Seed seed) {
    if (file.size() != BYTES) return false;
    uint8_t buffer[32];
    size_t offset = 0;
    while (offset < BYTES) {
        const size_t wanted = BYTES - offset < sizeof(buffer) ? BYTES - offset : sizeof(buffer);
        const size_t received = file.read(buffer, wanted);
        if (received == 0 || received > wanted) return false;
        for (size_t i = 0; i < received; ++i)
            if (buffer[i] != seed(offset + i)) return false;
        offset += received;
    }
    return file.read() == -1;
}
} // namespace M9StageAConfig
