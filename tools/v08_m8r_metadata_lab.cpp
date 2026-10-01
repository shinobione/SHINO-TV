// Real pinned ArduinoJson, explicit 32-bit ABI and exact target arena cap.
#include <MediaReceiver.h>
#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
static size_t arrayBytes=0,arrayPeak=0,arrayCount=0,arrayPeakCount=0;
static bool denyImage=false;
struct alignas(max_align_t) ArrayHeader { size_t size; };
void *operator new[](size_t n) {
  if (denyImage && n==4608) throw std::bad_alloc();
  auto *h=static_cast<ArrayHeader*>(std::malloc(sizeof(ArrayHeader)+n));
  if(!h)throw std::bad_alloc();h->size=n;arrayBytes+=n;++arrayCount;
  if(arrayBytes>arrayPeak)arrayPeak=arrayBytes;if(arrayCount>arrayPeakCount)arrayPeakCount=arrayCount;
  return h+1;
}
void operator delete[](void *p) noexcept {if(p){auto*h=static_cast<ArrayHeader*>(p)-1;arrayBytes-=h->size;--arrayCount;std::free(h);}}
void operator delete[](void *p,size_t) noexcept {operator delete[](p);}
static_assert(sizeof(void*) == 4, "Dedicated ESP-sized host profile needs 32-bit pointers");
static_assert(m7::JsonArena::capacity == SHINO_M8_METADATA_ARENA_BYTES);
static_assert(ARDUINOJSON_POOL_CAPACITY == 128 && ARDUINOJSON_SLOT_ID_SIZE == 2);
static std::vector<uint8_t> unhex(const std::string &s) {
  std::vector<uint8_t> b(s.size()/2);
  if (!m7::unhex(s.c_str(),b.data(),b.size())) throw std::runtime_error("hex");
  return b;
}
int main() {
  std::cerr<<"layout "<<sizeof(void*)<<' '<<alignof(max_align_t)<<' '<<ArduinoJson::detail::ResourceManager::slotSize<<' '<<offsetof(ArduinoJson::detail::StringNode,data)<<'\n';
#ifndef M8R_BASELINE_PROFILE
  {
    m7::JsonArena a;
    auto *first=static_cast<uint8_t*>(a.allocate(16));
    memset(first,0xa5,16);
    auto *second=static_cast<uint8_t*>(a.allocate(16));
    a.deallocate(first); // Older live blocks must not move or become reusable.
    if(a.reallocate(second,32)!=second || a.reallocate(second,8)!=second)
      throw std::runtime_error("latest resize");
    a.deallocate(second);
    if(a.allocate(16)!=second)throw std::runtime_error("latest reuse");
    auto *moved=static_cast<uint8_t*>(a.reallocate(first,32));
    if(moved==first || memcmp(first,moved,16))throw std::runtime_error("older copy");
    if(a.reallocate(moved,SIZE_MAX)!=nullptr || memcmp(first,moved,16))
      throw std::runtime_error("overflow preserved data");
    if(a.reallocate(first,8)!=first)throw std::runtime_error("older shrink");
  }
  if(arrayBytes || arrayCount)throw std::runtime_error("allocator unit cleanup");
#endif
  std::string txhex,hex;std::cin>>txhex;
  auto tx=unhex(txhex);uint64_t epoch=m7::be64(tx.data());
  std::vector<uint8_t> valid48;
  while(std::cin>>hex) {
    auto b=unhex(hex);m7::Record r; m7::Metadata m;
    // Build the same bounded wire envelope before metadata parsing.
    std::vector<uint8_t> body(40+b.size());memcpy(body.data(),"STV7",4);
    body[4]=2;body[5]=1;memcpy(body.data()+8,tx.data(),8);memcpy(body.data()+16,tx.data(),16);
    body[34]=uint8_t(b.size()>>8);body[35]=uint8_t(b.size());
    uint32_t crc=m7::crc(b.data(),b.size());for(int j=0;j<4;++j)body[36+j]=uint8_t(crc>>(24-8*j));
    memcpy(body.data()+40,b.data(),b.size());m7::JsonArena::lastUsage=0;m7::JsonArena::lastDenied=false;
    bool ok=m7::wire(body.data(),body.size(),1,tx.data(),epoch,r)&&m7::metadata(r,m);
    if(ok && m.cover==4608 && valid48.empty()) valid48=b;
    std::cout<<ok<<' '<<m7::JsonArena::lastUsage<<' '<<m7::JsonArena::lastDenied<<'\n';
  }
  if(m7::JsonArena::capacity<2048) return 0;
  if(valid48.empty())throw std::runtime_error("no retained 48 metadata");
  m7::Receiver receiver; m7::Record r;r.op=1;r.epoch=epoch;memcpy(r.tx,tx.data(),16);r.payload=valid48.data();r.length=uint16_t(valid48.size());
  if(!receiver.receive(r,0,0))throw std::runtime_error("Begin");
  std::vector<uint8_t> tile(512,0xa5);r.op=2;r.payload=tile.data();r.length=512;
  for(int n=0;n<9;++n){r.index=uint16_t(n);if(!receiver.receive(r,0,1))throw std::runtime_error("Tile");}
  r.op=3;r.index=0;r.length=0;if(!receiver.receive(r,0,2))throw std::runtime_error("Commit");
  auto *old=receiver.sink.image.get();auto metadata=std::string(receiver.sink.metadata);auto high=receiver.highest;
  // Newer transaction for replacement, without changing metadata validation.
  auto replacement=valid48;std::string raw(replacement.begin(),replacement.end());
  std::string next=txhex;next.back()='2';auto pos=raw.find(txhex);raw.replace(pos,txhex.size(),next);replacement.assign(raw.begin(),raw.end());
  auto tx2=unhex(next);r.op=1;memcpy(r.tx,tx2.data(),16);r.payload=replacement.data();r.length=uint16_t(replacement.size());
  arrayPeak=arrayBytes;arrayPeakCount=arrayCount;
  auto invalid=replacement;invalid[0]='[';r.payload=invalid.data();
  if(receiver.receive(r,0,3) || receiver.sink.image.get()!=old || receiver.highest!=high || receiver.pending || metadata!=receiver.sink.metadata)
    throw std::runtime_error("invalid Begin lost old image");
  r.payload=replacement.data();
  m7::JsonArena::denyBackingAllocation=true;
  bool failure=!receiver.receive(r,0,3);m7::JsonArena::denyBackingAllocation=false;
  if(!failure || receiver.sink.image.get()!=old || receiver.highest!=high || receiver.pending || metadata!=receiver.sink.metadata)throw std::runtime_error("failed Begin lost old image");
  // Actual allocation failure after validated Begin follows existing terminal semantics.
  denyImage=true;failure=!receiver.receive(r,0,4);denyImage=false;
  if(!failure || receiver.pending || receiver.sink.image || receiver.stagedBytes() || strcmp(receiver.outcome,"ALLOCATION_FAILED"))throw std::runtime_error("image failure cleanup");
  if(arrayBytes || arrayCount)throw std::runtime_error("array leak");
  std::cerr<<"lifetime "<<arrayPeak<<' '<<arrayPeakCount<<" 0 0\n";
}
