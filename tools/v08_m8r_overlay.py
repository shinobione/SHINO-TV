"""Separate single-owner media path; retain EXACT Mission 6A legacy parser/auth.

Mission 6C is provenance, never the source of this candidate parser.
No installed package or production source writes.
"""
from pathlib import Path
import hashlib
import shutil
import v08_m6a_overlay as legacy
from v07_pinned_core_probe import core_root, pinned_sources
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'experiments/v08_m8r/.pio/overlay'

def patch_header(value):
    value=legacy.previous.patch_header(value)
    value=legacy.previous.once(value,'  void handleClient();', '''  void handleClient();
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
  // Trusted lab setup only. Null by default; no route/provisioning endpoint.
  void setOfflineMedia(m7::Ingress* media) { _m7Media = media; }
#endif''','media setup seam')
    value=legacy.previous.once(value,'  bool _v08Closed = false;', '''  bool _v08Closed = false;
  m7::Ingress* _m7Media = nullptr;
  bool _m7Active = false;''','media owner fields')
    return '#include <MediaIngress.h>\n'+value

def patch_impl(value):
    value=legacy.patch_impl(value)
    value=legacy.previous.once(value,'void ESP8266WebServerTemplate<ServerType>::handleClient() {', '''void ESP8266WebServerTemplate<ServerType>::handleClient() {
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
  if (_m7Media) _m7Media->service();
#endif''','owner timer service')
    value=legacy.previous.once(value,'    _v08Closed = false;','    _v08Closed = false;\n    _m7Active = false;','accept media reset')
    value=legacy.previous.once(value,'        const V08LineResult firstLine = _v08ReadFirstLine(_currentClient);', '''        if (_m7Active) {
          const bool continued = _m7Media && (_m7Media->needsProof()
              ? _m7Media->verifyHeaders() : _m7Media->poll(_currentClient));
          if (continued) {
            if (!_currentClient.available() &&
                (_server.hasClientData() || _server.hasMaxPendingClients()) &&
                uint32_t(millis() - _statusChange) > HTTP_MAX_DATA_AVAILABLE_WAIT) {
              _v08CloseOnce();
            } else {
              keepCurrentClient = true;
              callYield = true;
            }
          } else {
            _m7Active = false;
            _v08CloseOnce();
          }
          break;
        }
        const V08LineResult firstLine = _v08ReadFirstLine(_currentClient);''','media continuation')
    value=legacy.previous.once(value,'        if (firstLine != V08_LINE_LEGACY) {', '''        if (firstLine == V08_LINE_MEDIA && _m7Media) {
          if (_m7Media->begin(_v08FirstLine, _v08Started)) {
            _m7Active = true;
            keepCurrentClient = true;
            callYield = true;
          } else _v08CloseOnce();
          break;
        }
        if (firstLine != V08_LINE_LEGACY) {''','media handoff')
    value=legacy.previous.once(value,'    _v08Closed = true;', '''    _v08Closed = true;
    if (_m7Active && _m7Media) _m7Media->cancel();
    _m7Active = false;''','terminal media buffer release')
    return value

def materialize(destination=OUTPUT):
    pinned_sources();src=core_root()/legacy.previous.LIB;destination=destination.resolve()
    if destination==src.resolve() or src.resolve() in destination.parents:raise ValueError('REFUSE_PACKAGE_WRITE')
    shutil.copytree(src,destination,dirs_exist_ok=True)
    result={}
    for name,fn in {'ESP8266WebServer.h':patch_header,'ESP8266WebServer-impl.h':patch_impl,'Parsing-impl.h':legacy.previous.patch_parser}.items():
        text=fn((src/name).read_text(encoding='utf-8'));(destination/name).write_text(text,encoding='utf-8',newline='\n');result[name]=hashlib.sha256(text.encode()).hexdigest()
    expected=legacy.previous.patch_parser((src/'Parsing-impl.h').read_text(encoding='utf-8'))
    assert (destination/'Parsing-impl.h').read_text(encoding='utf-8')==expected
    return result
