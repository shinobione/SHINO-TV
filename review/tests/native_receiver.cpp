// HOST/native contract, exact pinned SHA256; no socket/device/credentials.
#include "B54LanWeather.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include <iostream>
#include <sstream>
using namespace B54LanWeather;
static bool key(uint8_t* out){for(unsigned i=0;i<32;++i)out[i]=uint8_t(i);return true;}
static bool rfcKey(uint8_t* out){memset(out,0,32);memset(out,0x0b,20);return true;}
static unsigned nibble(char c){return c>='0'&&c<='9'?unsigned(c-'0'):unsigned(c-'a'+10);}
static std::vector<uint8_t> bytes(const char* text){
 size_t n=strlen(text);assert(n%2==0);std::vector<uint8_t> out(n/2);
 for(size_t i=0;i<n;i+=2)out[i/2]=uint8_t(nibble(text[i])*16+nibble(text[i+1]));return out;
}
static void setup(Receiver& r){
 const uint8_t device[]={1,2,3,4,5,6,7,8},boot[]={0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x80};
 r.configure(device,boot,reinterpret_cast<const uint8_t*>("DEMO0001"));
}
#include "vectors.inc"
static std::string hex(const uint8_t* p,size_t n){
 static const char alphabet[]="0123456789abcdef";std::string s;for(size_t i=0;i<n;++i){s+=alphabet[p[i]>>4];s+=alphabet[p[i]&15];}return s;
}
int main(int argc,char**){
 if(argc>1){
  Receiver receiver;setup(receiver);std::string line;
  while(std::getline(std::cin,line)){
   std::istringstream in(line);std::string command,wire;uint32_t utc=0,now=0;unsigned trust=1;
   in>>command;
   if(command=="STATUS"){
    in>>wire>>utc>>now;auto challenge=bytes(wire.c_str());assert(challenge.size()==8);
    receiver.poll(utc,utc!=0,now);assert(receiver.status(2,challenge.data(),utc,key));
    std::cout<<hex(receiver.workspace().wire,80)<<std::endl;
   }else if(command=="SAMPLE"){
    in>>wire>>utc>>trust>>now;auto data=bytes(wire.c_str());
    const auto result=receiver.receive(data.data(),data.size(),utc,trust!=0,now,key);
    std::cout<<unsigned(result)<<" ";
    if(result==Result::Accepted){uint8_t nonce[8];memcpy(nonce,data.data()+48,8);
     assert(receiver.status(3,nonce,utc,key));std::cout<<hex(receiver.workspace().wire,80);}
    else std::cout<<"-";
    std::cout<<std::endl;receiver.clearWorkspace();
   }else if(command=="POLL"){
    in>>utc>>trust>>now;receiver.poll(utc,trust!=0,now);
    std::cout<<receiver.state().sequence<<" "<<receiver.state().fresh<<" "<<receiver.state().tenths<<std::endl;
   }else if(command=="RESET"){
    in>>wire;auto boot=bytes(wire.c_str());assert(boot.size()==8);
    const uint8_t device[]={1,2,3,4,5,6,7,8};receiver.configure(device,boot.data(),reinterpret_cast<const uint8_t*>("DEMO0001"));std::cout<<"RESET"<<std::endl;
   }else if(command=="MAC"){
    in>>wire;auto data=bytes(wire.c_str());assert(hmac(receiver.workspace(),key,nullptr,0,data.data(),data.size()));
    std::cout<<hex(receiver.workspace().digest,32)<<std::endl;receiver.clearWorkspace();
   }else return 2;
  }
  return 0;
 }
 Receiver r;setup(r);auto frame=bytes(FrozenSample);
 Workspace rfc{};assert(hmac(rfc,rfcKey,nullptr,0,reinterpret_cast<const uint8_t*>("Hi There"),8));
 assert(hex(rfc.digest,32)=="b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7");
 assert(r.receive(frame.data(),frame.size(),1791955392,true,1000,key)==Result::Accepted);
 assert(r.state().tenths==182&&r.state().wmo==3&&r.state().sequence==1);
 const State prior=r.state();
 assert(r.receive(frame.data(),80,1791955392,true,1001,key)==Result::Replay);
 assert(memcmp(&prior,&r.state(),sizeof prior)==0);
 for(unsigned at=0;at<80;++at){Receiver bad;setup(bad);const State previous=bad.state();auto corrupt=frame;corrupt[at]^=1;
  assert(bad.receive(corrupt.data(),80,1791955392,true,1,key)!=Result::Accepted);
  assert(memcmp(&previous,&bad.state(),sizeof previous)==0);}
 for(size_t n=0;n<80;++n){Receiver cut;setup(cut);assert(cut.receive(frame.data(),n,1791955392,true,0,key)==Result::Framing);}
 r.poll(1791955392,false,1002);assert(!r.state().fresh);
 r.poll(1791955392,true,1003);assert(!r.state().fresh); // Trust loss cannot revive.
 std::printf("B54_LAN_NATIVE_HOST_PASS corrupt_bytes=80 truncations=80 replay/no-mutation/clock-trust sizeof(State)=%zu sizeof(Workspace)=%zu\n",sizeof(State),sizeof(Workspace));
}
