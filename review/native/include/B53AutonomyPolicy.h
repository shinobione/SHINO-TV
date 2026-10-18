// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Pure B5.3 clock/weather decision policy. No Arduino, network, heap or storage.
// A provider MUST validate actual sync/protocol trust before calling accept*().
#include <stdint.h>

namespace B53Autonomy {
constexpr uint32_t UTC_MIN = 1577836800U; // 2020-01-01
constexpr uint32_t UTC_MAX = 4102444799U; // 2099-12-31
constexpr uint32_t PC_MAX_LEASE_MS = 120000U;
constexpr uint32_t NTP_MAX_LEASE_MS = 21600000U; // 6 hours after confirmed SNTP
constexpr uint32_t WEATHER_MAX_LEASE_MS = 2700000U; // 45 minutes
constexpr uint32_t MAX_ELAPSED_MS = 0x7fffffffU;

enum class Authority : uint8_t { None, PairedPc, Sntp };
struct TimeView {
    Authority authority = Authority::None;
    uint32_t utc = 0;
    int16_t offsetMinutes = 0;
    uint32_t ageMs = 0;
    bool valid = false;
};
struct WeatherView {
    int16_t temperatureTenthsC = 0;
    uint8_t wmoCode = 0;
    uint32_t ageMs = 0;
    bool valid = false;
};

class Policy {
    struct TimeSlot {
        uint32_t utc = 0, receivedMs = 0, leaseMs = 0;
        int16_t offset = 0;
        bool received = false;
    } pc_, ntp_;
    struct WeatherSlot {
        int16_t tenthsC = 0;
        uint8_t code = 0;
        uint32_t receivedMs = 0, leaseMs = 0;
        bool received = false;
    } weather_;

    static bool utcValid(uint32_t utc, int16_t offset) {
        return utc >= UTC_MIN && utc <= UTC_MAX && offset >= -720 && offset <= 840;
    }
    static bool fresh(uint32_t receivedAt, uint32_t lease, uint32_t now) {
        const uint32_t age = uint32_t(now - receivedAt);
        // Millis subtraction supports rollover for bounded lease durations.
        return lease != 0 && lease < MAX_ELAPSED_MS && age < lease;
    }
    static bool timeValid(const TimeSlot& slot, uint32_t now) {
        if (!slot.received || !fresh(slot.receivedMs, slot.leaseMs, now)) return false;
        const uint32_t advance = uint32_t(now - slot.receivedMs)/1000U;
        return uint64_t(slot.utc) + advance <= UTC_MAX;
    }
    bool acceptTime(TimeSlot& slot, uint32_t utc, int16_t offset, uint32_t now,
                    uint32_t leaseMs, uint32_t limit) {
        if (!utcValid(utc,offset) || leaseMs == 0 || leaseMs > limit) return false;
        // A correction within a valid authority cannot run backwards.
        if (timeValid(slot,now) && utc < slot.utc + uint32_t(now-slot.receivedMs)/1000U)
            return false;
        slot = {utc,now,leaseMs,offset,true};
        return true;
    }
public:
    bool acceptPc(uint32_t utc, int16_t offset, uint32_t now, uint32_t leaseMs) {
        return acceptTime(pc_,utc,offset,now,leaseMs,PC_MAX_LEASE_MS);
    }
    bool acceptSntp(uint32_t utc, int16_t offset, uint32_t now, uint32_t leaseMs) {
        return acceptTime(ntp_,utc,offset,now,leaseMs,NTP_MAX_LEASE_MS);
    }
    TimeView time(uint32_t now) const {
        const TimeSlot* slot = nullptr;
        Authority source = Authority::None;
        if (timeValid(pc_,now)) { slot=&pc_; source=Authority::PairedPc; }
        else if (timeValid(ntp_,now)) { slot=&ntp_; source=Authority::Sntp; }
        if (!slot) return {};
        const uint32_t age = uint32_t(now-slot->receivedMs);
        return {source, uint32_t(slot->utc + age/1000U),slot->offset,age,true};
    }
    bool acceptWeather(int16_t tempTenths, uint8_t wmoCode, uint32_t now,
                       uint32_t leaseMs) {
        // Not every WMO code in 0..99 is defined. Providers must decode and
        // strictly validate their supported codes before invoking this seam.
        if (tempTenths < -900 || tempTenths > 700 || wmoCode > 99 ||
            !leaseMs || leaseMs > WEATHER_MAX_LEASE_MS) return false;
        weather_ = {tempTenths,wmoCode,now,leaseMs,true};
        return true;
    }
    WeatherView weather(uint32_t now) const {
        if (!weather_.received || !fresh(weather_.receivedMs,weather_.leaseMs,now)) return {};
        return {weather_.tenthsC,weather_.code,uint32_t(now-weather_.receivedMs),true};
    }
};
} // namespace B53Autonomy
