// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// M3-N: bounded, source-profiled HTTP Digest authorization research.
// No socket, WiFi state, routes, keys, clock source, listener or flash writer.
// DIGEST MD5 exists ONLY to preserve the B5.3 browser/telemetry path.
// The NEW display-control route MUST use M3-C HMAC-SHA256, never this class.
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdio>

namespace ShinoM3N {
inline void wipe(void* b,size_t n) {
    volatile uint8_t* p=static_cast<volatile uint8_t*>(b);
    while(n--) *p++=0u;
}
inline bool eq(const char* s,size_t n,const char* literal) {
    return s && std::strlen(literal)==n && std::memcmp(s,literal,n)==0;
}
struct Slice { const char* start=nullptr; size_t bytes=0u; };
inline bool eq(Slice s,const char* literal) {
    return eq(s.start,s.bytes,literal);
}
inline bool matchBytes(Slice s,const char* p,size_t n) {
    if(!s.start||!p||s.bytes!=n) return false;
    uint8_t diff=0u;
    for(size_t i=0;i<n;++i) diff|=static_cast<uint8_t>(s.start[i]^p[i]);
    return diff==0u;
}
inline bool parseHex(Slice s,uint32_t& out) {
    if(!s.start||s.bytes!=8u)return false;
    uint32_t value=0;
    for(size_t i=0;i<8u;++i) {
        const char c=s.start[i];
        if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
        value=(value<<4u) | static_cast<uint32_t>(
            c>='0'&&c<='9'?c-'0':c-'a'+10);
    }
    out=value;
    return value!=0u;
}
struct Fields {
    Slice username,realm,nonce,uri,response,opaque,qop,nc,cnonce,algorithm;
};
// Strict bounded parser. Unknown, repeated, control and escaped fields all
// reject; no String, strdup, heap or cross-request authentication state.
// Accepts standard quoted fields and unquoted qop/nc/algorithm.
inline bool parse(const char* raw,size_t n,Fields& parsed) {
    if(!raw||n<=7u||n>768u||std::memcmp(raw,"Digest ",7u)!=0)
        return false;
    Fields next{};
    uint16_t seen=0u;
    size_t at=7u;
    constexpr const char* names[]={
        "username","realm","nonce","uri","response","opaque",
        "qop","nc","cnonce","algorithm"
    };
    Slice* fields[]={
        &next.username,&next.realm,&next.nonce,&next.uri,
        &next.response,&next.opaque,&next.qop,&next.nc,
        &next.cnonce,&next.algorithm
    };
    while(at<n) {
        while(at<n&&raw[at]==' ')++at;
        const size_t begin=at;
        while(at<n&&((raw[at]>='a'&&raw[at]<='z')||raw[at]=='-'))++at;
        if(begin==at||at>=n||raw[at]!='=')return false;
        const Slice key{raw+begin,at-begin};
        int slot=-1;
        for(size_t i=0;i<10u;++i)if(eq(key,names[i])){slot=static_cast<int>(i);break;}
        if(slot<0||(seen&(1u<<slot)))return false;
        seen=static_cast<uint16_t>(seen|(1u<<slot));
        ++at;
        bool quoted=false;
        if(at<n&&raw[at]=='"') {quoted=true;++at;}
        const size_t valueStart=at;
        if(quoted) {
            while(at<n&&raw[at]!='"') {
                const uint8_t c=static_cast<uint8_t>(raw[at]);
                if(c<33u||c>126u||c=='\\')return false;
                ++at;
            }
            if(at>=n||at==valueStart)return false;
            *fields[slot]={raw+valueStart,at-valueStart};
            ++at;
        } else {
            while(at<n&&raw[at]!=','&&raw[at]!=' ') {
                const uint8_t c=static_cast<uint8_t>(raw[at]);
                if(c<33u||c>126u||c=='"'||c=='\\')return false;
                ++at;
            }
            if(at==valueStart)return false;
            *fields[slot]={raw+valueStart,at-valueStart};
        }
        while(at<n&&raw[at]==' ')++at;
        if(at==n)break;
        if(raw[at]!=',')return false;
        ++at;
        if(at==n)return false;
    }
    constexpr uint16_t allNine=(1u<<9u)-1u;
    if((seen&allNine)!=allNine)return false;
    if((seen&(1u<<9u)) && !eq(next.algorithm,"MD5"))return false;
    parsed=next;
    return true;
}
inline void toHex(const uint8_t* src,size_t n,char* out) {
    constexpr char alphabet[]="0123456789abcdef";
    for(size_t i=0;i<n;++i) {out[2u*i]=alphabet[src[i]>>4u];out[2u*i+1u]=alphabet[src[i]&15u];}
    out[2u*n]='\0';
}
inline bool lowerHex(Slice s,size_t n) {
    if(!s.start||s.bytes!=n)return false;
    for(size_t i=0;i<n;++i) {
        const char v=s.start[i];
        if(!((v>='0'&&v<='9')||(v>='a'&&v<='f')))return false;
    }
    return true;
}
inline bool validCnonce(Slice s) {
    if(!s.start||s.bytes<8u||s.bytes>64u)return false;
    for(size_t i=0;i<s.bytes;++i) {
        const char v=s.start[i];
        if(!((v>='A'&&v<='Z')||(v>='a'&&v<='z')||
             (v>='0'&&v<='9')||v=='-'||v=='_'||v=='+'||v=='/'||v=='='))
            return false;
    }
    return true;
}
enum class Verb : uint8_t { Get, Post };
struct Peer {
    uint32_t remote=0, local=0; // verified from WiFiClient, never HTTP fields
};
template<class MD5> inline bool digestResponse(
    const char* user,const char* password,const char* method,
    Slice uri,Slice nonce,Slice nc,Slice cnonce,char out[33]) {
    if(!user||!password||!method||!uri.start||!nonce.start||
       !nc.start||!cnonce.start)return false;
    constexpr char realm[]="SHINO-FirstBoot";
    uint8_t digest[16]{};
    char h1[33]{},h2[33]{};
    MD5 md5;
    const auto update=[&](const char* p,size_t bytes)->void{md5.add(p,bytes);};
    md5.reset();
    update(user,std::strlen(user));update(":",1u);
    update(realm,sizeof(realm)-1u);update(":",1u);
    update(password,std::strlen(password));md5.finish(digest);
    toHex(digest,16u,h1);
    md5.reset();
    update(method,std::strlen(method));update(":",1u);
    update(uri.start,uri.bytes);md5.finish(digest);
    toHex(digest,16u,h2);
    md5.reset();
    update(h1,32u);update(":",1u);update(nonce.start,nonce.bytes);
    update(":",1u);update(nc.start,nc.bytes);update(":",1u);
    update(cnonce.start,cnonce.bytes);update(":auth:",6u);
    update(h2,32u);md5.finish(digest);
    toHex(digest,16u,out);
    wipe(digest,sizeof(digest));wipe(h1,sizeof(h1));wipe(h2,sizeof(h2));
    return true;
}
// This gate has no true network authority: the *caller* must still check
// AP/STA local IP, subnet and Origin against HomeLan source policy.
class DigestState final {
    char nonce_[33]{},opaque_[33]{};
    Peer peer_{};
    uint32_t issuedMs_=0u,lastNc_=0u;
    bool active_=false;
public:
    static constexpr uint32_t kNonceMs=30000u;
    DigestState()=default;
    DigestState(const DigestState&)=delete;
    DigestState& operator=(const DigestState&)=delete;
    ~DigestState(){invalidate();}
    void invalidate() {
        wipe(nonce_,sizeof(nonce_));wipe(opaque_,sizeof(opaque_));
        peer_={};issuedMs_=lastNc_=0u;active_=false;
    }
    bool issue(const uint8_t entropy[32],Peer peer,uint32_t now) {
        invalidate();
        if(!entropy||!peer.remote||!peer.local)return false;
        // Challenge material must be supplied by an authenticated hardware
        // RNG call at the *native transport owner*, not a deterministic PRNG.
        bool nonzero=false;
        for(size_t i=0;i<32u;++i)nonzero|=entropy[i]!=0u;
        if(!nonzero)return false;
        toHex(entropy,16u,nonce_);toHex(entropy+16u,16u,opaque_);
        peer_=peer;issuedMs_=now;active_=true;return true;
    }
    const char* nonce()const{return active_?nonce_:"";}
    const char* opaque()const{return active_?opaque_:"";}
    template<class MD5>
    bool verify(const char* raw,size_t n,const char* method,
                const char* route,const char* user,const char* password,
                Peer peer,uint32_t now) {
        if(!active_||!method||!route||!user||!password||
           (std::strcmp(method,"GET")!=0&&std::strcmp(method,"POST")!=0)||
           static_cast<uint32_t>(now-issuedMs_)>=kNonceMs||
           peer.remote!=peer_.remote||peer.local!=peer_.local)
            return false;
        Fields f;
        if(!parse(raw,n,f)||!eq(f.username,user)||
           !eq(f.realm,"SHINO-FirstBoot")||
           !matchBytes(f.nonce,nonce_,32u)||!matchBytes(f.opaque,opaque_,32u)||
           !eq(f.qop,"auth")||!matchBytes(f.uri,route,std::strlen(route))||
           !lowerHex(f.response,32u)||!validCnonce(f.cnonce))return false;
        uint32_t nc=0;
        if(!parseHex(f.nc,nc)||nc<=lastNc_)return false;
        char expected[33]{};
        const bool built=digestResponse<MD5>(
            user,password,method,f.uri,f.nonce,f.nc,f.cnonce,expected);
        const bool accepted=built&&matchBytes(f.response,expected,32u);
        wipe(expected,sizeof(expected));
        if(accepted)lastNc_=nc; // replay floor only advances on actual proof
        return accepted;
    }
};
class BrowserReadSessions final {
    static constexpr uint32_t kTtlMs=7200000u;
    struct Slot {
        char token[33]{};
        Peer peer{};
        uint32_t issued=0;
        bool active=false;
    } slots_[2]{};
public:
    ~BrowserReadSessions(){invalidate();}
    void invalidate(){
        for(auto& s:slots_){wipe(s.token,sizeof(s.token));s.peer={};s.issued=0;s.active=false;}
    }
    bool issue(const uint8_t entropy[16],Peer p,uint32_t now,char out[33]){
        if(!entropy||!p.remote||!p.local||!out)return false;
        bool nonzero=false;
        for(size_t i=0;i<16u;++i)nonzero|=entropy[i]!=0;
        if(!nonzero)return false;
        size_t index=0u;
        if(slots_[0].active && (!slots_[1].active ||
            static_cast<uint32_t>(now-slots_[1].issued)>static_cast<uint32_t>(now-slots_[0].issued)))
            index=1u;
        auto& s=slots_[index];
        wipe(s.token,sizeof(s.token));
        toHex(entropy,16u,s.token);
        s.peer=p;s.issued=now;s.active=true;
        std::memcpy(out,s.token,33u);
        return true;
    }
    bool allowsGetOnly(const char* cookie,size_t bytes,Peer p,uint32_t now)const{
        constexpr char marker[]="SHINO_READ_SESSION=";
        if(!cookie||bytes<sizeof(marker)-1u+32u||bytes>256u||
           !p.remote||!p.local)return false;
        Slice found{};size_t hits=0u;
        size_t at=0u;
        while(at<bytes){
            size_t end=at;
            while(end<bytes && cookie[end]!=';')++end;
            while(at<end && cookie[at]==' ')++at;
            while(end>at && cookie[end-1u]==' ')--end;
            const size_t len=end-at;
            if(len>=sizeof(marker)-1u &&
               std::memcmp(cookie+at,marker,sizeof(marker)-1u)==0){
                ++hits;
                found={cookie+at+sizeof(marker)-1u,len-(sizeof(marker)-1u)};
            }
            at=end<bytes?end+1u:bytes;
        }
        if(hits!=1u||!lowerHex(found,32u))return false;
        for(const auto& s:slots_){
            if(s.active && s.peer.remote==p.remote && s.peer.local==p.local &&
               static_cast<uint32_t>(now-s.issued)<kTtlMs &&
               matchBytes(found,s.token,32u))return true;
        }
        return false;
    }
};
} // namespace ShinoM3N
