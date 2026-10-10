// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <cstring>
namespace M9NormalHttpPolicy {
inline int classify(bool get, bool post, const char* path, const char* length,
                    const char* type, const char* transfer) {
    if (*transfer) return 400;
    uint32_t bytes = 0;
    for (const char* p = length; *p; ++p) {
        if (*p < '0' || *p > '9' || bytes > 384) return 413;
        bytes = bytes * 10 + uint32_t(*p - '0');
    }
    if (get && bytes == 0 && (std::strcmp(path, "/status") == 0 ||
        std::strcmp(path, "/api/v1/m9/normal/status") == 0 ||
        std::strcmp(path, "/api/v1/m9/normal/resources") == 0 ||
        std::strcmp(path, "/api/v1/bridge/metrics") == 0)) return 200;
    if (post && std::strcmp(path, "/api/v1/bridge/metrics") == 0) {
        if (bytes < 16 || bytes > 384 || !*length) return 413;
        return std::strcmp(type, "application/json") == 0 ? 200 : 415;
    }
    return 404;
}
} // namespace M9NormalHttpPolicy
