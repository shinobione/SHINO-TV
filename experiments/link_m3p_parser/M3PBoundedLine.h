// SHINO // LINK M3-P. Fixed upper bound BEFORE hook and BEFORE any
// allocation proportional to untrusted request-line bytes.
// Designed for the Core3.1.2 parser in an environment-local copy ONLY.
// No change to real framework package, to firmware, or to a device.
#pragma once
#include <cstddef>
#include <cstdint>
namespace ShinoM3P {
static constexpr size_t kMaxRequestLine=256u;
static constexpr uint32_t kRequestDeadlineMs=2000u;
template<class Client,class Text,class Clock,class Yield>
__attribute__((noinline)) bool readFirstLine(Client& client,Text& line,
                                             Clock clock,Yield yield,
                                             uint32_t started) {
    line.clear();
    while(static_cast<uint32_t>(clock()-started)<kRequestDeadlineMs) {
        if(client.available()<=0) {
            if(!client.connected())return false;
            yield();
            continue;
        }
        const int value=client.read();
        if(value=='\r') {
            // Reject LF absence or any byte other than LF. Do not scan
            // or buffer a second unbounded line with readStringUntil.
            while(client.available()<=0 &&
                  static_cast<uint32_t>(clock()-started)<kRequestDeadlineMs) {
                if(!client.connected())return false;
                yield();
            }
            return client.available()>0 && client.read()=='\n';
        }
        if(value<32||value>126||line.length()>=kMaxRequestLine)return false;
        line+=static_cast<char>(value);
    }
    return false;
}
} // namespace ShinoM3P
