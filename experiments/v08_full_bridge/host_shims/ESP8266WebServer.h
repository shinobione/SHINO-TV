#pragma once
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <functional>
#include <map>
enum { HTTP_GET=1, HTTP_POST=2, DIGEST_AUTH=1 };
struct ClientFixture { IPAddress peer; IPAddress remoteIP(){return peer;} };
class ESP8266WebServer {
public:
  using Callback=std::function<void()>;
  struct Route { Callback handler,upload; };
  std::map<std::pair<std::string,int>,Route> routes;
  std::map<std::string,String> headers,outHeaders;
  Callback fallback; ClientFixture clientFixture;
  bool authorized=false,started=false; int code=0,challenges=0,authCalls=0,loops=0;
  String plain,body;
  explicit ESP8266WebServer(int){}
  String header(const char* name){return headers[name];}
  String arg(const char*){return plain;}
  ClientFixture& client(){return clientFixture;}
  bool authenticate(const char*,const char*){authCalls++;return authorized;}
  void requestAuthentication(int,const char*){challenges++;code=401;}
  void sendHeader(const char* key,const String& value){outHeaders[key]=value;}
  void send(int c,const char*,const String& value){code=c;body=value;}
  void send_P(int c,const char*,const char* value){code=c;body=value;}
  void collectHeaders(const char*){}
  void on(const char* path,int method,Callback handler,Callback upload={}){routes[{path,method}]={handler,upload};}
  void onNotFound(Callback cb){fallback=cb;}
  void begin(){started=true;}
  void handleClient(){loops++;}
  void dispatch(const char* path,int method){code=0;body.clear();outHeaders.clear();auto it=routes.find({path,method});if(it==routes.end())fallback();else it->second.handler();}
};
