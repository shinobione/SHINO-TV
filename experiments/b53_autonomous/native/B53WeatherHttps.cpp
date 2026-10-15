// SPDX-License-Identifier: GPL-3.0-or-later
// Owner opt-in B5.3 weather transport. Public-inert graph passes empty
// coordinates and therefore NEVER performs network I/O.
// No insecure TLS, redirect following, chunked HTTP or unbounded body.
#include "B53WeatherHttps.h"
#include "B53WeatherCA.h"
#include "B53WeatherFrame.h"
#include "B53WeatherGate.h"
#include "B53Sntp.h"
#include "B52Clock.h"
#include "B53AutonomyPolicy.h"
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WiFiClientSecureBearSSL.h>
#include <ctime>
#include <cstring>
#include <cstdlib>
#include <cstdio>

namespace B53WeatherHttps {
namespace {
constexpr char HOST[]="api.open-meteo.com";
constexpr uint32_t IO_DEADLINE_MS=2500;
constexpr unsigned HEADER_MAX=1000;
char lat[13]={},lon[13]={};
char body[B53WeatherFrame::MAX_BODY+1]={};
bool configured=false,begun=false;
uint32_t nextAttempt=0;
B53Autonomy::Policy weather;
bool coordinate(const char* text,char* out,size_t cap,double limit){
    if(!text)return false;
    size_t n=0;
    for(;n<cap && text[n];++n){
        const char c=text[n];
        if(!((c>='0'&&c<='9')||c=='.'||(c=='-'&&n==0)))return false;
    }
    if(!n||n>=cap||text[n])return false;
    unsigned dots=0;
    for(size_t i=0;i<n;++i)if(text[i]=='.')++dots;
    if(dots!=1)return false;
    char* end=nullptr;
    const double number=strtod(text,&end);
    if(end==text||!end||*end||number < -limit||number > limit)return false;
    memcpy(out,text,n+1);
    return true;
}
bool line(BearSSL::WiFiClientSecure& tls,char* out,size_t cap,uint32_t until){
    size_t n=0;
    while(int32_t(until-millis())>0){
        const int c=tls.read();
        if(c>=0){
            if(c=='\n'){if(n&&out[n-1]=='\r')--n;out[n]=0;return true;}
            if((c<32&&c!='\r'&&c!='\t')||n+1>=cap)return false;
            out[n++]=char(c);
        }else if(!tls.connected()&&!tls.available())return false;
        else yield();
    }
    return false;
}
bool prefix(const char* input,const char* key){
    for(;*key;++key,++input){
        char a=*input,b=*key;
        if(!a)return false;
        if(a>='A'&&a<='Z')a=char(a+32);
        if(a!=b)return false;
    }
    return true;
}
bool fetch(uint32_t utc,B53WeatherFrame::Sample& sample){
    // Local lifetimes: BearSSL holds only borrowed pointer to anchors.
    BearSSL::X509List anchors(B53_CA);
    BearSSL::WiFiClientSecure tls;
    tls.setTrustAnchors(&anchors);
    tls.setX509Time(time_t(utc));
    tls.setSSLVersion(BR_TLS12,BR_TLS12);
    tls.setBufferSizes(512,512); // only proceed if server negotiated MFLN
    tls.setTimeout(1000);
    if(!tls.connect(HOST,443)){tls.stop();return false;}
    if(!tls.getMFLNStatus()){tls.stop();return false;}
    char request[320]={};
    const int n=snprintf(request,sizeof(request),
        "GET /v1/forecast?latitude=%s&longitude=%s&current=temperature_2m%%2Cweather_code&temperature_unit=celsius&timezone=UTC HTTP/1.1\r\n"
        "Host: api.open-meteo.com\r\nAccept: application/json\r\n"
        "Accept-Encoding: identity\r\nConnection: close\r\n\r\n",lat,lon);
    if(n<=0||size_t(n)>=sizeof(request)||tls.write(
        reinterpret_cast<const uint8_t*>(request),size_t(n))!=size_t(n)){
        tls.stop();return false;
    }
    const uint32_t until=millis()+IO_DEADLINE_MS;
    char header[120]={};
    if(!line(tls,header,sizeof(header),until)||
        strncmp(header,"HTTP/1.1 200 ",13)!=0){tls.stop();return false;}
    int length=-1;bool json=false,endHeaders=false;
    unsigned headerBytes=0;
    for(unsigned i=0;i<24;++i){
        if(!line(tls,header,sizeof(header),until)){tls.stop();return false;}
        headerBytes+=unsigned(strlen(header))+2;
        if(headerBytes>HEADER_MAX){tls.stop();return false;}
        if(!header[0]){endHeaders=true;break;}
        if(prefix(header,"transfer-encoding:")||
           prefix(header,"content-encoding:")||
           prefix(header,"location:")){tls.stop();return false;}
        if(prefix(header,"content-type:")){
            if(json||!strstr(header,"application/json")){tls.stop();return false;}
            json=true;
        }
        if(prefix(header,"content-length:")){
            if(length>=0){tls.stop();return false;}
            const char* s=strchr(header,':')+1;
            while(*s==' ')++s;
            unsigned bytes=0,digits=0;
            while(*s>='0'&&*s<='9'){
                if(++digits>4){tls.stop();return false;}
                bytes=bytes*10U+unsigned(*s++-'0');
            }
            if(!digits||(*s&&*s!=' ')||bytes>B53WeatherFrame::MAX_BODY){
                tls.stop();return false;
            }
            length=int(bytes);
        }
    }
    if(!endHeaders||!json||length<16){tls.stop();return false;}
    size_t got=0;
    while(got<size_t(length)&&int32_t(until-millis())>0){
        int ch=tls.read();
        if(ch>=0)body[got++]=char(ch);
        else if(!tls.connected()&&!tls.available())break;
        else yield();
    }
    body[got]=0;
    bool ok=got==size_t(length)&&B53WeatherFrame::parse(body,got,sample);
    tls.stop();
    return ok;
}
}
void begin(const char* latitude,const char* longitude){
    if(begun)return;
    begun=true;
    nextAttempt=millis()+30000U;
    if(!coordinate(latitude,lat,sizeof(lat),90.0)||
       !coordinate(longitude,lon,sizeof(lon),180.0)){
        lat[0]=lon[0]=0;return;
    }
    configured=true;
}
void poll(uint32_t now,bool otaBusy,bool httpBusy,bool metricsStale){
    if(!begun||!configured||int32_t(now-nextAttempt)<0)return;
    uint32_t utc=0;
    const bool synced=B53Sntp::current(now,utc);
    uint32_t heap=0,block=0;uint8_t fragmentation=0;
    ESP.getHeapStats(&heap,&block,&fragmentation);
    if(!B53WeatherGate::allowed(configured,WiFi.status()==WL_CONNECTED,
            synced,metricsStale,otaBusy,httpBusy,heap,block,
            ESP.getFreeContStack(),fragmentation))return;
    // A failed or ambiguous TLS exchange NEVER causes an immediate retry.
    nextAttempt=now+B53WeatherGate::PERIOD_MS;
    B53WeatherFrame::Sample sample{};
    if(!fetch(utc,sample))return;
    const uint32_t finished=millis();
    if(!weather.acceptWeather(sample.tenthsC,sample.code,finished,2700000U))return;
    ArtworkPilot::WeatherData view{};
    view.valid=true;view.observedMs=finished;view.validForMs=2700000U;
    view.tenthsC=sample.tenthsC;
    const char* caption=B53WeatherFrame::label(sample.code);
    if(!caption)return;
    strncpy(view.condition,caption,sizeof(view.condition)-1);
    strncpy(view.place,"Local",sizeof(view.place)-1);
    B52Clock::setWeather(view);
}
}
