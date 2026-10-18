// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// HOST prototype only: no sockets, Arduino, authentication, OTA or storage.
#include "B53WeatherFrame.h"
#include "B53WeatherChunked.h"
#include <stdio.h>
#include <string.h>

namespace B53WeatherDirect {
constexpr uint32_t TOTAL_MS=2000, DNS_MS=400, CONNECT_MS=400, WRITE_MS=300;
constexpr uint32_t HEAD_MS=600, BODY_MS=600, MAX_AGE=2700, FUTURE_S=60;
constexpr uint32_t PERIOD_MS=1800000, RETRY_MS=60000;
constexpr size_t WIRE_MAX=6144, HEAD_MAX=1024;
enum class Io { Pending, Done, Failed };
// Future native driver MUST return promptly, including DNS/connect/write/read.
// A post-call check rejects overruns but cannot preempt a blocking driver.
struct Transport {
    virtual ~Transport()=default;
    virtual uint32_t nowMs() const=0;
    virtual Io resolve(const char* host)=0;
    virtual Io connect(unsigned port)=0;
    // Submitted bytes must be consumed/copied before return, never retained.
    virtual Io write(const char* bytes,size_t size,size_t& sent)=0;
    virtual Io read(uint8_t* bytes,size_t cap,size_t& got)=0;
    virtual void close()=0; // prompt, releases only this weather connection
};
struct Conditions {
    bool sta=false,utcValid=false,ota=false,digest=false,linkPending=false,linkFresh=false;
    uint32_t utc=0;
};
enum class Result { None, Busy, Success, Network, Timeout, Malformed, Stale };
class Client {
    enum class Phase { Idle, Dns, Connect, Write, Headers, Body };
    Phase phase_=Phase::Idle;
    char latitude_[13]={},longitude_[13]={};
    // Request (DNS/write), header line and decoded body never overlap in time.
    // RX callbacks own the adapter's separate ring and never borrow these bytes.
    static constexpr size_t REQUEST_CAP=320,LINE_CAP=128;
    char work_[B53WeatherFrame::MAX_BODY+1]={};
    B53WeatherChunked::Decoder chunks_{work_,B53WeatherFrame::MAX_BODY};
    B53WeatherFrame::TimedSample last_{};
    size_t requestSize_=0,sent_=0,lineSize_=0,headBytes_=0,wireBytes_=0,bodySize_=0;
    uint32_t start_=0,phaseStart_=0,lastAttempt_=0,wait_=0,accepted_=0,lease_=0;
    int length_=-1;
    unsigned lines_=0;
    bool configured_=false,attempted_=false,chunked_=false,json_=false,cr_=false,valid_=false;
    Result result_=Result::None;
    static bool coordinate(const char* in,char* out,unsigned limit){
        if(!in)return false;
        size_t n=0;while(n<13 && in[n])++n;
        if(!n||n>=13)return false;
        size_t i=in[0]=='-'?1:0;unsigned whole=0,digits=0,frac=0;
        for(;i<n && in[i]>='0' && in[i]<='9';++i){
            if(++digits>3)return false;
            whole=whole*10U+unsigned(in[i]-'0');
        }
        if(!digits||whole>limit)return false;
        if(i<n){
            if(in[i++]!='.'||i==n)return false;
            for(;i<n;++i){
                if(in[i]<'0'||in[i]>'9'||++frac>7||(whole==limit && in[i]!='0'))return false;
            }
        }
        memcpy(out,in,n+1);return true;
    }
    static bool eligible(const Conditions& c){
        return c.sta&&c.utcValid&&c.utc>=1577836800U&&c.utc<=4102444799U &&
            !c.ota&&!c.digest&&!c.linkPending&&!c.linkFresh;
    }
    uint32_t budget() const {
        switch(phase_){
        case Phase::Dns:return DNS_MS;case Phase::Connect:return CONNECT_MS;
        case Phase::Write:return WRITE_MS;case Phase::Headers:return HEAD_MS;
        default:return BODY_MS;
        }
    }
    bool late(uint32_t now) const {
        return uint32_t(now-start_)>=TOTAL_MS || uint32_t(now-phaseStart_)>=budget();
    }
    void enter(Phase next,uint32_t now){phase_=next;phaseStart_=now;}
    void stop(Transport& t,Result r){
        t.close();phase_=Phase::Idle;result_=r;
        wait_=r==Result::Success?PERIOD_MS:RETRY_MS;
    }
    bool append(const char* source,bool flash){
        for(size_t i=0;;++i){
            const char c=flash?B53WeatherFrame::Text::read(source+i):source[i];
            if(!c){work_[requestSize_]=0;return true;}
            if(requestSize_+1>=REQUEST_CAP)return false;
            work_[requestSize_++]=c;
        }
    }
    bool request(){
        requestSize_=0;
        // Bounded copies, no variadic formatter, temporary format or heap.
        return append(B53_WEATHER_TEXT("GET /v1/forecast?latitude="),true)&&append(latitude_,false)&&
            append(B53_WEATHER_TEXT("&longitude="),true)&&append(longitude_,false)&&
            append(B53_WEATHER_TEXT("&current=temperature_2m%2Cweather_code&temperature_unit=celsius&timezone=UTC HTTP/1.1\r\n"
              "Host: api.open-meteo.com\r\nAccept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n"),true);
    }
    bool header(){
        work_[lineSize_]=0;
        if(++lines_>24)return false;
        using B53WeatherFrame::Text::equals;
        if(lines_==1)return equals(work_,B53_WEATHER_TEXT("HTTP/1.1 200 OK"));
        if(!lineSize_){
            if(!json_||(!chunked_ && length_<16))return false;
            return true;
        }
        char* colon=strchr(work_,':');if(!colon||colon==work_)return false;
        for(char* s=work_;s<colon;++s){
            if(*s>='A'&&*s<='Z')*s=char(*s+32);
            if(!((*s>='a'&&*s<='z')||*s=='-'))return false;
        }
        *colon=0;char* value=colon+1;
        while(*value==' '||*value=='\t')++value;
        size_t n=strlen(value);while(n&&(value[n-1]==' '||value[n-1]=='\t'))value[--n]=0;
        if(equals(work_,B53_WEATHER_TEXT("location"))||equals(work_,B53_WEATHER_TEXT("content-encoding"))||equals(work_,B53_WEATHER_TEXT("trailer")))return false;
        if(equals(work_,B53_WEATHER_TEXT("content-type"))){
            if(json_ || (!equals(value,B53_WEATHER_TEXT("application/json")) && !equals(value,B53_WEATHER_TEXT("application/json; charset=utf-8"))))return false;
            json_=true;
        }else if(equals(work_,B53_WEATHER_TEXT("transfer-encoding"))){
            if(chunked_||length_>=0||!equals(value,B53_WEATHER_TEXT("chunked")))return false;
            chunked_=true;
        }else if(equals(work_,B53_WEATHER_TEXT("content-length"))){
            if(length_>=0||chunked_||!n||n>3)return false;
            unsigned size=0;
            for(size_t i=0;i<n;++i){if(value[i]<'0'||value[i]>'9')return false;size=size*10U+unsigned(value[i]-'0');}
            if(size>B53WeatherFrame::MAX_BODY)return false;
            length_=int(size);
        }
        return true;
    }
    bool consume(uint8_t ch,uint32_t now,bool& done){
        if(++wireBytes_>WIRE_MAX)return false;
        if(phase_==Phase::Headers){
            if(++headBytes_>HEAD_MAX)return false;
            if(cr_){
                if(ch!='\n')return false;
                cr_=false;const bool empty=lineSize_==0;
                if(!header())return false;
                lineSize_=0;
                if(empty){chunks_.reset();work_[0]=0;enter(Phase::Body,now);}
            }else if(ch=='\r')cr_=true;
            else {
                if(ch<32||ch>126||lineSize_+1>=LINE_CAP)return false;
                work_[lineSize_++]=char(ch);
            }
        }else if(phase_==Phase::Body){
            if(chunked_){
                if(!chunks_.consume(ch))return false;
                bodySize_=chunks_.size();done=chunks_.complete();
            }else {
                if(bodySize_>=size_t(length_)||bodySize_>=B53WeatherFrame::MAX_BODY)return false;
                work_[bodySize_++]=char(ch);work_[bodySize_]=0;
                done=bodySize_==size_t(length_);
            }
        }else return false;
        return true;
    }
    bool fresh(uint32_t now,const Conditions& c) const {
        return valid_&&c.utcValid&&uint32_t(now-accepted_)<lease_ &&
            (last_.utc>c.utc?last_.utc-c.utc<=FUTURE_S:c.utc-last_.utc<MAX_AGE);
    }
public:
    Client()=default;
    Client(const Client&)=delete;
    Client& operator=(const Client&)=delete; // Decoder's workspace pointer must stay stable.
    bool configure(const char* latitude,const char* longitude){
        if(phase_!=Phase::Idle)return false;
        configured_=false;valid_=false;last_={}; // Never retain another location's weather.
        if(!coordinate(latitude,latitude_,90)||!coordinate(longitude,longitude_,180))return false;
        if(!request())return false;
        configured_=true;valid_=false;attempted_=false;return true;
    }
    bool active() const{return phase_!=Phase::Idle;}
    Result result() const{return result_;}
    void step(Transport& t,const Conditions& c){
        const uint32_t now=t.nowMs();
        if(valid_&&!fresh(now,c))valid_=false; // expiry never revives on clock rollback
        if(!eligible(c)){
            if(active())stop(t,Result::Busy);
            return;
        }
        if(!active()){
            if(!configured_||(attempted_&&uint32_t(now-lastAttempt_)<wait_))return;
            if(!request()){result_=Result::Malformed;return;}
            attempted_=true;lastAttempt_=start_=phaseStart_=now;phase_=Phase::Dns;
            sent_=lineSize_=headBytes_=wireBytes_=bodySize_=0;length_=-1;lines_=0;
            chunked_=json_=cr_=false;chunks_.reset();result_=Result::None;
        }
        if(late(now)){stop(t,Result::Timeout);return;}
        Io io=Io::Pending;
        if(phase_==Phase::Dns)io=t.resolve("api.open-meteo.com");
        else if(phase_==Phase::Connect)io=t.connect(80);
        else if(phase_==Phase::Write){
            size_t sent=0;io=t.write(work_+sent_,requestSize_-sent_,sent);
            if(sent>requestSize_-sent_){stop(t,Result::Malformed);return;}
            sent_+=sent;
        }else {
            uint8_t bytes[64];size_t got=0;io=t.read(bytes,sizeof bytes,got);
            const uint32_t after=t.nowMs();
            if(late(after)){stop(t,Result::Timeout);return;}
            if(got>sizeof bytes){stop(t,Result::Malformed);return;}
            bool done=false;
            for(size_t i=0;i<got;++i){
                if(done||!consume(bytes[i],after,done)){stop(t,Result::Malformed);return;}
            }
            if(done){
                B53WeatherFrame::TimedSample sample{};
                if(!B53WeatherFrame::parseTimed(work_,bodySize_,sample)){stop(t,Result::Malformed);return;}
                const uint32_t utc=c.utc+uint32_t(after-now)/1000U;
                const uint32_t age=sample.utc>utc?0:utc-sample.utc;
                if((sample.utc>utc && sample.utc-utc>FUTURE_S)||age>=MAX_AGE){stop(t,Result::Stale);return;}
                last_=sample;accepted_=after;lease_=(MAX_AGE-age)*1000U;valid_=true;
                stop(t,Result::Success);return;
            }
            if(io!=Io::Pending){stop(t,Result::Network);return;}
            return;
        }
        const uint32_t after=t.nowMs();
        if(late(after)){stop(t,Result::Timeout);return;}
        if(io==Io::Failed){stop(t,Result::Network);return;}
        if(io==Io::Done){
            if(phase_==Phase::Dns)enter(Phase::Connect,after);
            else if(phase_==Phase::Connect)enter(Phase::Write,after);
            else if(sent_==requestSize_){work_[0]=0;enter(Phase::Headers,after);}
        }
    }
    // HOST fixture marker is explicit. Future native integration is not supplied.
    template<class WeatherData> bool view(WeatherData& out,uint32_t now,const Conditions& c) const {
        out=WeatherData{};out.synthetic=true;
        if(!last_.utc)return false;
        out.valid=true;out.tenthsC=last_.value.tenthsC;out.wmoCode=last_.value.code;
        // Preserve an expired sample only to label STALE; zero lease prevents revival.
        out.observedMs=accepted_;out.validForMs=valid_?lease_:0;
        const char* label=B53WeatherFrame::label(last_.value.code);
        if(label)strncpy(out.condition,label,sizeof(out.condition)-1);
        return fresh(now,c);
    }
};
}
