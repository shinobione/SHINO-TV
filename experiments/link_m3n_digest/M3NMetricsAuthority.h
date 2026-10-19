// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Concrete M3-M auth adapter: source-uses HomeLan peer & Origin policy,
// actual Digest MD5 kernel and read-only browser session state.
// STILL NOT THE NATIVE LISTENER. NetworkContext MUST originate from the
// accepted WiFiClient / current radio, never from HTTP request fields.
#include "M3NLegacyDigest.h"
#include "../link_m3m_native/M3MActualMetricsHandler.h"
#include "boot/HomeLanPolicy.h"
#include <cstring>
namespace ShinoM3N {
struct NetworkContext {
    Peer peer{};
    uint32_t subnet=0u;
    bool apActive=false;
    bool onApInterface=false;
    bool staOnline=false;
    bool onStaInterface=false;
    const char* localIp=nullptr;
    const char* host=nullptr;
    const char* origin=nullptr;
};
inline bool permittedPeer(const NetworkContext& ctx,const char* route) {
    if(!route||!ctx.localIp||!ctx.host||!ctx.origin ||
       !ctx.peer.local||!ctx.peer.remote)return false;
    // Reuse actual, pinned HomeLan policy (not a copied IP check).
    const bool ap=ctx.onApInterface && ctx.apActive;
    const bool sta=ctx.onStaInterface && ctx.staOnline;
    if(ap==sta)return false; // unknown or conflicting interface
    const uint32_t mask=ap?0xffffff00u:ctx.subnet;
    if(!HomeLan::peerOnSubnet(ctx.peer.remote,ctx.peer.local,mask)||
       !HomeLan::authority(ctx.host,ctx.origin,ctx.localIp))
        return false;
    return HomeLan::endpoint(ap,route);
}
template<class MD5>
class MetricsAuthority final {
    const NetworkContext& ctx_;
    DigestState& digest_;
    const BrowserReadSessions& browser_;
    const char* rawAuth_;
    size_t rawAuthBytes_;
    const char* rawCookie_;
    size_t rawCookieBytes_;
    const char* username_;
    const char* password_;
    uint32_t timeMs_;
public:
    MetricsAuthority(const NetworkContext& ctx,DigestState& digest,
                     const BrowserReadSessions& browser,
                     const char* rawAuth,size_t authLen,
                     const char* rawCookie,size_t cookieLen,
                     const char* username,const char* password,
                     uint32_t now):
       ctx_(ctx),digest_(digest),browser_(browser),
       rawAuth_(rawAuth),rawAuthBytes_(authLen),
       rawCookie_(rawCookie),rawCookieBytes_(cookieLen),
       username_(username),password_(password),timeMs_(now) {}
    bool permit(ShinoM3M::Verb method,ShinoM3M::Network network,
                const char* path)const {
        if(!path||std::strcmp(path,"/api/v1/bridge/metrics")!=0||
           !permittedPeer(ctx_,path))return false;
        const bool ap=ctx_.onApInterface&&ctx_.apActive;
        if((network==ShinoM3M::Network::ProtectedAp)!=ap)return false;
        if(method==ShinoM3M::Verb::Get &&
           browser_.allowsGetOnly(rawCookie_,rawCookieBytes_,
                                  ctx_.peer,timeMs_))return true;
        // No cookie, Basic, HTTP query string or unauthenticated read
        // can authorize POST. Credentials are only examined inside MD5
        // and never rendered to a response.
        return digest_.verify<MD5>(rawAuth_,rawAuthBytes_,
            method==ShinoM3M::Verb::Get?"GET":"POST",
            path,username_,password_,ctx_.peer,timeMs_);
    }
};
} // namespace ShinoM3N
