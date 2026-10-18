// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#if defined(ESP8266)
#include <pgmspace.h>
#define B53_DIAG_FLASH PROGMEM
#else
#define B53_DIAG_FLASH
#endif
namespace B53Diagnostic {
namespace Encoding {
static const char hex[] B53_DIAG_FLASH="0123456789abcdef";
static const char prefix[] B53_DIAG_FLASH="{\"b53_diag\":1,\"page\":";
static const char seq[] B53_DIAG_FLASH=",\"sequence_hex\":\"";
static const char body[] B53_DIAG_FLASH="\",\"hex\":\"";
inline void copy(char* out,const char* source,size_t n){
#if defined(ESP8266)
    memcpy_P(out,source,n);
#else
    memcpy(out,source,n);
#endif
}
inline char digit(unsigned n){
#if defined(ESP8266)
    return char(pgm_read_byte(hex+n));
#else
    return hex[n];
#endif
}
}

enum CaptureStop : uint32_t { InvalidCapture=0x100, ResourceFloor=0x101 };
struct Record {
    uint32_t timeUs, sequence, heap, block, stack, loopUs, gapUs;
    uint8_t event, fragmentation, valid, reserved;
};
enum Word : unsigned {
    Version, Started, Head, Sequence, Samples, Overwrites, Invalid, Lost, Missed,
    HeapMin, BlockMin, StackMin, FragMax, LoopMax, GapMax, CaptureMax,
    LastEntry, Entry, LoopCount, LoopOpen, LastSample, EncodeMax, Unsafe,
    Frozen, StopReason, CallbackMax0, CallbackMax1, CallbackMax2, CallbackMax3,
    CallbackMaxDns, DnsQueries, DnsCallbacks, DnsLate, DnsPending, DnsElapsed,
    PcbCreated, PcbReleased, PbufSeen, PbufFreed, TcpConnectedMs, TcpReleasedMs,
    DeferredCaptures, LastDecision, DecisionReason, LinkAgeMax, LinkLatencyMax,
    CallbackCalls0, CallbackCalls1, CallbackCalls2, CallbackCalls3,
    OutstandingPcb, OutstandingPbuf, DnsStartedMs, DnsEndedMs, LinkAccepts,
    LastAbortMs, AbortReason, LinkStaleEpisodes, LinkAcceptIntervalMax,
    WordsUsed
};
struct Control { uint32_t word[64]{}; };
static_assert(sizeof(Record)==32,"Diagnostic record exactly32 bytes");
static_assert(sizeof(Control)==256,"Diagnostic control exactly256 bytes");
static_assert(WordsUsed<=64,"Control capacity");
class Journal {
    static void increment(uint32_t& n){if(n!=UINT32_MAX)++n;}
    static void maximum(uint32_t& n,uint32_t value){if(value>n)n=value;}
public:
    Record records[16]{};
    Control control{};
    bool started()const{return control.word[Started]!=0;}
    bool frozen()const{return control.word[Frozen]!=0;}
    void stop(uint32_t reason){if(!frozen()){control.word[StopReason]=reason;control.word[Frozen]=1;}}
    void lost(){if(!frozen())increment(control.word[Lost]);}
    void value(Word index,uint32_t n){if(!frozen())control.word[index]=n;}
    void peak(Word index,uint32_t n){if(!frozen())maximum(control.word[index],n);}
    void count(Word index){if(!frozen())increment(control.word[index]);}
    void start(uint32_t now){
        if(started()){lost();return;} // Never reset an active measurement window.
        auto* w=control.word;w[Version]=1;w[Started]=1;
        w[HeapMin]=w[BlockMin]=w[StackMin]=UINT32_MAX;
        w[LastEntry]=w[LastSample]=now;
    }
    void enter(uint32_t now){
        if(!started()||frozen())return;
        auto* w=control.word;if(w[LoopOpen]){lost();return;}
        if(w[LoopCount])maximum(w[GapMax],uint32_t(now-w[LastEntry]));
        w[LastEntry]=w[Entry]=now;w[LoopOpen]=1;
    }
    void leave(uint32_t now){
        if(!started()||frozen())return;
        auto* w=control.word;if(!w[LoopOpen]){lost();return;}
        maximum(w[LoopMax],uint32_t(now-w[Entry]));w[LoopOpen]=0;increment(w[LoopCount]);
    }
    void captureCost(uint32_t elapsed){peak(CaptureMax,elapsed);}
    void encodeCost(uint32_t elapsed){peak(EncodeMax,elapsed);}
    void capture(uint32_t now,uint32_t heap,uint32_t block,uint8_t frag,
                 uint32_t stack,uint32_t elapsed){
        if(!started()||frozen())return;
        auto* w=control.word;captureCost(elapsed);
        if(!heap||heap>81920||!block||block>heap||frag>100||
           stack>4096||stack%4||stack>w[StackMin]){
            increment(w[Invalid]);stop(InvalidCapture);return;
        }
        if(w[Sequence]==UINT32_MAX){lost();return;}
        if(w[Samples]){
            const uint32_t periods=uint32_t(now-w[LastSample])/1000000U;
            if(periods>1){const uint32_t missing=periods-1;
                w[Missed]=missing>UINT32_MAX-w[Missed]?UINT32_MAX:w[Missed]+missing;}
        }
        w[LastSample]=now;
        if(heap<w[HeapMin])w[HeapMin]=heap;
        if(block<w[BlockMin])w[BlockMin]=block;
        if(stack<w[StackMin])w[StackMin]=stack;
        maximum(w[FragMax],frag);
        const bool unsafe=heap<20480||block<16384||stack<2048||frag>25;
        if(unsafe)increment(w[Unsafe]);
        increment(w[Sequence]);increment(w[Samples]);
        if(w[Samples]>16)increment(w[Overwrites]);
        records[w[Head]]={now,w[Sequence],heap,block,stack,w[LoopMax],w[GapMax],1,frag,1,0};
        w[Head]=(w[Head]+1U)%16U;
        if(unsafe)stop(ResourceFloor);
    }
    // Fixed three-page, little-endian native word encoding. Caller owns output.
    // Snapshot is serialized before any HTTP send/yield. No journal mutation here.
    size_t encode(unsigned page,char* out,size_t cap)const{
        if(!out||cap<600||page>2)return 0;
        using namespace Encoding;
        size_t n=sizeof(prefix)-1;copy(out,prefix,n);out[n++]=char('0'+page);
        copy(out+n,seq,sizeof(seq)-1);n+=sizeof(seq)-1;
        for(unsigned i=0;i<8;++i)out[n++]=digit((control.word[Sequence]>>(28U-4U*i))&15U);
        copy(out+n,body,sizeof(body)-1);n+=sizeof(body)-1;
        const auto* bytes=page==0?reinterpret_cast<const uint8_t*>(&control):
            reinterpret_cast<const uint8_t*>(records+(page-1)*8);
        for(unsigned i=0;i<256;++i){out[n++]=digit(bytes[i]>>4);out[n++]=digit(bytes[i]&15);}
        out[n++]='"';out[n++]='}';out[n++]='\n';out[n]=0;return n;
    }
};
static_assert(sizeof(Journal)==16*32+256,"Total diagnostic RAM exactly768 bytes");
}

#undef B53_DIAG_FLASH
