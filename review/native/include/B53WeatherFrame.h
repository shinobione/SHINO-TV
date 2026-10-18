// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Small, strict Open-Meteo "current" JSON decoder. Zero allocations.
// Entire HTTP body is limited by the transport to at most 768 bytes.
// Fails closed on incomplete JSON, duplicate fields, invalid codes/temperature.
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#if defined(ESP8266)
#include <pgmspace.h>
#define B53_WEATHER_TEXT(s) PSTR(s)
#define B53_WEATHER_STORAGE PROGMEM
#else
#define B53_WEATHER_TEXT(s) (s)
#define B53_WEATHER_STORAGE
#endif

namespace B53WeatherFrame {
namespace Text {
inline char read(const char* p){
#if defined(ESP8266)
    return char(pgm_read_byte(p));
#else
    return *p;
#endif
}
inline bool equals(const char* ram,const char* literal){
    for(size_t i=0;;++i){const char c=read(literal+i);if(ram[i]!=c)return false;if(!c)return true;}
}
inline bool prefix(const char* ram,size_t available,const char* literal,size_t n){
    if(available<n)return false;
    for(size_t i=0;i<n;++i)if(ram[i]!=read(literal+i))return false;
    return true;
}
}
constexpr size_t MAX_BODY=768;
struct Sample { int16_t tenthsC=0; uint8_t code=0; };
struct TimedSample { Sample value{}; uint32_t utc=0; };
// Strict UTC minute, requested with timezone=UTC. No local/PC timezone guess.
inline bool utcMinute(const char* s,uint32_t& out) {
    if(strlen(s)!=16 || s[4]!='-' || s[7]!='-' || s[10]!='T' || s[13]!=':')return false;
    for(unsigned i=0;i<16;++i)
        if(i!=4 && i!=7 && i!=10 && i!=13 && (s[i]<'0'||s[i]>'9'))return false;
    const unsigned year=unsigned(s[0]-'0')*1000+unsigned(s[1]-'0')*100+
        unsigned(s[2]-'0')*10+unsigned(s[3]-'0');
    const unsigned month=unsigned(s[5]-'0')*10+unsigned(s[6]-'0');
    const unsigned day=unsigned(s[8]-'0')*10+unsigned(s[9]-'0');
    const unsigned hour=unsigned(s[11]-'0')*10+unsigned(s[12]-'0');
    const unsigned minute=unsigned(s[14]-'0')*10+unsigned(s[15]-'0');
    if(year<2020||year>2099||month<1||month>12||hour>23||minute>59)return false;
    static const uint8_t days[] B53_WEATHER_STORAGE={31,28,31,30,31,30,31,31,30,31,30,31};
    const auto daysAt=[](unsigned i){return unsigned(uint8_t(Text::read(reinterpret_cast<const char*>(days+i))));};
    const unsigned max=daysAt(month-1)+unsigned(month==2 && year%4==0);
    if(day<1||day>max)return false;
    uint32_t count=0;
    for(unsigned y=1970;y<year;++y)count+=365U+unsigned(y%4==0);
    for(unsigned m=1;m<month;++m)count+=daysAt(m-1)+unsigned(m==2 && year%4==0);
    out=((count+day-1)*24U+hour)*3600U+minute*60U;
    return true;
}
#if defined(__GNUC__) && !defined(__clang__)
__attribute__((optimize("no-tree-switch-conversion")))
#endif
inline const char* label(uint8_t code) {
    switch(code) {
    case 0:return "Clear"; case 1:return "Mostly clear";
    case 2:return "Partly cloudy"; case 3:return "Cloudy";
    case 45:case 48:return "Fog";
    case 51:case 53:case 55:return "Drizzle";
    case 56:case 57:return "Icy drizzle";
    case 61:case 63:case 65:return "Rain";
    case 66:case 67:return "Freezing rain";
    case 71:case 73:case 75:return "Snow";
    case 77:return "Snow grains";
    case 80:case 81:case 82:return "Showers";
    case 85:case 86:return "Snow showers";
    case 95:return "Thunder";
    case 96:case 99:return "Thunder hail";
    default:return nullptr;
    }
}
class Reader {
    const char* data_;
    size_t n_,i_=0;
    bool gotCurrent_=false,gotTemp_=false,gotCode_=false;
    Sample sample_{};
    bool timed_=false,gotTime_=false;
    uint32_t utc_=0;
    void spaces(){while(i_<n_&&(data_[i_]==' '||data_[i_]=='\t'||data_[i_]=='\n'||data_[i_]=='\r'))++i_;}
    bool eat(char c){spaces();if(i_<n_&&data_[i_]==c){++i_;return true;}return false;}
    bool string(char* out,size_t cap){
        spaces();if(i_==n_||data_[i_++]!='"')return false;
        size_t used=0;
        while(i_<n_){
            unsigned char c=static_cast<unsigned char>(data_[i_++]);
            if(c=='"'){if(out&&cap)out[used]=0;return true;}
            if(c<0x20 || c>0x7e)return false;
            if(c=='\\'){
                if(i_==n_)return false;
                c=static_cast<unsigned char>(data_[i_++]);
                if(c=='u'){
                    for(unsigned k=0;k<4;++k){
                        if(i_==n_)return false;
                        unsigned char h=static_cast<unsigned char>(data_[i_++]);
                        if(!((h>='0'&&h<='9')||(h>='A'&&h<='F')||(h>='a'&&h<='f')))return false;
                    }
                    c='?';
                } else if(c=='"'||c=='\\'||c=='/'||c=='b'||c=='f'||c=='n'||c=='r'||c=='t')c='?';
                else return false;
            }
            if(out){if(used+1>=cap)return false;out[used]=char(c);}
            ++used;
        }
        return false;
    }
    bool number(int32_t& scaled, bool integerOnly){
        spaces();const size_t start=i_;
        bool negative=false;
        if(i_<n_&&data_[i_]=='-'){negative=true;++i_;}
        if(i_==n_)return false;
        int32_t value=0;
        unsigned digits=0;
        if(data_[i_]=='0'){++i_;digits=1;if(i_<n_&&data_[i_]>='0'&&data_[i_]<='9')return false;}
        else while(i_<n_&&data_[i_]>='0'&&data_[i_]<='9'){
            if(++digits>4)return false;
            value=value*10+(data_[i_++]-'0');
        }
        if(!digits)return false;
        int32_t frac=0;
        if(i_<n_&&data_[i_]=='.'){
            if(integerOnly)return false;
            ++i_;
            if(i_==n_||data_[i_]<'0'||data_[i_]>'9')return false;
            frac=data_[i_++]-'0';
            if(i_<n_&&data_[i_]>='0'&&data_[i_]<='9')return false;
        }
        if(i_==start)return false;
        if(i_<n_&&(data_[i_]=='e'||data_[i_]=='E'||data_[i_]=='+'))return false;
        scaled=(value*(integerOnly?1:10)+frac)*(negative?-1:1);
        return true;
    }
    bool scalar(){
        spaces();if(i_==n_)return false;
        if(data_[i_]=='"')return string(nullptr,0);
        if(Text::prefix(data_+i_,n_-i_,B53_WEATHER_TEXT("true"),4)){i_+=4;return true;}
        if(Text::prefix(data_+i_,n_-i_,B53_WEATHER_TEXT("false"),5)){i_+=5;return true;}
        if(Text::prefix(data_+i_,n_-i_,B53_WEATHER_TEXT("null"),4)){i_+=4;return true;}
        // Ignore well-formed finite JSON numbers in unrelated keys.
        bool hadDigit=false;
        if(data_[i_]=='-')++i_;
        if(i_>=n_)return false;
        if(data_[i_]=='0'){hadDigit=true;++i_;if(i_<n_&&data_[i_]>='0'&&data_[i_]<='9')return false;}
        else while(i_<n_&&data_[i_]>='0'&&data_[i_]<='9'){hadDigit=true;++i_;}
        if(!hadDigit)return false;
        if(i_<n_&&data_[i_]=='.'){
            ++i_;const size_t prior=i_;
            while(i_<n_&&data_[i_]>='0'&&data_[i_]<='9')++i_;
            if(prior==i_)return false;
        }
        if(i_<n_&&(data_[i_]=='e'||data_[i_]=='E')){
            ++i_;if(i_<n_&&(data_[i_]=='+'||data_[i_]=='-'))++i_;
            const size_t prior=i_;
            while(i_<n_&&data_[i_]>='0'&&data_[i_]<='9')++i_;
            if(prior==i_)return false;
        }
        return true;
    }
    bool object(){
        enum class Kind:uint8_t { Root,Current,Object,Array };
        enum class State:uint8_t { First,Required,Value,End };
        enum class Key:uint8_t { Other,Current,Time,Temp,Code };
        struct Context {Kind kind;State state;Key key;uint8_t count,depth;};
        // Root + current + up to four unknown containers; no recursive calls.
        Context stack[6]{};
        char token[48]; // Keys and timestamp have disjoint lifetimes.
        if(!eat('{'))return false;
        unsigned used=1;
        stack[0]={Kind::Root,State::First,Key::Other,0,0};
        for(unsigned steps=0;used && steps<MAX_BODY*2+8;++steps){
            auto& c=stack[used-1];
            const bool array=c.kind==Kind::Array;
            const char close=array?']':'}';
            if(c.state==State::First && eat(close)){
                if(c.kind==Kind::Current)return false; // Empty current is invalid.
                --used;continue;
            }
            if(c.state==State::First||c.state==State::Required){
                if(c.count>=48)return false;
                c.key=Key::Other;
                if(!array){
                    const bool relevant=c.kind==Kind::Root||c.kind==Kind::Current;
                    if(!string(relevant?token:nullptr,relevant?sizeof token:0)||!eat(':'))return false;
                    if(c.kind==Kind::Root && Text::equals(token,B53_WEATHER_TEXT("current")))c.key=Key::Current;
                    if(c.kind==Kind::Current){
                        if(timed_&&Text::equals(token,B53_WEATHER_TEXT("time")))c.key=Key::Time;
                        else if(Text::equals(token,B53_WEATHER_TEXT("temperature_2m")))c.key=Key::Temp;
                        else if(Text::equals(token,B53_WEATHER_TEXT("weather_code")))c.key=Key::Code;
                    }
                }
                c.state=State::Value;continue;
            }
            if(c.state==State::End){
                if(eat(close)){
                    if(c.kind==Kind::Current && (!gotTemp_||!gotCode_))return false;
                    --used;continue;
                }
                if(!eat(','))return false;
                c.state=State::Required;continue;
            }
            ++c.count;c.state=State::End;
            if(c.key==Key::Time){
                if(gotTime_||!string(token,17)||!utcMinute(token,utc_))return false;
                gotTime_=true;
            }else if(c.key==Key::Temp){
                int32_t t=0;if(gotTemp_||!number(t,false)||t<-900||t>700)return false;
                sample_.tenthsC=int16_t(t);gotTemp_=true;
            }else if(c.key==Key::Code){
                int32_t code=0;
                if(gotCode_||!number(code,true)||code<0||code>99||!label(uint8_t(code)))return false;
                sample_.code=uint8_t(code);gotCode_=true;
            }else if(c.key==Key::Current){
                if(gotCurrent_||!eat('{')||used>=6)return false;
                gotCurrent_=true;
                stack[used++]={Kind::Current,State::First,Key::Other,0,0};
            }else{
                const unsigned depth=c.depth+1;
                if(depth>4)return false;
                spaces();if(i_==n_)return false;
                if(data_[i_]=='{'||data_[i_]=='['){
                    if(used>=6)return false;
                    const Kind kind=data_[i_++]=='['?Kind::Array:Kind::Object;
                    stack[used++]={kind,State::First,Key::Other,0,uint8_t(depth)};
                }else if(!scalar())return false;
            }
        }
        return used==0;
    }
public:
    Reader(const char* data,size_t n):data_(data),n_(n){}
    bool parse(Sample& out){
        if(!data_||!n_||n_>MAX_BODY||!object())return false;
        spaces();if(i_!=n_||!gotCurrent_||!gotTemp_||!gotCode_||(timed_&&!gotTime_))return false;
        out=sample_;return true;
    }
    bool parseTimed(TimedSample& out){
        timed_=true;Sample value{};
        if(!parse(value))return false;
        out={value,utc_};return true;
    }
};
inline bool parse(const char* data,size_t n,Sample& out){return Reader(data,n).parse(out);}
inline bool parseTimed(const char* data,size_t n,TimedSample& out){return Reader(data,n).parseTimed(out);}
} // namespace B53WeatherFrame
