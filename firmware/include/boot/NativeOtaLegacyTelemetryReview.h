// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1 HOST-ONLY typed value model of the existing FslessMetrics::apply().
// This is NOT an ArduinoJson parser, real Windows POST handler, LCD painter,
// credential checker or connection to live FslessMetrics. The independent
// JSON decoding boundary and exact wire schema require separate host tests.
// No filesystem, EEPROM, flash, Updater, server or physical device access.
#include <cmath>
#include <cstdint>

namespace ShinoNativeOta {
struct LegacyNumericField {
    bool isNumeric=false; // JSON bool/string/null are NOT numeric.
    double value=0.0;
};
struct LegacyTelemetryInput {
    bool objectPresent=false;
    bool okIsBoolean=false,ok=false;
    bool gpuAvailableIsBoolean=false,gpuAvailable=false;
    LegacyNumericField cpuUsage{},gpuUsage{},memoryUsedGb{},gpuVramMb{},
                       gpuTempC{},gpuPower{},memoryTotalGb{};
    bool memoryTotalPresent=false; // Old PC companion may omit this field.
};
struct LegacyTelemetrySnapshot {
    float cpu=0.0f,gpu=0.0f,memoryGb=0.0f,memoryTotalGb=0.0f,
          vramMb=0.0f,gpuTempC=0.0f,gpuPowerW=0.0f;
    bool gpuAvailable=false,received=false;
    uint32_t lastReceivedMs=0u;
};
enum class LegacyTelemetryResult : uint8_t {
    InvalidEnvelope, InvalidNumbers, InvalidTotalRam,
    AcceptedIntoHostFixtureRamOnly
};
class NativeOtaLegacyTelemetryReview final {
public:
    static constexpr uint32_t kStaleMs=6000u;
    // These represent exact FslessMetrics field limits, not GPU danger bands.
    static constexpr double kPercentMax=100.0;
    static constexpr double kMemoryMaxGb=256.0;
    static constexpr double kVramMaxMb=65536.0;
    static constexpr double kTempMinC=-40.0;
    static constexpr double kTempMaxC=130.0;
    static constexpr double kPowerMaxW=1200.0;

    LegacyTelemetryResult applyFixture(const LegacyTelemetryInput& in,uint32_t nowMs) {
        if(!in.objectPresent || !in.okIsBoolean || !in.ok ||
           !in.gpuAvailableIsBoolean)
            return LegacyTelemetryResult::InvalidEnvelope;
        LegacyTelemetrySnapshot next{};
        if(!bounded(in.cpuUsage,0.0,kPercentMax,next.cpu) ||
           !bounded(in.gpuUsage,0.0,kPercentMax,next.gpu) ||
           !bounded(in.memoryUsedGb,0.0,kMemoryMaxGb,next.memoryGb) ||
           !bounded(in.gpuVramMb,0.0,kVramMaxMb,next.vramMb) ||
           !bounded(in.gpuTempC,kTempMinC,kTempMaxC,next.gpuTempC) ||
           !bounded(in.gpuPower,0.0,kPowerMaxW,next.gpuPowerW))
            return LegacyTelemetryResult::InvalidNumbers;
        if(in.memoryTotalPresent &&
           (!bounded(in.memoryTotalGb,0.01,kMemoryMaxGb,next.memoryTotalGb) ||
            next.memoryGb>next.memoryTotalGb))
            return LegacyTelemetryResult::InvalidTotalRam;
        next.gpuAvailable=in.gpuAvailable;
        next.received=true;
        next.lastReceivedMs=nowMs;
        snapshot_=next; // An invalid sample never replaces the last good one.
        return LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly;
    }
    LegacyTelemetrySnapshot snapshotForHostTestOnly() const {return snapshot_;}
    bool stale(uint32_t nowMs) const {
        return !snapshot_.received ||
            static_cast<uint32_t>(nowMs-snapshot_.lastReceivedMs)>kStaleMs;
    }
    bool memoryTotalAvailable() const {return snapshot_.memoryTotalGb>0.0f;}
    bool realDeviceMetricsChanged() const {return false;}
    bool fourLcdCardsActuallyRepainted() const {return false;}
private:
    static bool bounded(const LegacyNumericField& field,double low,double high,float& out) {
        if(!field.isNumeric || !std::isfinite(field.value) ||
           field.value<low || field.value>high)return false;
        out=static_cast<float>(field.value);
        return true;
    }
    LegacyTelemetrySnapshot snapshot_{};
};
} // namespace ShinoNativeOta
