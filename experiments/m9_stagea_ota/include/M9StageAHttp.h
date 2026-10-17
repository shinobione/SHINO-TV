// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// OFFLINE composition only. No listener, key, credentials or native writer here.
// Core CLIENT_IS_GIVEN releases its reference; this owner retains one client.
#include <ESP8266WebServer.h>
#include "M9SignedTransfer.h"

namespace M9StageA {
template<class Hash,class DigestHash,class Adapter,class Policy> class Http final {
public:
    using Gate=ShinoNativeOta::StrictOtaDigestGate<DigestHash>;
    Http(const M9Signed::Release& release,uint32_t current,Adapter& adapter,Policy& policy)
        : transfer_(release,current,adapter),policy_(policy) {}
    Http(const Http&)=delete;Http& operator=(const Http&)=delete;
    Gate armHeaderAuth,armAuth,uploadAuth; // Same one-use arm challenge, checked before AND after bounded consent.
    ESP8266WebServer::ClientFuture claim(const String& line,WiFiClient* client,uint32_t requestStarted) {
        // Called after the real bounded request-line reader, BEFORE Core headers/body.
        if(line.indexOf(" /api/v1/bridge/ota/")<0)
            return ESP8266WebServer::CLIENT_REQUEST_CAN_CONTINUE;
        const bool arm=line=="POST /api/v1/bridge/ota/arm HTTP/1.1";
        const bool upload=line=="POST /api/v1/bridge/ota/upload HTTP/1.1";
        if(!client || (!arm&&!upload) || busy_ || finished_ ||
           !policy_.privateAp(*client) || policy_.peer(*client)<0xc0a80402 ||
           policy_.peer(*client)>0xc0a804fe || !policy_.ownerConfirmed()) {
            fail();return ESP8266WebServer::CLIENT_MUST_STOP;
        }
        client_=*client; // Refcounted copy, not another listener or accept path.
        peer_=policy_.peer(client_);started_=requestStarted;used_=line.length()+2;
        if(used_>=sizeof(scratch_.headers)){fail();return ESP8266WebServer::CLIENT_MUST_STOP;}
        memcpy(scratch_.headers,line.c_str(),line.length());
        scratch_.headers[line.length()]='\r';scratch_.headers[line.length()+1]='\n';
        busy_=true;state_=Headers;isArm_=arm;return ESP8266WebServer::CLIENT_IS_GIVEN;
    }
    void pump() {
        if(!busy_)return;
        const auto now=policy_.now();
        if(uint32_t(now-started_)>=60000 || !policy_.ownerConfirmed() ||
           !policy_.privateAp(client_) || policy_.peer(client_)!=peer_ ||
           !policy_.budget().safe()) {fail();return;}
        // Bounded work: at most512 incoming bytes per cooperative invocation.
        if(state_==Headers) {
            if(uint32_t(now-started_)>=2000){fail();return;}
            unsigned work=0;
            while(client_.available() && work++<512) {
                int c=client_.read();
                if(c<0 || used_==sizeof(scratch_.headers)){fail();return;}
                scratch_.headers[used_++]=char(c);
                if(used_>=4 && !memcmp(scratch_.headers+used_-4,"\r\n\r\n",4)) {
                    if(!M9Signed::HeaderGate::inspect(scratch_.headers,used_,parsed_)) {fail();return;}
                    if(isArm_) {
                        if(parsed_.contentLength!=16 || transfer_.phase()!=M9Signed::Phase::Idle){fail();return;}
                        if(!armHeaderAuth.verify(peer_,parsed_.kind,scratch_.headers+parsed_.digestValueOffset,
                            parsed_.digestValueLength,policy_.user(),policy_.ha1(),now)){fail();return;}
                        state_=Consent;
                    } else {
                        // Every release/consent/auth/geometry/budget gate precedes begin.
                        if(!transfer_.begin(scratch_.headers,used_,peer_,true,uploadAuth,
                            policy_.user(),policy_.ha1(),now,policy_.budget())){fail();return;}
                        state_=Stream; // Header/chunk union may now be reused.
                    }
                    return;
                }
            }
        } else if(state_==Consent) {
            if(client_.available()>int(16-consentBytes_)){fail();return;}
            while(client_.available() && consentBytes_<16)consent_[consentBytes_++]=uint8_t(client_.read());
            if(consentBytes_==16) {
                if(!transfer_.arm(scratch_.headers,used_,consent_,16,peer_,true,
                    policy_.ownerConfirmed(),policy_.token(),armAuth,policy_.user(),policy_.ha1(),now,policy_.budget())){fail();return;}
                respond(true);return; // No staging allocation/write for arm.
            }
        } else {
            const uint32_t remaining=parsed_.contentLength-transfer_.received();
            if(client_.available()>int(remaining)){fail();return;}
            const size_t count=std::min(size_t(client_.available()),std::min(size_t(remaining),M9Signed::Chunk));
            if(count) {
                for(size_t i=0;i<count;++i){int c=client_.read();if(c<0){fail();return;}scratch_.chunk[i]=uint8_t(c);}
                if(!transfer_.add(scratch_.chunk,count,transfer_.received(),now,policy_.budget())){fail();return;}
                ++chunks;
            }
            if(transfer_.phase()==M9Signed::Phase::Complete) {
                if(client_.available() || !transfer_.finish(now,policy_.budget())){fail();return;}
                finished_=true;respond(true);return;
            }
        }
        if(!client_.connected() && !client_.available())fail();
    }
    void cancel(){fail();}
    bool busy()const{return busy_;}
    M9Signed::Phase phase()const{return transfer_.phase();}
    uint32_t received()const{return transfer_.received();}
    unsigned chunks=0,rejects=0;
private:
    enum State:uint8_t{Headers,Consent,Stream};
    void respond(bool ok) {
        // Constant bounded response; no response String or body-sized buffer.
        const char* response=ok?"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 2\r\n\r\n{}":
            "HTTP/1.1 400 Bad Request\r\nConnection: close\r\nContent-Length: 2\r\n\r\n{}";
        const size_t size=strlen(response);
        const auto sent=client_.write(reinterpret_cast<const uint8_t*>(response),size);
        client_.stop();client_=WiFiClient();busy_=false;
        if(sent!=size && transfer_.phase()!=M9Signed::Phase::Scheduled)transfer_.disconnect();
    }
    void fail(){++rejects;transfer_.disconnect();finished_=true;if(busy_)respond(false);}
    M9Signed::Transfer<Hash,DigestHash,Adapter> transfer_;Policy& policy_;
    WiFiClient client_;
    // Narrow reduction: headers and512B chunk cannot overlap in time.
    union Scratch {char headers[2048];uint8_t chunk[512];Scratch(){}} scratch_;
    ShinoNativeOta::RawOtaHeaderResult parsed_;
    uint32_t peer_=0,started_=0;size_t used_=0,consentBytes_=0;
    uint8_t consent_[16]{};State state_=Headers;bool busy_=false,isArm_=false,finished_=false;
};
}
