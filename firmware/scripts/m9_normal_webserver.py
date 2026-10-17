"""Pinned StageA-only bounded pre-body parser. Never edits the installed Core.

Same Stream/Core Digest implementation as the reviewed ingress, without media,
onboarding or OTA extensions. Every StageA translation unit uses this one ABI.
"""
from pathlib import Path
import hashlib, shutil
PINS={
    'ESP8266WebServer.h':'167b098fa4f964fc92ae9b89d531a69e3984561d4ca0729ab857f8f36d52dd67',
    'ESP8266WebServer-impl.h':'19934c7352eea30acb6d30ab6314d1b794fa5311d88fd3cdc7edaa6cdb7bb150',
    'Parsing-impl.h':'f8fe756b04222f20c49813ea63f0c8a90a99034255324de84349e32755afe818',
}

def once(text, old, new):
    if text.count(old)!=1:raise ValueError('StageA parser anchor drift')
    return text.replace(old,new,1)

def patch_header(text):
    text=once(text,'  void handleClient();','  void handleClient();\n  void setStageAPrebody(std::function<bool()> fn) { _stageAPrebody=fn; }')
    return once(text,'  size_t           _contentLength = 0;',
        '  std::function<bool()> _stageAPrebody;\n  uint32_t _stageAStarted = 0;\n  size_t           _contentLength = 0;')

LINE=r'''
template<class Client> bool m9StageALine(Client& client, String& line, size_t maximum, uint32_t started) {
  line.clear();
  while (uint32_t(millis()-started)<2000) {
    if (!client.available()) { if(!client.connected()) return false; yield(); continue; }
    const int c=client.read();
    if(c=='\r') {
      while(!client.available() && client.connected() && uint32_t(millis()-started)<2000) yield();
      return client.available() && client.read()=='\n';
    }
    if(c<32 || c>126 || line.length()>=maximum) return false;
    line+=char(c);
  }
  return false;
}
inline bool m9StageAUnique(const String& name, unsigned& seen) {
  const char* keys[]={"Host","Authorization","Content-Length","Content-Type","Transfer-Encoding","Connection"};
  for(unsigned i=0;i<6;++i) if(name.equalsIgnoreCase(keys[i])) {
    if(seen&(1u<<i))return false;
    seen|=1u<<i;
  }
  return true;
}
'''

def patch_parser(text):
    text=once(text,'namespace esp8266webserver {','namespace esp8266webserver {\n'+LINE)
    text=once(text,"  String req = client.readStringUntil('\\r');",
        '  _stageAStarted=millis();\n  unsigned seen=0,headerBytes=0,headerCount=0;\n  String req;\n  if(!m9StageALine(client,req,256,_stageAStarted)) return CLIENT_MUST_STOP;')
    text=once(text,"\n  client.readStringUntil('\\n');\n  //reset header value",'\n  //reset header value')
    text=once(text,"  int hasSearch = url.indexOf('?');","  int hasSearch = url.indexOf('?');\n  if(hasSearch!=-1) return CLIENT_MUST_STOP;")
    marker="      req = client.readStringUntil('\\r');\n      client.readStringUntil('\\n');"
    if text.count(marker)!=2:raise ValueError('StageA header loop drift')
    text=text.replace(marker,'''      if(!m9StageALine(client,req,512,_stageAStarted)) return CLIENT_MUST_STOP;
      headerBytes+=req.length()+2;
      if(headerBytes>2048 || ++headerCount>32) return CLIENT_MUST_STOP;''')
    text=once(text,'      headerValue.trim();','      headerValue.trim();\n      if(!m9StageAUnique(headerName,seen)) return CLIENT_MUST_STOP;')
    text=once(text,'      headerValue = req.substring(headerDiv + 2);',
        '      headerValue = req.substring(headerDiv + 1);\n      headerValue.trim();\n      if(!m9StageAUnique(headerName,seen)) return CLIENT_MUST_STOP;')
    # Close legacy multipart/encoded parser paths before reading any body.
    text=once(text,'    String plainBuf;', '''    if(!_stageAPrebody || !_stageAPrebody()) return CLIENT_REQUEST_IS_HANDLED;
    if(isForm || isEncoded || contentLength>384) return CLIENT_MUST_STOP;
    String plainBuf;''')
    text=once(text,'readBytesWithTimeout<ServerType>(client, contentLength, plainBuf, HTTP_MAX_POST_WAIT)',
        'readBytesWithTimeout<ServerType>(client, contentLength, plainBuf, uint32_t(millis()-_stageAStarted)<2000 ? int(2000-uint32_t(millis()-_stageAStarted)) : 0)')
    text=once(text,'    if (isEncoded) {','    if(uint32_t(millis()-_stageAStarted)>=2000) return CLIENT_MUST_STOP;\n    if (isEncoded) {')
    text=once(text,'    _parseArguments(searchStr);\n  }',
        '    if(!_stageAPrebody || !_stageAPrebody()) return CLIENT_REQUEST_IS_HANDLED;\n    _parseArguments(searchStr);\n  }')
    return text

def materialize(core, destination):
    source=Path(core)/'libraries/ESP8266WebServer';destination=Path(destination)
    if source.resolve()==destination.resolve() or source.resolve() in destination.resolve().parents:
        raise ValueError('REFUSE_PACKAGE_WRITE')
    for name,digest in PINS.items():
        if hashlib.sha256((source/'src'/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Pinned StageA Core source changed: '+name)
    shutil.copytree(source,destination,dirs_exist_ok=True)
    for name,patch in (('ESP8266WebServer.h',patch_header),('Parsing-impl.h',patch_parser)):
        (destination/'src'/name).write_text(patch((source/'src'/name).read_text()),encoding='utf-8',newline='\n')
    return destination/'src'
