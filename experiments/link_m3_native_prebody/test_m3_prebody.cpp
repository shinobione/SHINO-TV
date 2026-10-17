// M3-B host C++ source-executed, isolated from firmware and network.
#include "M3ModePrebodySyntax.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <utility>
#include <vector>

using ShinoM3::PrebodySyntax;
using ShinoM3::Scan;
static const char* kHost = "192.168.1.46";
static const char* kTx = "00000000000000000000000000000001";

static std::string headers() {
    return "POST /api/v1/display/mode HTTP/1.1\r\n"
           "Host: 192.168.1.46\r\n"
           "Content-Type: application/json\r\n"
           "Content-Length: 230\r\n"
           "Authorization: Digest username=\"lab\", nonce=\"NOT-A-PROOF\"\r\n"
           "X-Shino-Tx: 00000000000000000000000000000001\r\n"
           "Connection: close\r\n\r\n";
}

static std::string replace(std::string src, const std::string& from,
                           const std::string& to) {
    const size_t pos = src.find(from);
    assert(pos != std::string::npos);
    src.replace(pos, from.size(), to);
    return src;
}

static Scan feed(const std::string& raw, uint32_t timestamp,
                 size_t* used = nullptr, ShinoM3::Candidate* candidate = nullptr,
                 const char* expectedHost = kHost) {
    PrebodySyntax scanner(expectedHost);
    Scan result = Scan::More;
    for (size_t i = 0; i < raw.size(); ++i) {
        result = scanner.feed(raw[i], timestamp);
        if (result != Scan::More) break;
    }
    if (used) *used = scanner.consumed();
    if (candidate) *candidate = scanner.candidate();
    assert(!scanner.authorizedToReadBody());
    return result;
}

static void testOnlyHeaderIsConsumed() {
    std::string header = headers();
    const std::string withBody = header + "BODY-INTENTIONALLY-UNREAD";
    size_t consumed = 0;
    ShinoM3::Candidate info{};
    assert(feed(withBody, 100u, &consumed, &info) == Scan::CandidateSyntaxOnly);
    assert(consumed == header.size());
    assert(info.contentLength == 230u);
    assert(std::strcmp(info.transaction, kTx) == 0);
    assert(info.authLength >= 8u && info.authOffset < header.size());
    assert(header.compare(info.authOffset, 7u, "Digest ") == 0);
    // Accepted syntax NEVER changes the zero-body-authority rule.
    PrebodySyntax scanner(kHost);
    for (const char c : header) scanner.feed(c, 0u);
    assert(scanner.state() == Scan::CandidateSyntaxOnly);
    assert(!scanner.authorizedToReadBody());
    assert(scanner.feed('Z', 0u) == Scan::CandidateSyntaxOnly); // no increment
    assert(scanner.consumed() == header.size());
}

static void testMalformedRefused() {
    const std::string good = headers();
    std::vector<std::string> bad = {
        replace(good, "POST /api/v1/display/mode", "GET /api/v1/display/mode"),
        replace(good, "POST /api/v1/display/mode", "POST /api/v1/bridge/metrics"),
        replace(good, "POST /api/v1/display/mode", "POST /api/v1/display/mode?mode=MUSIC"),
        replace(good, "HTTP/1.1", "HTTP/1.0"),
        replace(good, "Host: 192.168.1.46", "Host: 192.168.1.47"),
        replace(good, "Host: 192.168.1.46", "Host: 192.168.1.46:80"),
        replace(good, "Host: 192.168.1.46", "Host: 8.8.8.8"),
        replace(good, "Content-Type: application/json", "Content-Type: text/plain"),
        replace(good, "Content-Length: 230", "Content-Length: -1"),
        replace(good, "Content-Length: 230", "Content-Length: 024"),
        replace(good, "Content-Length: 230", "Content-Length: 241"),
        replace(good, "Content-Length: 230", "Content-Length: 65535"),
        replace(good, "Content-Length: 230", "Content-Length: 0"),
        replace(good, "Content-Length: 230", "Content-Length: 1e2"),
        replace(good, "Content-Length: 230", "Content-Length: 2.3"),
        replace(good, "Authorization: Digest", "Authorization: Basic"),
        replace(good, "Authorization: Digest", "Authorization: Bearer"),
        replace(good, "X-Shino-Tx: " + std::string(kTx),
                "X-Shino-Tx: 00000000000000000000000000000000"),
        replace(good, "X-Shino-Tx: " + std::string(kTx),
                "X-Shino-Tx: 0000000000000000000000000000000A"),
        replace(good, "X-Shino-Tx: " + std::string(kTx),
                "X-Shino-Tx: 0000000000000000000000000000000"),
        replace(good, "Connection: close", "Connection: keep-alive"),
        replace(good, "Host: ", "Host:\t"),
        replace(good, "\r\nConnection: close",
                "\r\nTransfer-Encoding: chunked\r\nConnection: close"),
        replace(good, "\r\nConnection: close",
                "\r\nExpect: 100-continue\r\nConnection: close"),
        replace(good, "\r\nConnection: close",
                "\r\nContent-Encoding: gzip\r\nConnection: close"),
        replace(good, "\r\nConnection: close",
                "\r\nOrigin: http://192.168.1.46\r\nConnection: close"),
        replace(good, "\r\nConnection: close",
                "\r\nUser-Agent: TEST\r\nConnection: close"),
        replace(good, "\r\nConnection: close",
                "\r\nHost: 192.168.1.46\r\nConnection: close"),
        replace(good, "\r\nConnection: close",
                "\r\nhOsT: 192.168.1.46\r\nConnection: close"),
        replace(good, "\r\nConnection: close",
                "\r\nContent-Length: 230\r\nConnection: close"),
        replace(good, "\r\nConnection: close",
                "\r\nX-Shino-Tx: " + std::string(kTx)
                + "\r\nConnection: close"),
        replace(good, "\r\nConnection: close",
                "\r\nAuthorization: Digest fake\r\nConnection: close"),
        replace(good, "\r\nConnection: close", "\r\nConne ction: close"),
        replace(good, "\r\nConnection: close", "\r\nConnection : close"),
        replace(good, "\r\nConnection: close", "\r\nConnection: close\t"),
        replace(good, "\r\nConnection: close", "\r\nConnection: close\r\n\n"),
        replace(good, "\r\nConnection: close",
                "\r\nX-Shino-Tx: 00000000000000000000000000000002\r\nConnection: close"),
        replace(good, "Host: 192.168.1.46", "Host: 192.168.1.46\r\n"),
    };
    // A single LF terminator may never be accepted.
    bad.push_back(replace(good, "HTTP/1.1\r\n", "HTTP/1.1\n"));
    bad.push_back(replace(good, "Content-Type: application/json",
                          "Content-Type: application/\vjson"));
    bad.push_back(replace(good, "Content-Type: application/json",
                          "Content-Type: application/\xC3\xA9json"));
    for (size_t i = 0; i < bad.size(); ++i) {
        const Scan s = feed(bad[i], 2u);
        if (s != Scan::Reject) {
            std::cerr << "Unsafe syntactic acceptance case " << i
                      << " (state " << int(s) << ")\n";
            std::abort();
        }
    }
}

static void testBoundedFramingAndTiming() {
    const std::string good = headers();
    assert(feed(good, 1001u) == Scan::Reject);
    assert(feed(good, 1000u) == Scan::CandidateSyntaxOnly);
    assert(feed(good.substr(0, good.size() - 1), 0u) == Scan::More);
    assert(feed(std::string(513, 'A'), 0u) == Scan::Reject);
    const std::string huge = replace(good, "Content-Type: application/json",
                                     "Content-Type: " + std::string(260, 'a'));
    assert(feed(huge, 0u) == Scan::Reject);
    assert(feed(good, 0u, nullptr, nullptr, "10.0.0.1") == Scan::Reject);
    assert(feed(good, 0u, nullptr, nullptr, nullptr) == Scan::Reject);
    // Deliberately only syntax: even forged Digest passes text checks, but
    // authorizedToReadBody() stays false and no body is consumed.
    assert(feed(replace(good, "Digest username=\"lab\", nonce=\"NOT-A-PROOF\"",
                        "Digest ATTACKER-FORGED"), 0u)
           == Scan::CandidateSyntaxOnly);
}

int main() {
    testOnlyHeaderIsConsumed();
    testMalformedRefused();
    testBoundedFramingAndTiming();
    std::cout << "M3B_PREBODY_SYNTAX_NATIVE_HOST_PASS_REJECT_ONLY\n";
}
