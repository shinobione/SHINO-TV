// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1 host-testable REJECT-ONLY raw HTTP/1.1 header preflight.
// No HTTP server registered, no Digest crypto, no upload body, no Updater,
// no dynamic allocation, filesystem, reboot, public signing key or flash.
//
// A future dedicated TCP streaming adapter must preserve the exact raw
// header bytes and must NOT dispatch OTA through ESP8266WebServer's ordinary
// POST parser (which buffers non-multipart POST content into a String and can
// overwrite Host/Content-Length on duplicate header fields).
//
// This parser requires the buffer to contain EXACTLY request line + headers
// through CRLFCRLF. Body bytes must be held by the future streaming adapter.
// A pass is a syntactic PRECHECK ONLY: a future independent Digest verifier
// MUST authenticate the exact method+URI and one-use challenge/owner consent.
#include "boot/NativeOtaRawHeaderGate.h"
#include <cstddef>
#include <cstdint>

namespace M9Signed {
using ShinoNativeOta::RawOtaHeaderResult; using ShinoNativeOta::RawOtaRequestKind;

class HeaderGate final {
public:
    static constexpr size_t kMaxHeaderBytes = 2048u;
    static constexpr size_t kMaxLineBytes = 768u;
    static constexpr size_t kMaxHeaders = 24u;
    static constexpr size_t kMaxNameBytes = 40u;
    static constexpr size_t kMaxDigestHeaderBytes = 640u;
    static constexpr uint32_t kMaxSignedTransportBytes = 0xFEFF0u + 256u + 4u;

    // No heap, no null-terminated incoming data assumption.
    static bool inspect(const char* data, size_t len, RawOtaHeaderResult& result) {
        result = RawOtaHeaderResult{};
        if (!data || len < 30u || len > kMaxHeaderBytes) return false;
        if (data[len-4u] != '\r' || data[len-3u] != '\n' ||
            data[len-2u] != '\r' || data[len-1u] != '\n') return false;
        for (size_t i = 0; i < len; ++i) {
            if (data[i] == '\0' ||
                (data[i] == '\n' && (i == 0 || data[i-1u] != '\r')) ||
                (data[i] == '\r' && (i+1u >= len || data[i+1u] != '\n')))
                return false;
        }
        size_t lineEnd = 0u;
        if (!endOfLine(data,len,0u,lineEnd) || lineEnd > 110u) return false;
        const Span request{data,lineEnd};
        if (exact(request,"POST /api/v1/bridge/ota/arm HTTP/1.1"))
            result.kind = RawOtaRequestKind::Arm;
        else if (exact(request,"POST /api/v1/bridge/ota/upload HTTP/1.1"))
            result.kind = RawOtaRequestKind::SignedTransport;
        else return false;

        Span names[kMaxHeaders]{};
        size_t nameCount = 0u;
        size_t position = lineEnd+2u;
        bool gotHost=false,gotOrigin=false,gotType=false,gotLen=false,gotAuth=false;
        bool gotToken=false,gotTransfer=false;
        uint32_t bodyLength = 0u;
        bool fetchSameOrigin = true;

        while (position < len) {
            if (!endOfLine(data,len,position,lineEnd)) return false;
            if (lineEnd == position) {
                if (position+2u != len) return false; // No body/pipelining in header preflight.
                break;
            }
            if (lineEnd-position > kMaxLineBytes || nameCount == kMaxHeaders) return false;
            const size_t colon=findColon(data,position,lineEnd);
            if (colon == position || colon == lineEnd || colon-position > kMaxNameBytes)
                return false;
            for (size_t i=position;i<colon;++i)
                if (!headerTokenChar(data[i])) return false;
            const Span name{data+position,colon-position};
            for(size_t i=0;i<nameCount;++i)
                if (sameHeader(names[i],name)) return false; // ALL duplicate header names fail closed.
            names[nameCount++]=name;

            size_t vStart=colon+1u;
            size_t vEnd=lineEnd;
            while(vStart<vEnd && (data[vStart]==' ' || data[vStart]=='\t')) ++vStart;
            while(vEnd>vStart && (data[vEnd-1u]==' ' || data[vEnd-1u]=='\t')) --vEnd;
            for(size_t i=vStart;i<vEnd;++i)
                if (static_cast<unsigned char>(data[i]) < 32u ||
                    static_cast<unsigned char>(data[i]) >= 127u)
                    return false; // Forbid obs-fold, interior TAB, controls and non-ASCII.
            const Span value{data+vStart,vEnd-vStart};
            if (sameHeader(name,Span{"host",4u})) {
                gotHost=exact(value,"192.168.4.1");
                if (!gotHost) return false;
            } else if (sameHeader(name,Span{"origin",6u})) {
                gotOrigin=exact(value,"http://192.168.4.1");
                if (!gotOrigin) return false;
            } else if (sameHeader(name,Span{"content-type",12u})) {
                gotType = result.kind==RawOtaRequestKind::Arm
                    ? exact(value,"application/json") : exact(value,"application/octet-stream");
                if (!gotType) return false;
            } else if (sameHeader(name,Span{"content-length",14u})) {
                if (!parseDecimal(value,bodyLength)) return false;
                gotLen=true;
            } else if (sameHeader(name,Span{"authorization",13u})) {
                if (value.n < 8u || value.n > kMaxDigestHeaderBytes ||
                    !hasPrefix(value,"Digest ")) return false;
                gotAuth=true; // Syntax only; verifier must bind route/nonce/replay.
                result.digestValueOffset=vStart;
                result.digestValueLength=value.n;
            } else if (sameHeader(name,Span{"x-shino-intent",14u})) {
                if (value.n!=32u) return false;
                uint8_t nonzero=0u;
                for(size_t i=0;i<32u;++i) {
                    if (!lowerHex(value.p[i])) return false;
                    nonzero |= static_cast<uint8_t>(value.p[i] != '0');
                    result.intentToken[i]=value.p[i];
                }
                if (!nonzero) return false;
                result.intentToken[32u]='\0';
                gotToken=true;
            } else if (sameHeader(name,Span{"cookie",6u})) {
                result.readCookiePresent=true; // Entirely ignored for write authority.
            } else if (sameHeader(name,Span{"sec-fetch-site",14u})) {
                fetchSameOrigin=exact(value,"same-origin");
                if (!fetchSameOrigin) return false;
            } else if (sameHeader(name,Span{"transfer-encoding",17u}) ||
                       sameHeader(name,Span{"expect",6u}) ||
                       sameHeader(name,Span{"content-encoding",16u}) ||
                       sameHeader(name,Span{"upgrade",7u}) ||
                       sameHeader(name,Span{"proxy-connection",16u}) ||
                       sameHeader(name,Span{"trailer",7u})) {
                gotTransfer=true; // Explicitly reject ambiguous framing / 100-continue.
                return false;
            }
            // All other syntactically bounded headers are advisory only.
            position=lineEnd+2u;
        }
        if (!gotHost || !gotOrigin || !gotType || !gotLen || !gotAuth ||
            gotTransfer || !fetchSameOrigin) return false;
        if (result.kind==RawOtaRequestKind::Arm) {
            if (gotToken || bodyLength<16u || bodyLength>384u) return false;
        } else {
            if (!gotToken || bodyLength<64260u || bodyLength>kMaxSignedTransportBytes)
                return false;
        }
        result.contentLength=bodyLength;
        result.digestHeaderPresent=gotAuth;
        result.intentTokenPresent=gotToken;
        return true;
    }
private:
    struct Span {const char* p;size_t n;};
    static bool endOfLine(const char* d,size_t n,size_t start,size_t& end) {
        for(size_t i=start;i+1u<n;++i)
            if (d[i]=='\r' && d[i+1u]=='\n') {end=i;return true;}
        return false;
    }
    static size_t findColon(const char* d,size_t start,size_t end) {
        for(size_t i=start;i<end;++i) if (d[i]==':') return i;
        return end;
    }
    static bool headerTokenChar(char c) {
        return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||
               (c>='0'&&c<='9')||c=='-';
    }
    static char lower(char c) {return c>='A'&&c<='Z'?static_cast<char>(c+('a'-'A')):c;}
    static bool sameHeader(Span a,Span b) {
        if (a.n!=b.n) return false;
        for(size_t i=0;i<a.n;++i) if (lower(a.p[i])!=lower(b.p[i])) return false;
        return true;
    }
    static bool exact(Span a,const char* b) {
        size_t i=0u;
        while(i<a.n && b[i] && a.p[i]==b[i]) ++i;
        return i==a.n && b[i]=='\0';
    }
    static bool hasPrefix(Span a,const char* prefix) {
        size_t i=0u;
        while(prefix[i]) {
            if (i>=a.n || a.p[i]!=prefix[i]) return false;
            ++i;
        }
        return true;
    }
    static bool lowerHex(char c) {return (c>='0'&&c<='9')||(c>='a'&&c<='f');}
    static bool parseDecimal(Span value,uint32_t& output) {
        if (value.n==0u || value.n>9u) return false;
        if (value.n>1u && value.p[0]=='0') return false;
        uint32_t parsed=0u;
        for(size_t i=0;i<value.n;++i) {
            const char c=value.p[i];
            if (c<'0'||c>'9') return false;
            const uint32_t digit=static_cast<uint32_t>(c-'0');
            if (parsed>(kMaxSignedTransportBytes-digit)/10u) return false;
            parsed=parsed*10u+digit;
        }
        output=parsed;
        return true;
    }
};

} // namespace ShinoNativeOta
