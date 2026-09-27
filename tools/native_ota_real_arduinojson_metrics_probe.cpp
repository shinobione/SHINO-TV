// SPDX-License-Identifier: GPL-3.0-or-later
// HOST ONLY: links ORIGINAL firmware/src/boot/FslessMetrics.cpp against actual
// exact PlatformIO ArduinoJson 7.4.3, with a minimal Arduino.h millis/String
// shim. Reads JSON lines from stdin; does not own any TCP/server, Digest,
// private credential, OTA route, Updater, filesystem or device hardware.
// Outputs fixture outcomes and original RAM snapshot as line-delimited JSON.
#include "boot/FslessMetrics.h"
#include <ArduinoJson.h>
#include <cstdint>
#include <iostream>
#include <string>

static_assert(ARDUINOJSON_VERSION_MAJOR == 7 &&
              ARDUINOJSON_VERSION_MINOR == 4 &&
              ARDUINOJSON_VERSION_REVISION == 3,
              "Host comparison must use exact same pinned ArduinoJson 7.4.3.");
namespace {
uint32_t clockFixture=0u;
}
uint32_t millis() {return clockFixture;}
int main() {
    std::string line;
    uint32_t count=0u;
    while(std::getline(std::cin,line)) {
        if(line.size()>65536u)return 3; // host probe, not upload receiver.
        clockFixture=100u+count++;
        int status=200;
        JsonDocument doc;
        if(line.size()<16u || line.size()>384u) status=413;
        else {
            const DeserializationError result=deserializeJson(
                doc,line.data(),line.size());
            if(result)status=422;
            else {
                String error;
                if(!FslessMetrics::apply(doc.as<JsonVariantConst>(),error))
                    status=422;
            }
        }
        const auto state=FslessMetrics::snapshot();
        JsonDocument out;
        out["status"]=status;
        out["received"]=state.received;
        out["cpu_usage"]=state.cpu;
        out["gpu_usage"]=state.gpu;
        out["memory_used_gb"]=state.memoryGb;
        out["memory_total_gb"]=state.memoryTotalGb;
        out["gpu_vram_mb"]=state.vramMb;
        out["gpu_temp_c"]=state.gpuTempC;
        out["gpu_power"]=state.gpuPowerW;
        out["gpu_available"]=state.gpuAvailable;
        out["last_received_ms"]=state.lastReceivedMs;
        out["real_hardware_write"]=false;
        char result[512]{};
        const size_t written=serializeJson(out,result,sizeof(result));
        if(written==0u || written>=sizeof(result))return 4;
        std::cout<<result<<'\n';
    }
    return 0;
}
