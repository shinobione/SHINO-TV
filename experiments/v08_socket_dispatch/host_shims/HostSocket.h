#pragma once
#include <Arduino.h>
#include <chrono>
#include <thread>
#include <memory>
#include <deque>
#include <stdexcept>
#include <atomic>
#ifdef _WIN32
#define NOMINMAX
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <bcrypt.h>
using Socket=SOCKET;
inline void closeSocket(Socket s){closesocket(s);}
#else
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <netinet/in.h>
#include <unistd.h>
#include <openssl/evp.h>
using Socket=int;
constexpr Socket INVALID_SOCKET=-1;
inline void closeSocket(Socket s){close(s);}
#define SD_SEND SHUT_WR
#define SD_BOTH SHUT_RDWR
#endif
inline std::atomic<size_t> allocs{0},frees{0},bytesRead{0},bytesWritten{0},contexts{0},destroyed{0},stops{0};
inline std::atomic<size_t> liveSockets{0},peakSockets{0},accepted{0};
inline std::atomic<uint64_t> maxContextLifetimeUs{0};
inline std::chrono::steady_clock::time_point lab_poll_origin;
inline bool lab_poll_active=false;
inline double lab_first_write_us=-1;
inline void trackSocket(){auto n=++liveSockets;peakSockets=std::max(peakSockets.load(),n);}
struct IPAddress {uint32_t value=1;bool operator!=(const IPAddress& p)const{return value!=p.value;}};
struct Context {
 Socket fd=INVALID_SOCKET;
 std::chrono::steady_clock::time_point born=std::chrono::steady_clock::now();
 explicit Context(Socket f):fd(f){contexts++;trackSocket();}
 ~Context(){if(fd!=INVALID_SOCKET){closeSocket(fd);liveSockets--;}maxContextLifetimeUs=std::max(maxContextLifetimeUs.load(),uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-born).count()));destroyed++;}
};
struct Stream {
 virtual ~Stream()=default;
 virtual int read(){return -1;}
 virtual int timedRead(){return read();}
 virtual ssize_t streamRemaining(){return 0;}
 virtual size_t write(const uint8_t*,size_t){return 0;}
 String readStringUntil(char terminator); // exact pinned Stream method
 template<class T>size_t sendSize(T* dest,size_t n){size_t done=0;uint8_t buf[2048];while(done<n){size_t count=0;while(count<std::min(n-done,sizeof buf)){int c=read();if(c<0)break;buf[count++]=uint8_t(c);}if(!count)break;done+=dest->write(buf,count);}return done;}
 template<class T>size_t sendAll(T* dest){return sendSize(dest,size_t(streamRemaining()));}
};
struct S2Stream {String& s;explicit S2Stream(String& v):s(v){}size_t write(const uint8_t* p,size_t n){return s.write(p,n);}};
struct StreamConstPtr:Stream {
 const char* p;size_t n,at=0;
 explicit StreamConstPtr(const String& s):p(s.c_str()),n(s.size()){}
 StreamConstPtr(const char* s,size_t len):p(s),n(len){}
 int read()override{return at<n?uint8_t(p[at++]):-1;}
 ssize_t streamRemaining()override{return ssize_t(n-at);}
};
struct WiFiClient:Stream {
 std::shared_ptr<Context> ctx;int timeout=5000;
 WiFiClient()=default;explicit WiFiClient(Socket s):ctx(std::make_shared<Context>(s)){}
 explicit operator bool()const{return ctx && ctx->fd!=INVALID_SOCKET;}
 int available()const{if(!*this)return 0;
#ifdef _WIN32
 u_long n=0;ioctlsocket(ctx->fd,FIONREAD,&n);
#else
 int n=0;ioctl(ctx->fd,FIONREAD,&n);
#endif
 return int(n);}
 bool readable(int ms=0)const{if(!*this)return false;fd_set f;FD_ZERO(&f);FD_SET(ctx->fd,&f);timeval t{ms/1000,(ms%1000)*1000};return select(int(ctx->fd)+1,&f,nullptr,nullptr,&t)>0;}
 bool connected()const{if(!*this)return false;if(!readable())return true;char c;return recv(ctx->fd,&c,1,MSG_PEEK)>0;}
 int read()override{if(!readable())return -1;unsigned char c;int n=recv(ctx->fd,reinterpret_cast<char*>(&c),1,0);if(n==1){bytesRead++;return c;}return -1;}
 int timedRead()override{if(!readable(timeout))return -1;return read();}
 size_t sendSize(S2Stream& d,size_t n,int ms){auto start=std::chrono::steady_clock::now();size_t done=0;uint8_t buf[2048];while(done<n){if(!readable(std::min(ms,10))){if(std::chrono::steady_clock::now()-start>=std::chrono::milliseconds(ms))break;continue;}int count=recv(ctx->fd,reinterpret_cast<char*>(buf),int(std::min(n-done,sizeof buf)),0);if(count<=0)break;bytesRead+=count;d.write(buf,size_t(count));done+=count;}return done;}
 size_t write(const uint8_t* p,size_t n)override{if(!*this)return 0;if(lab_poll_active && lab_first_write_us<0)lab_first_write_us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-lab_poll_origin).count();size_t done=0;while(done<n){
#ifdef _WIN32
 int count=send(ctx->fd,reinterpret_cast<const char*>(p+done),int(n-done),0);
#else
 int count=send(ctx->fd,p+done,n-done,MSG_NOSIGNAL);
#endif
 if(count<=0)break;done+=count;bytesWritten+=count;}return done;}
 void setTimeout(int ms){timeout=ms;}
 void flush(){} // Explicit seam: no SDK/lwIP output-drain implementation.
 void stop(){stops++;if(*this){shutdown(ctx->fd,SD_BOTH);closeSocket(ctx->fd);ctx->fd=INVALID_SOCKET;liveSockets--;}}
 IPAddress remoteIP()const{return {};}
 template<class... T>int printf(const char* f,T... a){char b[128];int n=snprintf(b,sizeof b,f,a...);return int(write(reinterpret_cast<uint8_t*>(b),size_t(n)));}
 int printf_P(const char* f){return printf("%s",f);}
};
struct WiFiServer {
 using ClientType=WiFiClient;
 Socket listener=INVALID_SOCKET;uint16_t port=0;std::deque<WiFiClient> pending;
 explicit WiFiServer(int){} WiFiServer(IPAddress,int){}
 void begin(){listener=socket(AF_INET,SOCK_STREAM,0);if(listener==INVALID_SOCKET)throw std::runtime_error("socket");trackSocket();sockaddr_in a{};a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);a.sin_port=0;if(bind(listener,reinterpret_cast<sockaddr*>(&a),sizeof a)||listen(listener,8))throw std::runtime_error("loopback bind/listen");
#ifdef _WIN32
 int len=sizeof a;
#else
 socklen_t len=sizeof a;
#endif
 getsockname(listener,reinterpret_cast<sockaddr*>(&a),&len);port=ntohs(a.sin_port);}
 void begin(uint16_t){begin();}
 void harvest(){if(listener==INVALID_SOCKET)return;for(int i=0;i<8;i++){fd_set f;FD_ZERO(&f);FD_SET(listener,&f);timeval t{};if(select(int(listener)+1,&f,nullptr,nullptr,&t)<=0)break;Socket s=::accept(listener,nullptr,nullptr);if(s!=INVALID_SOCKET){pending.emplace_back(s);accepted++;}}}
 WiFiClient accept(){harvest();if(pending.empty())return {};auto c=pending.front();pending.pop_front();return c;}
 bool hasClient(){harvest();return !pending.empty();}
 bool hasClientData(){harvest();for(auto& c:pending)if(c.available())return true;return false;}
 bool hasMaxPendingClients(){harvest();return pending.size()>=5;}// declared host queue policy, not SDK evidence
 void close(){pending.clear();if(listener!=INVALID_SOCKET){closeSocket(listener);listener=INVALID_SOCKET;liveSockets--;}}
 ~WiFiServer(){close();}
};
class MD5Builder {
 String input,result;
public:
 void begin(){input.clear();result.clear();}void add(const String& s){input+=s;}
 void calculate(){unsigned char digest[16];
#ifdef _WIN32
 BCRYPT_ALG_HANDLE alg;BCRYPT_HASH_HANDLE hash;DWORD len=0,got=0;
 if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_MD5_ALGORITHM,nullptr,0)<0)throw std::runtime_error("BCrypt MD5");
 BCryptGetProperty(alg,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&len),sizeof len,&got,0);std::vector<unsigned char> obj(len);
 if(BCryptCreateHash(alg,&hash,obj.data(),len,nullptr,0,0)<0)throw std::runtime_error("BCrypt hash");
 BCryptHashData(hash,reinterpret_cast<PUCHAR>(input.data()),ULONG(input.size()),0);BCryptFinishHash(hash,digest,16,0);BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(alg,0);
#else
 unsigned len=0;EVP_Digest(input.data(),input.size(),digest,&len,EVP_md5(),nullptr);
#endif
 char b[33];for(int i=0;i<16;i++)snprintf(b+i*2,3,"%02x",digest[i]);result=b;}
 String toString(){return result;}
};
namespace base64 {inline String encode(const String& s,bool){static const char t[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";String out;unsigned bits=0;int n=0;for(unsigned char c:s){bits=(bits<<8)|c;n+=8;while(n>=6){n-=6;out+=t[(bits>>n)&63];}}if(n)out+=t[(bits<<(6-n))&63];while(out.size()%4)out+='=';return out;}}
