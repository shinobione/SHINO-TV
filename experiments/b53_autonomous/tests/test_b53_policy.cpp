// SPDX-License-Identifier: GPL-3.0-or-later
#include "B53AutonomyPolicy.h"
#include "B53Layout.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

int main() {
    using namespace B53Autonomy;
    Policy p;
    assert(!p.time(0).valid && !p.weather(0).valid);
    const uint32_t now=10000U, t=1792062000U;
    assert(!p.acceptPc(0,120,now,120000));
    assert(!p.acceptSntp(UTC_MAX+1U,120,now,1000));
    assert(!p.acceptPc(t,900,now,120000));
    assert(!p.acceptSntp(t,120,now,0));
    assert(!p.acceptSntp(t,120,now,NTP_MAX_LEASE_MS+1));
    assert(p.acceptSntp(t,120,now,NTP_MAX_LEASE_MS));
    auto v=p.time(now);assert(v.valid && v.authority==Authority::Sntp);
    assert(p.acceptPc(t,120,now,PC_MAX_LEASE_MS));
    v=p.time(now+3000);assert(v.valid && v.utc==t+3 && v.authority==Authority::PairedPc);
    assert(!p.acceptPc(t,120,now+3000,100000)); // same-source backward
    v=p.time(now+PC_MAX_LEASE_MS);assert(v.valid && v.authority==Authority::Sntp);
    assert(!p.time(now+NTP_MAX_LEASE_MS).valid);
    assert(!p.acceptWeather(710,2,now,1800000));
    assert(!p.acceptWeather(150,100,now,1800000));
    assert(!p.acceptWeather(150,2,now,WEATHER_MAX_LEASE_MS+1));
    assert(p.acceptWeather(182,2,now,1800000));
    assert(p.weather(now).valid && p.weather(now).temperatureTenthsC==182);
    assert(!p.weather(now+1800000).valid);
    // Cross-uint32 rollover: old valid data remains valid for bounded TTL.
    Policy rollover;
    const uint32_t nearWrap=0xfffffff0U;
    assert(rollover.acceptSntp(t,60,nearWrap,90000));
    assert(rollover.time(0x00000020).valid);
    assert(rollover.time(uint32_t(nearWrap+90000U)).valid==false);
    // Sensor bridge correctness depends on all cards fitting in LCD.
    for (auto card:B53Layout::CARDS) {
        assert(B53Layout::within(card));
        assert(B53Layout::CARD_BAR_OFFSET_X+B53Layout::CARD_BAR_WIDTH <= card.w);
        assert(B53Layout::CARD_BAR_OFFSET_Y+B53Layout::CARD_BAR_HEIGHT <= card.h);
    }
    std::puts("B53_HOST_POLICY_PASS");
}
