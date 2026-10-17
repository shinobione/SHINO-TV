// Actual pinned Updater.cpp and BearSSL signing functions execute against RAM.
#include <fstream>
#include <iostream>
#include <sstream>
#include <memory>
#include <functional>
#include "Arduino.h"
#include <Updater.h>
#include <BearSSLHelpers.h>
// Host-only visibility seam permits simulated process-reset cleanup without
// adding abort/end-to-reset to the production adapter or changing Core logic.
#define private public
#include "M9SignedCore.h"
#undef private
#include "eboot_command.h"
HostESP ESP;
extern "C" {volatile uint32_t m9_host_rtc[32]{};
int memcmp_P(const void* a,const void* b,size_t bytes){return std::memcmp(a,b,bytes);}
br_ec_impl const* br_ec_get_default(void){return nullptr;}
br_ecdsa_vrfy br_ecdsa_vrfy_raw_get_default(void){return nullptr;}}
unsigned checks=0,transactions=0,failedBootDispatches=0;
#define CHECK(x) do{++checks;if(!(x))throw std::runtime_error("offline assertion line "+std::to_string(__LINE__));}while(0)
std::vector<uint8_t> read(const std::string& path){std::ifstream f(path,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
M9Signed::Digest sha(const uint8_t* p,size_t n){M9Signed::Sha256 h;M9Signed::Digest d;h.begin();h.add(p,n);h.end(d.data());return d;}
std::string hex(const char* p,size_t n){char out[65];M9Signed::DigestHash::hex(p,n,out);return out;}
const char* nonce="23456789abcdef0123456789abcdef01";
const char* opaque="cdef0123456789abcdef0123456789ab";
const char* token="abcdefabcdefabcdefabcdefabcdefab";
const uint32_t peer=0xc0a80402;
const M9Signed::Budget ample{60000,50000,0,4096};
std::string ha1=hex("shino:SHINO-OTA:INERT_PRIVATE_FIXTURE",sizeof("shino:SHINO-OTA:INERT_PRIVATE_FIXTURE")-1);
std::string header(bool arm,uint32_t length){
    const std::string path=arm?"/api/v1/bridge/ota/arm":"/api/v1/bridge/ota/upload";
    const auto ha2=hex(("POST:"+path).c_str(),5+path.size());
    const std::string proofInput=ha1+":"+nonce+":00000001:inertcnonce:auth:"+ha2;
    const auto response=hex(proofInput.c_str(),proofInput.size());
    return "POST "+path+" HTTP/1.1\r\nHost: 192.168.4.1\r\nOrigin: http://192.168.4.1\r\nContent-Type: "+
        (arm?"application/json":"application/octet-stream")+"\r\nContent-Length: "+std::to_string(length)+
        "\r\nAuthorization: Digest username=\"shino\", realm=\"SHINO-OTA\", nonce=\""+nonce+
        "\", opaque=\""+opaque+"\", uri=\""+path+"\", algorithm=SHA-256, qop=auth, nc=00000001, cnonce=\"inertcnonce\", response=\""+response+
        "\"\r\n"+(arm?"":std::string("X-Shino-Intent: ")+token+"\r\n")+"\r\n";
}
struct Trial {
    M9Signed::Release selected;
    M9Signed::NativeAdapter adapter;
    M9Signed::Transfer<M9Signed::Sha256,M9Signed::DigestHash,M9Signed::NativeAdapter> transfer;
    ShinoNativeOta::StrictOtaDigestGate<M9Signed::DigestHash> armAuth,uploadAuth;
    Trial(std::vector<uint8_t>& der,std::vector<uint8_t>& package)
      :selected{uint32_t(package.size()-260),sha(package.data(),package.size()-260),sha(package.data(),package.size()),sha(der.data(),der.size())},
       adapter(der.data(),der.size()),transfer(selected,399264,adapter){
        ESP=HostESP{};eboot_command_clear();++transactions;
        CHECK(armAuth.challenge(peer,ShinoNativeOta::RawOtaRequestKind::Arm,nonce,opaque,0));
        CHECK(uploadAuth.challenge(peer,ShinoNativeOta::RawOtaRequestKind::SignedTransport,nonce,opaque,0));
    }
    ~Trial(){adapter.core_._reset();} // simulated process reset, never end(false)
    bool arm(std::string h=header(true,16),uint32_t now=1,bool consent=true,M9Signed::Budget b=ample,
             const char* body="{\"confirm\":true}"){
        return transfer.arm(h.c_str(),h.size(),reinterpret_cast<const uint8_t*>(body),16,peer,true,consent,token,armAuth,"shino",ha1.c_str(),now,b);
    }
    bool begin(std::string h={},uint32_t now=2,uint32_t p=peer,bool ap=true,M9Signed::Budget b=ample){
        if(h.empty())h=header(false,selected.rawBytes+260);
        return transfer.begin(h.c_str(),h.size(),p,ap,uploadAuth,"shino",ha1.c_str(),now,b);
    }
    bool upload(std::vector<uint8_t>& p,uint32_t time=3){
        for(uint32_t at=0;at<p.size();at+=512)
            if(!transfer.add(p.data()+at,std::min(size_t(512),p.size()-at),at,time,ample))return false;
        return true;
    }
    void refused(){
        CHECK(transfer.phase()==M9Signed::Phase::Failed);
        CHECK(ESP.writeCalls==0);eboot_command cmd{};CHECK(eboot_command_read(&cmd)!=0);
    }
    void noBoot(){eboot_command cmd{};const bool dispatch=eboot_command_read(&cmd)==0 && cmd.action==ACTION_COPY_RAW;
        if(dispatch)++failedBootDispatches;CHECK(!dispatch);CHECK(eboot_command_read(&cmd)!=0);}
};
int main(int argc,char** argv){try{
    CHECK(argc==2);const std::string root=argv[1];auto n=read(root+"/modulus"),e=read(root+"/exponent"),der=read(root+"/public.der"),p=read(root+"/signed.inert");
    CHECK(p.size()>64000);const auto baseline=p;
    {Trial t(der,p);CHECK(t.arm());CHECK(t.begin());CHECK(t.upload(p));CHECK(t.transfer.finish(4,ample));
     CHECK(t.adapter.key_.getRSA()->nlen==n.size() && std::memcmp(t.adapter.key_.getRSA()->n,n.data(),n.size())==0);
     CHECK(!t.transfer.finish(5,ample));eboot_command cmd{};CHECK(eboot_command_read(&cmd)==0);
     CHECK(cmd.args[0]==0x200000-((p.size()+4095)&~4095u));CHECK(cmd.args[1]==0);CHECK(cmd.args[2]==p.size()-260);
     CHECK(t.adapter.core_._verify!=nullptr); // Core reset preserves verifier
     for(size_t i=0x200000;i<ESP.flash.size();++i)CHECK(ESP.flash[i]==0xff);
     m9_host_rtc[2]^=1;CHECK(eboot_command_read(&cmd)!=0); // actual command CRC blocks metadata bitflip
    }
    // Pre-body negatives cannot begin/write/schedule a copy.
    for(unsigned which=0;which<20;++which){Trial t(der,p);auto h=header(false,uint32_t(p.size()));
        CHECK(t.arm());bool result=false;
        if(which==0)result=t.begin(h,60001);
        if(which==1)result=t.begin(h,2,peer+1);
        if(which==2)result=t.begin(h,2,peer,false);
        if(which==3){h.insert(h.size()-2,"Host: 192.168.4.1\r\n");result=t.begin(h);}
        if(which==4){h.insert(h.size()-2,"Transfer-Encoding: chunked\r\n");result=t.begin(h);}
        if(which==5){h.replace(h.find("Host: 192.168.4.1"),19,"Host: attacker.invalid");result=t.begin(h);}
        if(which==6){h.replace(h.find("http://192.168.4.1"),18,"http://attacker.test");result=t.begin(h);}
        if(which==7){h.replace(h.find("Digest username"),6,"Basic ");result=t.begin(h);}
        if(which==8){h[h.find("response=\"")+10]^=1;result=t.begin(h);}
        if(which==9){h[h.find("X-Shino-Intent: ")+16]='0';result=t.begin(h);}
        if(which==10)result=t.begin(h,2,peer,true,{31543,50000,0,4096});
        if(which==11)result=t.begin(h,2,peer,true,{60000,22583,0,4096});
        if(which==12)result=t.begin(h,2,peer,true,{60000,50000,26,4096});
        if(which==13)result=t.begin(h,2,peer,true,{60000,50000,0,4095});
        if(which==14){h.replace(h.find("/api/v1/bridge/ota/upload"),23,"/api/v1/bridge/ota/wrong");result=t.begin(h);}
        if(which==15)result=t.begin(header(false,uint32_t(p.size()-1)));
        if(which==16){h.insert(h.size()-2,"Expect: 100-continue\r\n");result=t.begin(h);}
        if(which==17){auto start=h.find("Authorization:");h.replace(start,h.find("\r\n",start)-start,"Cookie: session=inert");result=t.begin(h);}
        if(which==18){h.replace(h.find("nc=00000001"),11,"nc=00000002");result=t.begin(h);}
        if(which==19){h.replace(h.find("SHINO-OTA"),9,"SHINO-StageA");result=t.begin(h);}
        CHECK(!result);t.refused();CHECK(!t.begin());
    }
    for(unsigned which=0;which<4;++which){Trial t(der,p);
        CHECK(!t.arm(header(true,16),1,which!=0,ample,which==1?"CHANGED_ARM_BODY!":"{\"confirm\":true}" ) || which>1);
        if(which<2)t.refused();else{CHECK(t.begin());t.transfer.disconnect();t.noBoot();}
    }
    {Trial t(der,p);CHECK(!t.arm(header(true,16),60000));t.refused();}
    // Stream failures, changed source/transport, duplicate/empty/overflow,
    // deadline/disconnect, staged corruption/read and write/erase faults.
    for(unsigned which=0;which<13;++which){p=baseline;Trial t(der,p);CHECK(t.arm());CHECK(t.begin());
        if(which==0)CHECK(!t.transfer.add(p.data(),0,0,3,ample));
        if(which==1)CHECK(!t.transfer.add(p.data(),513,0,3,ample));
        if(which==2){CHECK(t.transfer.add(p.data(),512,0,3,ample));CHECK(!t.transfer.add(p.data(),512,0,4,ample));}
        if(which==3)CHECK(!t.transfer.add(p.data(),512,0,60002,ample));
        if(which==4){p[5000]^=1;CHECK(t.upload(p));CHECK(!t.transfer.finish(4,ample));}
        if(which==5){p.back()^=1;CHECK(t.upload(p));CHECK(!t.transfer.finish(4,ample));}
        if(which==6){CHECK(t.transfer.add(p.data(),512,0,3,ample));CHECK(!t.transfer.finish(4,ample));}
        if(which==7){t.transfer.disconnect();CHECK(!t.upload(p));}
        if(which==8){CHECK(t.upload(p));ESP.flash[0x200000-((p.size()+4095)&~4095u)+5000]^=1;CHECK(!t.transfer.finish(4,ample));}
        if(which==9){CHECK(t.upload(p));ESP.failRead=true;CHECK(!t.transfer.finish(4,ample));}
        if(which==10){ESP.failWrite=true;CHECK(!t.upload(p));}
        if(which==11){ESP.failErase=true;CHECK(!t.upload(p));}
        if(which==12){CHECK(t.upload(p));CHECK(!t.transfer.add(p.data(),1,uint32_t(p.size()),4,ample));CHECK(!t.transfer.finish(4,ample));}
        t.noBoot();CHECK(!t.adapter.commit());
    }
    // Bad native signer: full selected transfer matches, only RSA rejects.
    {p=baseline;p[p.size()-260]^=1;Trial t(der,p);CHECK(t.arm());CHECK(t.begin());CHECK(t.upload(p));CHECK(!t.transfer.finish(4,ample));t.noBoot();}
    {p=baseline;auto wrong=der;auto at=std::search(wrong.begin(),wrong.end(),n.begin(),n.end());CHECK(at!=wrong.end());at[80]^=1;Trial t(wrong,p);CHECK(t.arm());CHECK(t.begin());CHECK(t.upload(p));CHECK(!t.transfer.finish(4,ample));t.noBoot();}
    // Replay, duplicate arm/begin, bad geometry/trust and runtime header gates.
    for(unsigned which=0;which<10;++which){p=baseline;Trial t(der,p);
        if(which==0){CHECK(t.arm());CHECK(!t.arm());t.noBoot();}
        if(which==1){CHECK(t.arm());CHECK(t.begin());CHECK(!t.begin());t.noBoot();}
        if(which==2){CHECK(t.arm());CHECK(t.begin());CHECK(t.upload(p));CHECK(t.transfer.finish(4,ample));
            CHECK(!t.begin());CHECK(!t.arm());CHECK(!t.transfer.add(p.data(),512,0,5,ample));CHECK(!t.transfer.finish(5,ample));}
        if(which==3){der[0]^=1;CHECK(t.arm());CHECK(!t.begin());t.noBoot();der[0]^=1;}
        if(which==4){ESP.mode=0;CHECK(t.arm());CHECK(!t.begin());t.noBoot();}
        if(which==5){ESP.current=1044464;CHECK(t.arm());CHECK(!t.begin());t.noBoot();}
        if(which>=6){CHECK(t.arm());CHECK(t.begin());p[which-6]^=1;CHECK(!t.transfer.add(p.data(),512,0,3,ample));t.noBoot();}
    }
    // Simulated reset at every512-byte boundary, including a fully staged body:
    // no end call means no new RTC command. No real flash or power cut.
    p=baseline;
    for(uint32_t cut=0;cut<=p.size();cut=std::min(uint32_t(p.size()),cut+512)){
        Trial t(der,p);CHECK(t.arm());CHECK(t.begin());
        for(uint32_t at=0;at<cut;at+=512){auto amount=std::min(size_t(512),size_t(cut-at));CHECK(t.transfer.add(p.data()+at,amount,at,3,ample));}
        t.transfer.disconnect();t.noBoot();CHECK(!t.transfer.finish(4,ample));
        if(cut==p.size())break;
    }
    // Demonstrate the documented Core signing/MD5 mutual exclusion.
    {Trial t(der,p);CHECK(t.arm());CHECK(t.begin());CHECK(t.adapter.core_.setMD5("00000000000000000000000000000000"));
     CHECK(t.upload(p));CHECK(t.transfer.finish(4,ample));}
    // Residual: a valid committed RTC command does NOT authenticate staging
    // again at boot. This is a demonstrated integration HOLD, not a fake fix.
    bool postcommitUnprotected=false;
    {Trial t(der,p);CHECK(t.arm());CHECK(t.begin());CHECK(t.upload(p));CHECK(t.transfer.finish(4,ample));
     eboot_command cmd{};CHECK(eboot_command_read(&cmd)==0);ESP.flash[cmd.args[0]+5000]^=1;
     CHECK(eboot_command_read(&cmd)==0);postcommitUnprotected=true;
     // Interrupted RTC writes from a CLEARED command are rejected until all
     // 32 words are present. This does not prove arbitrary stale RTC safety.
     uint32_t saved[32];for(size_t i=0;i<32;++i)saved[i]=m9_host_rtc[i];
     for(size_t cut=0;cut<32;++cut){for(auto& word:m9_host_rtc)word=0;
         for(size_t i=0;i<cut;++i)m9_host_rtc[i]=saved[i];CHECK(eboot_command_read(&cmd)!=0);}
     for(size_t i=0;i<32;++i)m9_host_rtc[i]=saved[i];CHECK(eboot_command_read(&cmd)==0);}
    std::cout<<"{\"checks\":"<<checks<<",\"transactions\":"<<transactions
             <<",\"precommit_failures_boot_dispatches\":"<<failedBootDispatches<<",\"rtc_interrupted_boundaries\":32,\"reset_boundaries\":"<<(baseline.size()+511)/512+1
             <<",\"postcommit_staging_authentication\":false,\"postcommit_hold_demonstrated\":"<<(postcommitUnprotected?"true":"false")
             <<",\"device_contacts\":0,\"device_writes\":0}"<<std::endl;
}catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}}
