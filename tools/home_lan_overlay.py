"""P1-only bounded pre-body policy over retained Mission 8R/Mission 6A owner.

Never edits installed Core. Does not change the legacy OEM multipart parser.
"""
import hashlib, shutil
from pathlib import Path
import v08_m8r_overlay as base
from v07_pinned_core_probe import core_root, pinned_sources
ROOT=Path(__file__).resolve().parents[1]

def patch_header(value):
    value=base.patch_header(value)
    value=value.replace('  void handleClient();','''  void handleClient();
  void setHomeLanPrebody(std::function<bool()> fn) { _homeLanPrebody=fn; }''',1)
    value=value.replace('  bool _m7Active = false;','''  bool _m7Active = false;
  std::function<bool()> _homeLanPrebody;
  char _homeLanMediaHost[16] = {};''',1)
    return '#include "boot/HomeLanPolicy.h"\n'+value

def patch_impl(value):
    value=base.patch_impl(value)
    marker='        if (firstLine == V08_LINE_MEDIA && _m7Media) {'
    replacement=marker+'''
          const IPAddress local=_currentClient.localIP(),peer=_currentClient.remoteIP();
          const IPAddress mask=local==WiFi.softAPIP()?IPAddress(255,255,255,0):WiFi.subnetMask();
          auto order=[](const IPAddress& a)->uint32_t { return uint32_t(a[0])<<24|uint32_t(a[1])<<16|uint32_t(a[2])<<8|a[3]; };
          if(!HomeLan::peerOnSubnet(order(peer),order(local),order(mask)) ||
             (local!=WiFi.softAPIP() && local!=WiFi.localIP())) { _v08CloseOnce(); break; }
          const String authority=local.toString();
          memcpy(_homeLanMediaHost,authority.c_str(),authority.length()+1);
          _m7Media->setExpectedHost(_homeLanMediaHost);'''
    assert value.count(marker)==1
    return value.replace(marker,replacement)

def patch_parser(value):
    value=base.legacy.previous.patch_parser(value)
    value=value.replace('  String formData;','  unsigned homeLanSeen=0;\n  String formData;',1)
    # Header line bounded before String grows; strict CRLF, aggregate and time.
    value=value.replace('  String req = prefetchedFirstLine;','  String req = prefetchedFirstLine;\n  _hostHeader.clear();',1)
    marker="      req = client.readStringUntil('\\r');\n      client.readStringUntil('\\n');"
    replacement='''      req.clear();
      bool complete=false;
      while(uint32_t(millis()-_v08Started)<2000 && req.length()<=512) {
        if(!client.available()) { if(!client.connected()) return CLIENT_MUST_STOP; yield(); continue; }
        const int c=client.read();
        if(c=='\\r') {
          while(!client.available() && client.connected() && uint32_t(millis()-_v08Started)<2000) yield();
          if(!client.available() || client.read()!='\\n') return CLIENT_MUST_STOP;
          complete=true; break;
        }
        if(c<32 || c>126) return CLIENT_MUST_STOP;
        req+=char(c);
      }
      if(!complete || req.length()>512) return CLIENT_MUST_STOP;
      homeLanHeaderBytes+=req.length()+2;
      if(homeLanHeaderBytes>2048 || ++homeLanHeaderCount>32) return CLIENT_MUST_STOP;'''
    assert value.count(marker)==2
    value=value.replace('  unsigned homeLanSeen=0;','  unsigned homeLanSeen=0,homeLanHeaderBytes=0,homeLanHeaderCount=0;')
    value=value.replace(marker,replacement)
    value=value.replace('      headerValue.trim();','      headerValue.trim();\n      if(!homeLanUnique(headerName,homeLanSeen)) return CLIENT_MUST_STOP;',1)
    value=value.replace('      headerValue = req.substring(headerDiv + 2);','      headerValue = req.substring(headerDiv + 1);\n      headerValue.trim();\n      if(!homeLanUnique(headerName,homeLanSeen)) return CLIENT_MUST_STOP;',1)
    value=value.replace('    String plainBuf;','''    if(_homeLanPrebody && !_homeLanPrebody()) return CLIENT_REQUEST_IS_HANDLED;
    if(_currentUri.startsWith("/api/v1/bridge/wifi") && searchStr.length()) return CLIENT_MUST_STOP;
    String plainBuf;''',1)
    value=value.replace('readBytesWithTimeout<ServerType>(client, contentLength, plainBuf, HTTP_MAX_POST_WAIT)',
        '''readBytesWithTimeout<ServerType>(client, contentLength, plainBuf,
               (_currentUri=="/api/v1/bridge/wifi" || _currentUri=="/api/v1/bridge/metrics")
                   ? (uint32_t(millis()-_v08Started)<2000 ? int(2000-uint32_t(millis()-_v08Started)) : 0)
                   : HTTP_MAX_POST_WAIT)''',1)
    value=value.replace('    if (isEncoded) {','''    if((_currentUri=="/api/v1/bridge/wifi" || _currentUri=="/api/v1/bridge/metrics") &&
       uint32_t(millis()-_v08Started)>=2000) {
      if(_currentUri=="/api/v1/bridge/wifi") {
        volatile char* secret=const_cast<char*>(plainBuf.c_str());
        for(size_t i=0;i<plainBuf.length();++i) secret[i]=0;
      }
      return CLIENT_MUST_STOP;
    }
    if (isEncoded) {''',1)
    value=value.replace('    _parseArguments(searchStr);\n  }','    if(_homeLanPrebody && !_homeLanPrebody()) return CLIENT_REQUEST_IS_HANDLED;\n    _parseArguments(searchStr);\n  }',1)
    value=value.replace('        arg.value = plainBuf;','''        arg.value = plainBuf;
        if(_currentUri=="/api/v1/bridge/wifi") {
          volatile char* secret=const_cast<char*>(plainBuf.c_str());
          for(size_t i=0;i<plainBuf.length();++i) secret[i]=0;
        }''',1)
    value='''inline bool homeLanUnique(const String& name,unsigned& seen) {
  const char* keys[]={"Host","Origin","Authorization","Content-Length","Content-Type","Transfer-Encoding","X-Shino-Wifi-Intent","Cookie"};
  for(unsigned i=0;i<8;++i) if(name.equalsIgnoreCase(keys[i])) {
    if(seen&(1u<<i)) return false;
    seen|=1u<<i;
  }
  return true;
}
'''+value
    return value

def materialize(destination):
    pinned_sources(); source=core_root()/base.legacy.previous.LIB
    destination=Path(destination).resolve()
    if destination==source.resolve() or source.resolve() in destination.parents: raise ValueError('REFUSE_PACKAGE_WRITE')
    shutil.copytree(source,destination,dirs_exist_ok=True)
    hashes={}
    for name,fn in {'ESP8266WebServer.h':patch_header,'ESP8266WebServer-impl.h':patch_impl,'Parsing-impl.h':patch_parser}.items():
        text=fn((source/name).read_text(encoding='utf-8'))
        (destination/name).write_text(text,encoding='utf-8',newline='\n')
        hashes[name]=hashlib.sha256(text.encode()).hexdigest()
    return hashes
