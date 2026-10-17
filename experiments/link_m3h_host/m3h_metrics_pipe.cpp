// M3-H HOST ONLY: original, unmodified FslessMetrics.cpp+real ArduinoJson
// acting as the injected PC telemetry sink. This executable has NO TCP,
// digest, firmware route, device secret, flash, LCD, OTA, LittleFS or Windows.
// Sample lines come from the real Python LINK encode_sample() contract.
#include "boot/FslessMetrics.h"
#include <ArduinoJson.h>
#include <cstdint>
#include <iostream>
#include <string>

static_assert(ARDUINOJSON_VERSION_MAJOR == 7 &&
              ARDUINOJSON_VERSION_MINOR == 4 &&
              ARDUINOJSON_VERSION_REVISION == 3,
              "Pinned ArduinoJson 7.4.3 required for M3-H original-code sink");
namespace {
uint32_t fakeNow = 100u;
}
uint32_t millis() {return fakeNow;}

int main() {
    std::string incoming;
    while(std::getline(std::cin,incoming)) {
        int code=200;
        if(incoming.size()<16u || incoming.size()>384u) code=413;
        else {
            JsonDocument parsed;
            if(deserializeJson(parsed,incoming.data(),incoming.size())) code=422;
            else {
                String issue;
                if(!FslessMetrics::apply(parsed.as<JsonVariantConst>(),issue))
                    code=422;
            }
        }
        JsonDocument output;
        output["code"]=code;
        output["host_only"]=true;
        output["applied_on_smalltv"]=false;
        auto state=FslessMetrics::snapshot();
        output["received"]=state.received;
        output["cpu_usage"]=state.cpu;
        output["gpu_usage"]=state.gpu;
        output["memory_used_gb"]=state.memoryGb;
        output["memory_total_gb"]=state.memoryTotalGb;
        output["gpu_temp_c"]=state.gpuTempC;
        output["last_received_ms"]=state.lastReceivedMs;
        char line[512]{};
        const size_t written=serializeJson(output,line,sizeof(line));
        if(written==0u || written>=sizeof(line)) return 3;
        std::cout.write(line,static_cast<std::streamsize>(written));
        std::cout<<std::endl; // flush for injected LINK sender roundtrip
        fakeNow+=2000u;
    }
    return 0;
}
