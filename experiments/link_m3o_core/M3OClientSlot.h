// SHINO // LINK M3-O: bounded lifetime of one handed-over connection.
// No request parsing, credentials, OTA, screen mutation or socket listener.
// A taken client is NEVER silently treated as a verified M3 command.
// This class is deliberately deny-only and owns one copied Client handle.
#pragma once
#include <cstdint>
namespace ShinoM3O {
enum class Result : uint8_t { Idle, Occupied, Denied, Expired };
template<class Client>
class ClientSlot final {
    Client current_{};
    bool busy_=false;
    uint32_t startedMs_=0u;
public:
    static constexpr uint32_t kHoldLimitMs=2000u;
    ClientSlot()=default;
    ClientSlot(const ClientSlot&)=delete;
    ClientSlot& operator=(const ClientSlot&)=delete;
    ~ClientSlot(){close();}
    bool busy()const{return busy_;}
    bool take(Client* offered,uint32_t now) {
        if(busy_ || !offered || !static_cast<bool>(*offered))return false;
        current_=*offered; // WiFiClient is handle-like; copy retained
        if(!static_cast<bool>(current_)) {
            current_=Client();
            return false;
        }
        busy_=true;startedMs_=now;
        return true;
    }
    // Exactly one bounded owner poll closes the refused socket. Nothing
    // is read: NOT a gateway to headers/body and NOT a mode ACK.
    Result denyAndRelease(uint32_t now) {
        if(!busy_)return Result::Idle;
        const Result outcome=static_cast<uint32_t>(now-startedMs_)>=kHoldLimitMs
            ?Result::Expired:Result::Denied;
        close();
        return outcome;
    }
    void close() {
        if(busy_)current_.stop();
        current_=Client();busy_=false;startedMs_=0u;
    }
};
}
