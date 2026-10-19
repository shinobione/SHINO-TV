"""Pin and clone ESP8266 3.1.2 Core webserver, patch *only* request-line.

This is a compiler experiment, NOT firmware installation. Never modify the
global PlatformIO framework package. Unlike the already-reviewed StageA
overlay, leave existing legacy POST, headers, Digest, UI, media, Wi-Fi/OTA
untouched. It does not make all legacy headers memory-bounded.
"""
import hashlib
import shutil
from pathlib import Path

PINS={
 "ESP8266WebServer.h":"167b098fa4f964fc92ae9b89d531a69e3984561d4ca0729ab857f8f36d52dd67",
 "ESP8266WebServer-impl.h":"19934c7352eea30acb6d30ab6314d1b794fa5311d88fd3cdc7edaa6cdb7bb150",
 "Parsing-impl.h":"f8fe756b04222f20c49813ea63f0c8a90a99034255324de84349e32755afe818",
}
M3_ROUTE="/api/v1/display/mode"
FIRST="  String req = client.readStringUntil('\\r');"
SECOND="  client.readStringUntil('\\n');"
PATH='  String url = req.substring(addr_start + 1, addr_end);'
INCLUDE='#include "M3PBoundedLine.h"'
CALL="""  String req;
  const uint32_t m3pStarted=millis();
  if(!ShinoM3P::readFirstLine(client,req,[]() {return millis();},
                              []() {yield();},m3pStarted))
    return CLIENT_MUST_STOP;"""
CHECK="""  // M3 handoff may see a parsed method/path but not the raw HTTP version.
  // Preserve the exact M3-C first-line contract before allowing its hook.
  if(url == F("/api/v1/display/mode") ||
     url.startsWith(F("/api/v1/display/mode?"))) {
    if(req != F("POST /api/v1/display/mode HTTP/1.1"))
      return CLIENT_MUST_STOP;
  }"""
def once(text,old,new):
    if text.count(old)!=1:
        raise ValueError("M3P_PINNED_CORE_PARSER_ANCHOR_DRIFT "+repr(old))
    return text.replace(old,new,1)
def patch_parser(src):
    x=once(src,"namespace esp8266webserver {",
           INCLUDE+"\nnamespace esp8266webserver {")
    x=once(x,FIRST,CALL)
    x=once(x,SECOND+"\n  //reset header value","  //reset header value")
    x=once(x,PATH,PATH+"\n"+CHECK)
    if FIRST in x:raise ValueError("Original unbounded FIRST line still active")
    if "if (_hook)" not in x or "client.readStringUntil('\\r')" not in x:
        raise ValueError("Legacy parsing/handler unexpectedly removed")
    return x
def materialize(core,destination):
    source=Path(core).resolve()/"libraries/ESP8266WebServer"
    dest=Path(destination).resolve()
    if dest==source or source in dest.parents:
        raise ValueError("REFUSE_MODIFY_FRAMEWORK_PACKAGE")
    if not source.is_dir():raise ValueError("Core WebServer missing")
    for name,digest in PINS.items():
        if hashlib.sha256((source/"src"/name).read_bytes()).hexdigest()!=digest:
            raise ValueError("CORE_3_1_2_PIN_MISMATCH "+name)
    # Allow a clean, isolated scratch overlay only, never user secrets.
    if dest.exists():
        if not (dest/"M3P_GENERATED_ONLY").exists():
            raise ValueError("REFUSE_REPLACE_UNOWNED_DIRECTORY "+str(dest))
        shutil.rmtree(dest)
    shutil.copytree(source,dest)
    src=dest/"src"/"Parsing-impl.h"
    src.write_text(patch_parser((source/"src"/"Parsing-impl.h").read_text()),
                   encoding="utf-8",newline="\n")
    (dest/"M3P_GENERATED_ONLY").write_text(
        "Generated isolated Core 3.1.2 server clone, never device firmware.\n")
    assert (source/"src"/"Parsing-impl.h").read_bytes()!=src.read_bytes()
    return dest/"src"
