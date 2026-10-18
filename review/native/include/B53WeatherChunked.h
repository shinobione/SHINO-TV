// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Bounded HTTP/1.1 chunked decoder: exact CRLF, no extensions or trailers,
// no allocation, no decoded body beyond configured capacity.
#include <stdint.h>
#include <stddef.h>
namespace B53WeatherChunked {
class Decoder {
    enum class Stage:uint8_t { Size, SizeLF, Data, DataCR, DataLF,
                               FinalCR, FinalLF, Complete, Invalid };
    Stage stage_=Stage::Size;
    char* const out_;
    const size_t cap_;
    size_t total_=0,remaining_=0,chunk_=0;
    unsigned digits_=0;
    bool fail(){stage_=Stage::Invalid;return false;}
public:
    Decoder(char* buffer,size_t cap):out_(buffer),cap_(cap){}
    void reset(){stage_=Stage::Size;total_=remaining_=chunk_=0;digits_=0;}
    bool complete()const{return stage_==Stage::Complete;}
    size_t size()const{return total_;}
    bool consume(uint8_t c){
        switch(stage_){
        case Stage::Size:{
            if(c=='\r'){
                if(!digits_||chunk_>cap_-total_)return fail();
                remaining_=chunk_;stage_=Stage::SizeLF;return true;
            }
            unsigned v;
            if(c>='0'&&c<='9')v=c-'0';
            else if(c>='a'&&c<='f')v=c-'a'+10;
            else if(c>='A'&&c<='F')v=c-'A'+10;
            else return fail();
            if(digits_>=4)return fail();
            chunk_=chunk_*16U+v;++digits_;
            if(chunk_>cap_-total_)return fail();
            return true;
        }
        case Stage::SizeLF:
            if(c!='\n')return fail();
            stage_=remaining_?Stage::Data:Stage::FinalCR;return true;
        case Stage::Data:
            if(total_>=cap_||remaining_==0)return fail();
            out_[total_++]=char(c);
            if(--remaining_==0)stage_=Stage::DataCR;
            return true;
        case Stage::DataCR:
            if(c!='\r')return fail();
            stage_=Stage::DataLF;return true;
        case Stage::DataLF:
            if(c!='\n')return fail();
            stage_=Stage::Size;digits_=0;chunk_=0;return true;
        case Stage::FinalCR:
            if(c!='\r')return fail();
            stage_=Stage::FinalLF;return true;
        case Stage::FinalLF:
            if(c!='\n')return fail();
            out_[total_]=0;stage_=Stage::Complete;return true;
        default:return fail();
        }
    }
};
}
