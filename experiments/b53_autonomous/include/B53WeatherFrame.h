// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Small, strict Open-Meteo "current" JSON decoder. Zero allocations.
// Entire HTTP body is limited by the transport to at most 768 bytes.
// Fails closed on incomplete JSON, duplicate fields, invalid codes/temperature.
#include <stdint.h>
#include <stddef.h>
#include <string.h>

namespace B53WeatherFrame {
constexpr size_t MAX_BODY=768;
struct Sample { int16_t tenthsC=0; uint8_t code=0; };
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
    bool value(unsigned depth){
        if(depth>4)return false;
        spaces();if(i_==n_)return false;
        if(data_[i_]=='"')return string(nullptr,0);
        if(data_[i_]=='{'||data_[i_]=='['){
            const bool array=data_[i_++]=='[';
            spaces();
            if(eat(array?']':'}'))return true;
            for(unsigned items=0;items<48;++items){
                if(!array){if(!string(nullptr,0)||!eat(':'))return false;}
                if(!value(depth+1))return false;
                if(eat(array?']':'}'))return true;
                if(!eat(','))return false;
            }
            return false;
        }
        for(const char* k:{"true","false","null"}){
            const size_t len=strlen(k);
            if(n_-i_>=len && memcmp(data_+i_,k,len)==0){i_+=len;return true;}
        }
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
    bool object(bool current){
        if(!eat('{'))return false;
        if(eat('}'))return !current;
        for(unsigned fields=0;fields<48;++fields){
            char key[48]={};
            if(!string(key,sizeof(key))||!eat(':'))return false;
            if(current&&strcmp(key,"temperature_2m")==0){
                if(gotTemp_)return false;
                int32_t t=0;if(!number(t,false)||t<-900||t>700)return false;
                sample_.tenthsC=int16_t(t);gotTemp_=true;
            }else if(current&&strcmp(key,"weather_code")==0){
                if(gotCode_)return false;
                int32_t code=0;if(!number(code,true)||code<0||code>99||!label(uint8_t(code)))return false;
                sample_.code=uint8_t(code);gotCode_=true;
            }else if(!current&&strcmp(key,"current")==0){
                if(gotCurrent_)return false;
                gotCurrent_=true;if(!object(true))return false;
            }else if(!value(1))return false;
            if(eat('}'))return !current||(gotTemp_&&gotCode_);
            if(!eat(','))return false;
        }
        return false;
    }
public:
    Reader(const char* data,size_t n):data_(data),n_(n){}
    bool parse(Sample& out){
        if(!data_||!n_||n_>MAX_BODY||!object(false))return false;
        spaces();if(i_!=n_||!gotCurrent_||!gotTemp_||!gotCode_)return false;
        out=sample_;return true;
    }
};
inline bool parse(const char* data,size_t n,Sample& out){return Reader(data,n).parse(out);}
} // namespace B53WeatherFrame
