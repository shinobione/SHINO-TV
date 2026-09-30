"""Partial R7 research overlay. No production/package writes or admission hook.

Body-before-application-auth remains BLOCKED BY ARCHITECTURE. Multipart is
closed before callbacks, not represented as a compatible upload repair.
"""
from pathlib import Path
import hashlib
import v08_m6a_overlay as prior
from v08_native_overlay import once

OUTPUT = prior.previous.ROOT / 'experiments/v08_m6c/.pio/pinned_overlay'

FIELDS = r'''
  bool _r7Line(ClientType&, String&, size_t&);
  bool _r7Body(ClientType&, uint32_t, String&);
  String _r7Target;
  String _r7Method;
  uint32_t _r7LastNc = 0;
  uint16_t _r7Work = 0;
'''

READERS = r'''
template <typename ServerType>
bool ESP8266WebServerTemplate<ServerType>::_r7Line(ClientType& c, String& line, size_t& budget) {
  line.clear();
  bool cr = false;
  while (uint32_t(millis() - _v08Started) < 2000u) {
    if (!_r7Work) return false;
    --_r7Work;
    if (!c.available()) {
      if (!c.connected()) return false;
      if ((_server.hasClientData() || _server.hasMaxPendingClients()) &&
          uint32_t(millis() - _statusChange) > HTTP_MAX_DATA_AVAILABLE_WAIT) return false;
      yield();
      continue;
    }
    if (!budget) return false;
    const int b = c.read();
    if (b < 0) return false;
    --budget;
    if (cr) return b == '\n';
    if (b == '\r') { cr = true; continue; }
    if (b < 0x20 || b > 0x7e || line.length() >= 512u) return false;
    line += char(b);
  }
  return false;
}

template <typename ServerType>
bool ESP8266WebServerTemplate<ServerType>::_r7Body(ClientType& c, uint32_t n, String& out) {
  if (n > 4096u) return false;
  while (out.length() < n) {
    if (!_r7Work) return false;
    --_r7Work;
    if (uint32_t(millis() - _v08Started) >= 2000u) return false;
    if (!c.available()) {
      if (!c.connected()) return false;
      if ((_server.hasClientData() || _server.hasMaxPendingClients()) &&
          uint32_t(millis() - _statusChange) > HTTP_MAX_DATA_AVAILABLE_WAIT) return false;
      yield();
      continue;
    }
    int b = c.read();
    if (b < 0) return false;
    const size_t before = out.length();
    out += char(b);
    if (out.length() != before + 1u) return false;
  }
  return uint32_t(millis() - _v08Started) < 2000u;
}
'''

DIGEST = r'''
template <typename ServerType>
bool ESP8266WebServerTemplate<ServerType>::authenticateDigest(const String& username, const String& H1) {
  String raw = header(FPSTR(AUTHORIZATION_HEADER));
  if (!raw.substring(0, 7).equalsIgnoreCase("Digest ")) return false;
  String keys[12], values[12];
  int count = 0, at = 7;
  while (at < int(raw.length())) {
    while (at < int(raw.length()) && raw[at] == ' ') ++at;
    int start = at;
    while (at < int(raw.length()) && ((raw[at]>='a' && raw[at]<='z') ||
           (raw[at]>='A' && raw[at]<='Z') || raw[at]=='-')) ++at;
    String key = raw.substring(start, at);
    while (at < int(raw.length()) && raw[at]==' ') ++at;
    if (!key.length() || at >= int(raw.length()) || raw[at++]!='=' || count==12) return false;
    while (at < int(raw.length()) && raw[at]==' ') ++at;
    String value;
    if (at < int(raw.length()) && raw[at]=='"') {
      start = ++at;
      while (at < int(raw.length()) && raw[at]!='"') {
        if (raw[at]=='\\') return false; // Narrow profile: no quoted escapes.
        ++at;
      }
      if (at == int(raw.length())) return false;
      value = raw.substring(start, at++);
    } else {
      start = at;
      while (at < int(raw.length()) && raw[at]!=',' && raw[at]!=' ') ++at;
      value = raw.substring(start, at);
    }
    if (!value.length()) return false;
    for (int i=0; i<count; ++i) if (keys[i].equalsIgnoreCase(key)) return false;
    keys[count]=key; values[count++]=value;
    while (at < int(raw.length()) && raw[at]==' ') ++at;
    if (at < int(raw.length())) {
      if (raw[at++]!=',' || at==int(raw.length())) return false;
    }
  }
  const auto param = [&](const char* name) -> String {
    for (int i=0; i<count; ++i) if (keys[i].equalsIgnoreCase(name)) return values[i];
    return String();
  };
  String nc=param("nc"), cn=param("cnonce"), response=param("response");
  if (param("username")!=username || param("realm")!=_srealm || ! _srealm.length() ||
      param("nonce")!=_snonce || !_snonce.length() || param("opaque")!=_sopaque ||
      param("uri")!=_r7Target || param("qop")!="auth" || nc.length()!=8 ||
      !cn.length() || cn.length()>64 || response.length()!=32) return false;
  String algorithm=param("algorithm");
  if (algorithm.length() && !algorithm.equalsIgnoreCase("MD5")) return false;
  uint32_t sequence=0;
  for (unsigned i=0;i<8;++i) {
    char c=nc[i]; int x=c>='0' && c<='9'?c-'0':c>='a' && c<='f'?c-'a'+10:c>='A' && c<='F'?c-'A'+10:-1;
    if (x<0) return false;
    sequence=(sequence<<4)|uint32_t(x);
  }
  if (!sequence || sequence<=_r7LastNc) return false;
  MD5Builder md5; md5.begin(); md5.add(_r7Method+":"+_r7Target); md5.calculate();
  String h2=md5.toString();
  md5.begin(); md5.add(H1+":"+_snonce+":"+nc+":"+cn+":auth:"+h2); md5.calculate();
  if (!response.equalsConstantTime(md5.toString())) return false;
  _r7LastNc=sequence;
  return true;
}
'''

HEADER_GUARD = r'''
      if (++headerCount > 32u) return CLIENT_MUST_STOP;
      if (headerName.isEmpty()) return CLIENT_MUST_STOP;
      for (unsigned i=0;i<headerName.length();++i) {
        char c=headerName[i];
        if (!((c>='a' && c<='z') || (c>='A' && c<='Z') ||
              (c>='0' && c<='9') || c=='-')) return CLIENT_MUST_STOP;
      }
      const char* critical[]={"Authorization","Content-Length","Transfer-Encoding","Cookie","Host","Content-Type","Connection"};
      for (unsigned i=0;i<7;++i) if (headerName.equalsIgnoreCase(critical[i])) {
        if (seenHeaders & (1u<<i)) return CLIENT_MUST_STOP;
        seenHeaders |= (1u<<i);
      }
      if (headerName.equalsIgnoreCase("Transfer-Encoding")) return CLIENT_MUST_STOP;
      if (headerName.equalsIgnoreCase("Content-Type") &&
          headerValue.substring(0,10).equalsIgnoreCase("multipart/")) r7Multipart=true;
      if (headerName.equalsIgnoreCase("Content-Length")) {
        if (!headerValue.length()) return CLIENT_MUST_STOP;
        uint32_t n=0;
        for (unsigned i=0;i<headerValue.length();++i) {
          char c=headerValue[i];
          if (c<'0' || c>'9' || n>4096u/10u) return CLIENT_MUST_STOP;
          n=n*10u+uint32_t(c-'0');
          if (n>4096u) return CLIENT_MUST_STOP;
        }
        if (_currentMethod!=HTTP_POST && _currentMethod!=HTTP_PUT &&
            _currentMethod!=HTTP_PATCH && _currentMethod!=HTTP_DELETE && n) return CLIENT_MUST_STOP;
      }
'''

def patch_header(value):
    value = prior.previous.patch_header(value)
    return once(value, '  ServerType  _server;', FIELDS+'  ServerType  _server;', 'R7 fields')

def patch_impl(value):
    value = prior.patch_impl(value)
    value = once(value, 'authReq.startsWith(F("Basic"))', 'authReq.substring(0, 6).equalsIgnoreCase("Basic ")', 'Basic separator')
    start = value.index('template <typename ServerType>\nbool ESP8266WebServerTemplate<ServerType>::authenticateDigest')
    end = value.index('template <typename ServerType>\nString ESP8266WebServerTemplate<ServerType>::_getRandomHexString',start)
    value = value[:start]+DIGEST+'\n'+value[end:]
    value = once(value, 'authReq.startsWith(F("Digest"))', 'authReq.substring(0, 7).equalsIgnoreCase("Digest ")', 'Digest separator')
    value = once(value, '    _snonce=_getRandomHexString();', '    _r7LastNc=0;\n    _snonce=_getRandomHexString();', 'nonce watermark reset')
    return once(value, 'namespace esp8266webserver {', 'namespace esp8266webserver {\n'+READERS, 'R7 readers')

def patch_parser(value):
    value = prior.previous.patch_parser(value)
    value = once(value, '  String methodStr = req.substring(0, addr_start);',
        '  size_t headerBudget=2048; unsigned headerCount=0, seenHeaders=0; bool r7Multipart=false; _r7Work=8192;\n'
        '  String methodStr = req.substring(0, addr_start);\n'
        '  _r7Method=methodStr; _r7Target=req.substring(addr_start+1,addr_end);\n'
        '  if (methodStr!="GET" && methodStr!="HEAD" && methodStr!="POST" && methodStr!="PUT" &&\n'
        '      methodStr!="DELETE" && methodStr!="OPTIONS" && methodStr!="PATCH") return CLIENT_MUST_STOP;', 'R7 raw target')
    old="      req = client.readStringUntil('\\r');\n      client.readStringUntil('\\n');"
    if value.count(old)!=2: raise ValueError('header loop drift')
    value=value.replace(old,'      if (!_r7Line(client, req, headerBudget)) return CLIENT_MUST_STOP;')
    value=value.replace("      if (headerDiv == -1){\n        break;\n      }", "      if (headerDiv == -1) return CLIENT_MUST_STOP;")
    value=once(value,'      headerValue = req.substring(headerDiv + 2);','      headerValue = req.substring(headerDiv + 1);\n      headerValue.trim();', 'GET header whitespace')
    # Both pinned loops collect headers after this point; reject ambiguity first.
    anchor='_collectHeader(headerName.c_str(),headerValue.c_str());'
    if value.count(anchor)!=2: raise ValueError('collect drift')
    value=value.replace(anchor,HEADER_GUARD+'\n      '+anchor)
    value=once(value,'    String plainBuf;',
        '    // Multipart needs incremental authenticated ownership; fail closed here.\n'
        '    if (isForm || r7Multipart) return CLIENT_MUST_STOP;\n    String plainBuf;', 'multipart blocker')
    value=once(value,'!readBytesWithTimeout<ServerType>(client, contentLength, plainBuf, HTTP_MAX_POST_WAIT)',
        '!_r7Body(client, contentLength, plainBuf)', 'absolute body reader')
    return value

def materialize(destination: Path = OUTPUT):
    prior.materialize(destination)
    src=prior.core_root()/prior.previous.LIB
    result={}
    for name,transform in {'ESP8266WebServer.h':patch_header,'ESP8266WebServer-impl.h':patch_impl,'Parsing-impl.h':patch_parser}.items():
        data=transform((src/name).read_text(encoding='utf-8'))
        (destination/name).write_text(data,encoding='utf-8',newline='\n')
        result[name]=hashlib.sha256(data.encode()).hexdigest()
    return result
