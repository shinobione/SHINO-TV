// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Fixed RAM clock policy. No Arduino, networking, libc TZ, filesystem or heap.
// Only the admitted Digest clock route may call synchronize in the native graph.
#include <display/SceneEngine.h>
#include <stdint.h>

namespace ClockFoundation {
constexpr uint32_t MIN_UTC=1577836800U, MAX_UTC=4102444799U; // 2020..2099
constexpr unsigned MAX_LEASE_S=120;
struct Snapshot {
    uint32_t utc=0,ageMs=0,remainingMs=0,generation=0;
    int16_t offsetMinutes=0;
    bool valid=false,synced=false;
};
class State {
    uint32_t utc_=0,since_=0,leaseMs_=0,generation_=0;
    int16_t offset_=0;
    bool synced_=false,expired_=false;
    static unsigned daysInMonth(unsigned year,unsigned month){
        static constexpr uint8_t days[]={31,28,31,30,31,30,31,31,30,31,30,31};
        return days[month-1]+(month==2&&year%4==0&&(year%100!=0||year%400==0));
    }
    static void civil(uint32_t utc,int offset,ArtworkPilot::ClockData& out){
        // Epoch/offset bounds guarantee a positive date within 2019..2100.
        const int64_t local=int64_t(utc)+int64_t(offset)*60;
        uint32_t days=uint32_t(local/86400),seconds=uint32_t(local%86400);
        unsigned year=1970,month=1;
        for(unsigned count=0;count<131;++count){
            const unsigned size=365+(year%4==0&&(year%100!=0||year%400==0));
            if(days<size)break;
            days-=size;++year;
        }
        while(month<12&&days>=daysInMonth(year,month)){days-=daysInMonth(year,month);++month;}
        out.year=uint16_t(year);out.month=uint8_t(month);out.day=uint8_t(days+1);
        out.hour=uint8_t(seconds/3600);out.minute=uint8_t((seconds/60)%60);out.second=uint8_t(seconds%60);
    }
public:
    bool synchronize(uint32_t utc,int offset,unsigned lease,uint32_t started,uint32_t now){
        if(utc<MIN_UTC||utc>MAX_UTC||offset<-720||offset>840||
           !lease||lease>MAX_LEASE_S||uint32_t(now-started)>=lease*1000U||
           uint32_t(now-started)>=2000U)return false;
        if(synced_){
            const uint32_t age=uint32_t(now-since_);
            // Zero backward tolerance. Expiration never discards the watermark.
            if(utc<utc_||(!expired_&&age<leaseMs_&&utc+uint32_t(now-started)/1000U<utc_+age/1000U))return false;
        }
        utc_=utc;offset_=int16_t(offset);since_=started;leaseMs_=lease*1000U;
        synced_=true;expired_=false;++generation_;
        return true;
    }
    Snapshot snapshot(uint32_t now){
        const uint32_t age=uint32_t(now-since_);
        if(synced_&&age>=leaseMs_)expired_=true;
        const bool valid=synced_&&!expired_;
        return {valid?utc_+age/1000U:0,synced_?age:0,
                valid?leaseMs_-age:0,generation_,offset_,valid,synced_};
    }
    ArtworkPilot::ClockData view(uint32_t now){
        const auto s=snapshot(now);
        ArtworkPilot::ClockData out{};
        out.source=s.synced?ArtworkPilot::ClockSource::PairedPc:ArtworkPilot::ClockSource::Unknown;
        out.syncedMs=since_;out.utcOffsetMinutes=offset_;out.observedMs=now;
        out.valid=s.synced;out.validForMs=s.remainingMs;
        if(s.valid)civil(s.utc,s.offsetMinutes,out);
        return out;
    }
};
} // namespace ClockFoundation

