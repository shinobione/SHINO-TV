// SHINO // LINK M3-Q -- bounded M3-only header intake AFTER Core hook handoff.
// HOST/native-INERT research. This is NOT an authentication or display gate.
// The original B5.3 Core parsing remains unchanged for every legacy route.
#pragma once
#include <cstddef>
#include <cstdint>

namespace ShinoM3Q {
enum class State : uint8_t { Reading, ReadyForAuth, Rejected };
class HeaderGuard final {
public:
    // M3-C's bound is 1024 including the already-consumed request line.
    // 960 header bytes is conservative and deliberately independent.
    static constexpr size_t kMaxHeaderBytes = 960u;
    static constexpr size_t kMaxLineBytes = 320u;
    static constexpr uint32_t kDeadlineMs = 1000u;
    static constexpr uint16_t kRequired = (1u << 11u)-1u;

    State state() const { return state_; }
    size_t consumed() const { return total_; }
    unsigned fields() const { return fields_; }
    State reject() { state_=State::Rejected; return state_; }
    State feed(int byte, uint32_t now, uint32_t started) {
        if(state_!=State::Reading) return state_;
        if(static_cast<uint32_t>(now-started)>=kDeadlineMs ||
           byte<0 || byte>126 || (byte<32 && byte!='\r' && byte!='\n') ||
           total_>=kMaxHeaderBytes)
            return reject();
        ++total_;
        if(byte=='\r') {
            if(cr_) return reject();
            cr_=true;
            return state_;
        }
        if(byte=='\n') {
            if(!cr_) return reject();
            cr_=false;
            if(used_==0u) {
                state_=(seen_==kRequired && fields_==11u)
                    ?State::ReadyForAuth:State::Rejected;
                return state_;
            }
            if(!validLine()) return reject();
            used_=0;
            return state_;
        }
        if(cr_ || used_>=kMaxLineBytes) return reject();
        line_[used_++]=static_cast<char>(byte);
        return state_;
    }
private:
    // Kept as instance storage, not an unbounded String or CONT stack array.
    char line_[kMaxLineBytes+1u]{};
    size_t used_=0u;
    size_t total_=0u;
    uint16_t seen_=0u;
    uint8_t fields_=0u;
    bool cr_=false;
    State state_=State::Reading;
    struct Span {const char* p; size_t n;};
    static bool same(Span s,const char* text,bool folded=false) {
        size_t i=0;
        while(text[i]) {
            if(i>=s.n)return false;
            char a=s.p[i],b=text[i];
            if(folded){if(a>='A'&&a<='Z')a+=32;if(b>='A'&&b<='Z')b+=32;}
            if(a!=b)return false;
            ++i;
        }
        return i==s.n;
    }
    static bool hex(Span s,size_t exactLength,bool nonzero=false) {
        if(s.n!=exactLength)return false;
        bool any=false;
        for(size_t i=0;i<s.n;++i) {
            const char c=s.p[i];
            if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
            if(c!='0')any=true;
        }
        return !nonzero||any;
    }
    static bool decimal(Span s,uint32_t maximum,bool nonzero) {
        if(!s.n||s.n>10u||(s.n>1u&&s.p[0]=='0'))return false;
        uint32_t n=0;
        for(size_t i=0;i<s.n;++i) {
            const char c=s.p[i];
            if(c<'0'||c>'9')return false;
            const uint32_t digit=static_cast<uint32_t>(c-'0');
            if(digit>maximum || n>(maximum-digit)/10u)return false;
            n=n*10u+digit;
        }
        return !nonzero||n!=0;
    }
    bool validLine() {
        // Exactly one optional SP after colon; no folded lines/obs-text.
        size_t colon=0;
        while(colon<used_ && line_[colon]!=':')++colon;
        if(colon==0u||colon>=used_||colon>32u)return false;
        for(size_t i=0;i<colon;++i) {
            const char c=line_[i];
            if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||
                 (c>='0'&&c<='9')||c=='-'))return false;
        }
        size_t start=colon+1u;
        if(start<used_ && line_[start]==' ')++start;
        if(start==used_ || line_[start]==' ' || line_[used_-1u]==' ')return false;
        for(size_t i=start;i<used_;++i)
            if(line_[i]<'!'||line_[i]>'~')return false;
        const Span name{line_,colon}, val{line_+start,used_-start};
        unsigned field=11;
        static constexpr const char* labels[]={"Host","Content-Type","Content-Length",
          "Connection","X-Shino-Device","X-Shino-Boot","X-Shino-Revision",
          "X-Shino-Mode","X-Shino-Tx","X-Shino-Body-Sha256","X-Shino-Proof"};
        for(unsigned i=0;i<11;++i)if(same(name,labels[i],true)){field=i;break;}
        if(field==11 || (seen_ & (1u<<field))!=0u || fields_>=11u)return false;
        bool good=true;
        switch(field) {
            case 1:good=same(val,"application/json");break;
            case 2:good=decimal(val,240u,true);break;
            case 3:good=same(val,"close",true);break;
            case 4:good=hex(val,16u);break;
            case 5:good=hex(val,32u);break;
            case 6:good=decimal(val,0xfffffffeu,false);break;
            case 7:good=same(val,"AUTO")||same(val,"CLOCK_WEATHER")||
                         same(val,"MONITORING")||same(val,"MUSIC");break;
            case 8:good=hex(val,32u,true);break;
            case 9:good=hex(val,64u,true);break;
            case 10:good=hex(val,64u,true);break;
            default:break; // Host binding against real device is M3-C's job.
        }
        if(!good)return false;
        seen_=static_cast<uint16_t>(seen_|(1u<<field));
        ++fields_;
        return true;
    }
};

template<class Client,class Clock,class Yield>
__attribute__((noinline)) State readHeaders(Client& client,HeaderGuard& guard,
                                           Clock clock,Yield yield,uint32_t started) {
    while(guard.state()==State::Reading) {
        const uint32_t now=clock();
        if(static_cast<uint32_t>(now-started)>=HeaderGuard::kDeadlineMs)
            return guard.reject();
        if(client.available()<=0) {
            if(!client.connected())return guard.reject();
            yield();
            continue;
        }
        const int byte=client.read(); // one byte only; NEVER consume body
        guard.feed(byte,clock(),started);
    }
    return guard.state();
}
} // namespace ShinoM3Q
