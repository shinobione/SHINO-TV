// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <ESP8266WiFi.h>
#include "ShinoWifiUpdate.h"
namespace ShinoInstall {
class Native {
public:
    Native(const char* device,const char* build,const uint8_t* key):device_(device),build_(build),key_(key),listener_(8266){}
    bool begin(){if(!privateAp())return false;listener_.begin();return true;}
    bool busy()const{return receiver_ && receiver_->receiving();}
    void pump(){
        if(done_)return;
        if(!privateAp()){fail();return;}
        if(!client_){client_=listener_.accept();if(!client_)return;started_=last_=millis();}
        auto extra=listener_.accept();if(extra)extra.stop(); // Never replace active owner.
        if(!client_.connected() || uint32_t(millis()-started_)>=60000 || uint32_t(millis()-last_)>=3000){fail();return;}
        if(receiver_ && receiver_->receiving() && receiver_->received()<expected_){
            size_t count=std::min(size_t(512),std::min(size_t(client_.available()),size_t(expected_-receiver_->received())));
            if(receiver_->received()==0 && count<4)count=0;
            if(count){int n=client_.read(reinterpret_cast<uint8_t*>(buffer_),count);
                if(n<=0 || !receiver_->add(reinterpret_cast<uint8_t*>(buffer_),n,millis(),budget())){fail();return;}
                client_.printf("ACK %u\n",receiver_->received());last_=millis();}
        }else{
            for(unsigned step=0;step<512 && client_.available();++step){int c=client_.read();
                if(c=='\n'){buffer_[used_]=0;line();used_=0;last_=millis();break;}
                if(c<32 || c>126 || used_>=sizeof(buffer_)-1){fail();return;}buffer_[used_++]=char(c);}
        }
        ESP.wdtFeed();yield();
    }
private:
    const char *device_,*build_;const uint8_t* key_;WiFiServer listener_;WiFiClient client_;
    alignas(Receiver) uint8_t storage_[sizeof(Receiver)];Receiver* receiver_=nullptr;
    char buffer_[512]{};uint16_t used_=0;uint32_t started_=0,last_=0,expected_=0;bool done_=false;
    bool privateAp()const{return WiFi.getMode()==WIFI_AP && WiFi.softAPIP()==IPAddress(192,168,4,1);}
    bool localPeer(){auto p=client_.remoteIP();return client_.localIP()==WiFi.softAPIP() && p[0]==192&&p[1]==168&&p[2]==4&&p[3]>1&&p[3]<255;}
    uint32_t peer(){auto p=client_.remoteIP();return uint32_t(p[0])<<24|uint32_t(p[1])<<16|uint32_t(p[2])<<8|p[3];}
    Budget budget(){uint32_t heap,block;uint8_t frag;ESP.getHeapStats(&heap,&block,&frag);return {heap,block,ESP.getFreeContStack(),frag};}
    void fail(){if(receiver_){receiver_->abort();receiver_->~Receiver();receiver_=nullptr;}client_.stop();used_=0;expected_=0;}
    void line(){
        if(!localPeer()){fail();return;}
        if(!receiver_){
            char dev[17],cn[33],tail;int n=0;
            if(std::sscanf(buffer_,"CAP %16s %32s%n%c",dev,cn,&n,&tail)!=2 || size_t(n)!=std::strlen(buffer_) || std::strcmp(dev,device_)){fail();return;}
            uint8_t random[16];for(unsigned i=0;i<4;++i){uint32_t r=os_random();std::memcpy(random+4*i,&r,4);}char nonce[33];encode(random,16,nonce);
            receiver_=new(storage_) Receiver(device_,build_,key_);
            if(!receiver_->capability(cn,nonce,peer(),privateAp(),millis(),buffer_,sizeof(buffer_))){fail();return;}client_.print(buffer_);return;
        }
        if(receiver_->receiving()){
            if(std::strcmp(buffer_,"COMMIT") || client_.available() || !receiver_->commit(millis(),budget())){fail();return;}
            client_.printf("STAGED %s\n",receiver_->nextBuild());client_.flush(1000);client_.stop();listener_.stop();done_=true;
            // Research proof is unreachable. Future explicit installer consent
            // encompasses this reboot; an ACK alone never means boot success.
            ESP.restart();return;
        }
        unsigned cmd,size;char sha[65],build[65],proof[65],tail;int n=0;
        if(std::sscanf(buffer_,"AUTH %u %u %64s %64s %64s%n%c",&cmd,&size,sha,build,proof,&n,&tail)!=5 || size_t(n)!=std::strlen(buffer_) ||
            !receiver_->authorize(cmd,size,sha,build,proof,peer(),privateAp(),millis(),budget(),ESP.getSketchSize())){fail();return;}
        expected_=size;client_.print("READY\n");
    }
};
}
