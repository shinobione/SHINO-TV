"""B5 4m2m LAN/OTA opt-in build. Never changes B4 sources or contacts devices.

The normal HTTP OTA receiver is copied into a new disposable source graph,
then receives only exact-anchor HomeLAN additions. Public CI images are inert;
owner-private releases require a new, separately approved physical decision.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from m9_stagea_build import ROOT, ENV
from shino_http_ota_build import (
    prepare as prepare_b4, materialize_http as materialize_b4,
    descriptor, elf_layout, stack_frames,
)
from shino_owner_transition import OWNER, load
from m9_signed_release import validate_image
from shino_wifi_resources import one


def once(source, old, replacement):
    if source.count(old)!=1:raise ValueError("B5 anchor drift")
    return source.replace(old,replacement,1)


def materialize_http(core,destination):
    """Retain B4's pinned, bounded parser and add two unique B5 headers."""
    headers=materialize_b4(core,destination)
    parser=headers/"Parsing-impl.h"
    data=parser.read_text(encoding="utf-8")
    data=once(data,
      '"X-Shino-Nonce","X-Shino-Proof"};',
      '"X-Shino-Nonce","X-Shino-Proof","Origin","X-Shino-Lan-Intent"};')
    data=once(data,"i<11;++i","i<13;++i")
    parser.write_text(data,encoding="utf-8",newline="\n")
    return headers


def patch_normal(source):
    source=once(source,'#include "ShinoRelease.h"',
          '#include "ShinoRelease.h"\n#include "B5Lan.h"')
    source=once(source,
          'WiFiManager network("","","SHINO-TV-StageA",SHINO_SETUP_AP_PSK);',
          '// B5 operates AP/STA via the separate, opt-in 4m2m controller.')
    source=once(source,'WiFi.getMode()==WIFI_AP&&uint32_t(millis()-uploadStart)<120000',
          'B5Lan::permitted(server)&&uint32_t(millis()-uploadStart)<120000')
    source=once(source,'enum class Route:uint8_t{Closed,Normal,MetricsGet,MetricsPost,Identity,Upload};',
          'enum class Route:uint8_t{Closed,Normal,MetricsGet,MetricsPost,Identity,Upload,LanIntent,LanProvision,LanStatus};')
    source=once(source,
          'if(path=="/api/v1/update/status"||path=="/api/v1/m9/maintenance/result")return Route::Identity;',
          'if(path=="/api/v1/update/status"||path=="/api/v1/m9/maintenance/result")return Route::Identity;\n'
          '        if(path=="/api/v1/lan/status")return Route::LanStatus;\n'
          '        if(path=="/api/v1/lan/intent")return Route::LanIntent;')
    source=once(source,'if(path=="/api/v1/update")return Route::Upload;',
          'if(path=="/api/v1/update")return Route::Upload;\n'
          '        if(path=="/api/v1/lan/provision")return Route::LanProvision;')
    source=once(source,
          'bool localPeer(){const auto p=server.client().remoteIP();return WiFi.getMode()==WIFI_AP&&server.client().localIP()==WiFi.softAPIP()&&p[0]==192&&p[1]==168&&p[2]==4&&p[3]>1&&p[3]<255;}',
          'bool localPeer(){return B5Lan::permitted(server);}')
    source=once(source,'const Route selected=route();uint32_t bytes=0;',
          'const Route selected=route();uint32_t bytes=0;\n'
          '    if(!B5Lan::permitted(server)){respond(403,"{\\\"error\\\":\\\"NETWORK_POLICY\\\"}");return false;}')
    return source
