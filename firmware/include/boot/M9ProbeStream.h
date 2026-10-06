// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace M9ProbeStream {
// Exact algorithm shared by the target adapter and host fault-injection tests.
// Reader supplies bounded reads/eof, Hasher supplies SHA256, Seed/Observer do
// not allocate or mutate filesystem state. Short positive reads are allowed.
template<class Hasher>
struct Workspace {
    uint8_t buffer[256];
    Hasher hash;
    uint8_t actual[32];
    bool active = false;
};

// Synchronous ownership spans observer/yield calls. Nested validation must
// fail before touching scratch, the reader, hash, or checked-byte counter.
template<class Hasher>
class Lease {
public:
    explicit Lease(Workspace<Hasher>& workspace) : workspace_(workspace) { workspace_.active = true; }
    ~Lease() { workspace_.active = false; }
    Lease(const Lease&) = delete;
    Lease& operator=(const Lease&) = delete;
private:
    Workspace<Hasher>& workspace_;
};

template<class Reader, class Hasher, class Seed, class Observer>
bool validate(Reader& file, uint32_t expectedBytes, const uint8_t expectedHash[32],
              Workspace<Hasher>& workspace, Seed seed, Observer observe, uint32_t& checkedBytes) {
    static_assert(sizeof(workspace.buffer) == 256, "Streaming read bound changed");
    if (workspace.active) return false;
    Lease<Hasher> lease(workspace);
    uint32_t consumed = 0;
    workspace.hash.begin();
    while (consumed < expectedBytes) {
        const size_t remaining = expectedBytes - consumed;
        const size_t wanted = remaining < sizeof(workspace.buffer) ? remaining : sizeof(workspace.buffer);
        const int got = file.read(workspace.buffer, wanted);
        if (got <= 0 || static_cast<size_t>(got) > wanted) return false;
        if (!seed(consumed, workspace.buffer, static_cast<size_t>(got))) return false;
        workspace.hash.update(workspace.buffer, static_cast<size_t>(got));
        consumed += static_cast<uint32_t>(got);
        observe();
    }
    if (file.read() != -1) return false; // Reject extra bytes even if size() lied.
    workspace.hash.end(workspace.actual);
    if (std::memcmp(workspace.actual, expectedHash, sizeof(workspace.actual)) != 0) return false;
    checkedBytes += consumed; // Count only completely validated payloads.
    return true;
}
} // namespace M9ProbeStream
