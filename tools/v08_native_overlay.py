"""Materialize an isolated, disabled-by-default patch of pinned ESP8266 Core 3.1.2.

The installed framework is fingerprinted and never modified. The overlay is for
host source execution and a separate compile-only PlatformIO project. It does
not register or accept a media endpoint; every media namespace line is closed.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys

from v07_pinned_core_probe import core_root, pinned_sources

ROOT = Path(__file__).resolve().parents[1]
LIB = Path("libraries/ESP8266WebServer/src")
OUTPUT = ROOT / "experiments/v08_preparse/.pio/pinned_overlay"

DECLARATIONS = r'''
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
  // Fixed request-line slot; only the experimental compile-only overlay owns it.
  enum V08LineResult { V08_LINE_PENDING, V08_LINE_LEGACY, V08_LINE_MEDIA, V08_LINE_REJECT };
  V08LineResult _v08ReadFirstLine(ClientType& client);
  void _v08CloseOnce();
  char _v08FirstLine[131] = {};
  uint16_t _v08FirstLength = 0;
  uint32_t _v08Started = 0;
  bool _v08Closed = false;
#endif
'''

METHODS = r'''
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
template <typename ServerType>
typename ESP8266WebServerTemplate<ServerType>::V08LineResult
ESP8266WebServerTemplate<ServerType>::_v08ReadFirstLine(ClientType& client) {
  // Subtraction on unsigned 32-bit ticks is wrap-safe for this 2-second bound.
  if (uint32_t(millis() - _v08Started) >= 2000u) return V08_LINE_REJECT;
  static const char media[] = "/api/v2/bridge/media";
  uint8_t work = 64;
  while (work-- && client.available() > 0) {
    const int input = client.read();
    if (input < 0) break;
    const uint8_t byte = uint8_t(input);
    if (_v08FirstLength >= 130u) return V08_LINE_REJECT;
    if (byte < 0x20u && byte != '\r' && byte != '\n') return V08_LINE_REJECT;
    if (byte > 0x7eu) return V08_LINE_REJECT;
    if (_v08FirstLength && _v08FirstLine[_v08FirstLength - 1] == '\r' && byte != '\n')
      return V08_LINE_REJECT;
    if (byte == '\n' && (!_v08FirstLength || _v08FirstLine[_v08FirstLength - 1] != '\r'))
      return V08_LINE_REJECT;
    _v08FirstLine[_v08FirstLength++] = char(byte);
    if (byte == '\n') {
      _v08FirstLine[_v08FirstLength - 2] = 0; // terminate before CRLF
      const size_t textLength = _v08FirstLength - 2;
      // Stock routing decodes percent escapes. Decode once in fixed stack space
      // before deciding whether a media candidate can reach legacy handlers.
      char decoded[131];
      size_t decodedLength = 0;
      for (size_t i = 0; i < textLength; ++i) {
        uint8_t b = uint8_t(_v08FirstLine[i]);
        if (b == '%') {
          if (i + 2 >= textLength) return V08_LINE_REJECT;
          const auto nibble = [](char c) -> int {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            if (c >= 'A' && c <= 'F') return c - 'A' + 10;
            return -1;
          };
          const int hi = nibble(_v08FirstLine[i + 1]);
          const int lo = nibble(_v08FirstLine[i + 2]);
          if (hi < 0 || lo < 0) return V08_LINE_REJECT;
          b = uint8_t((hi << 4) | lo);
          i += 2;
        }
        if (b < 0x20u || b > 0x7eu) return V08_LINE_REJECT;
        decoded[decodedLength++] = char(b);
      }
      for (size_t i = 0; i + sizeof(media) - 1 <= decodedLength; ++i) {
        size_t j = 0;
        while (j < sizeof(media) - 1 && decoded[i + j] == media[j]) ++j;
        if (j == sizeof(media) - 1) return V08_LINE_MEDIA;
      }
      size_t first = 0;
      while (first < textLength && _v08FirstLine[first] != ' ') ++first;
      if (!first || first == textLength) return V08_LINE_REJECT;
      size_t second = first + 1;
      while (second < textLength && _v08FirstLine[second] != ' ') ++second;
      if (second == first + 1 || second == textLength || _v08FirstLine[first + 1] != '/')
        return V08_LINE_REJECT;
      const char* version = _v08FirstLine + second + 1;
      const bool http11 = textLength - second - 1 == 8 &&
        version[0]=='H' && version[1]=='T' && version[2]=='T' && version[3]=='P' &&
        version[4]=='/' && version[5]=='1' && version[6]=='.' && version[7]=='1';
      const bool http10 = textLength - second - 1 == 8 &&
        version[0]=='H' && version[1]=='T' && version[2]=='T' && version[3]=='P' &&
        version[4]=='/' && version[5]=='1' && version[6]=='.' && version[7]=='0';
      return http11 || http10 ? V08_LINE_LEGACY : V08_LINE_REJECT;
    }
  }
  if (!client.connected() && client.available() <= 0) return V08_LINE_REJECT;
  return V08_LINE_PENDING;
}

template <typename ServerType>
void ESP8266WebServerTemplate<ServerType>::_v08CloseOnce() {
  if (!_v08Closed) {
    _v08Closed = true;
    _currentClient.stop();
  }
}
#endif
'''


def once(value: str, old: str, new: str, label: str) -> str:
    if value.count(old) != 1:
        raise ValueError(f"ANCHOR_DRIFT {label}: {value.count(old)}")
    return value.replace(old, new, 1)


def patch_header(value: str) -> str:
    value = once(value, "  ClientFuture _parseRequest(ClientType& client);",
                 """  ClientFuture _parseRequest(ClientType& client
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
    , const char* prefetchedFirstLine
#endif
  );""", "parse declaration")
    value = once(value, "  ServerType  _server;", DECLARATIONS + "  ServerType  _server;",
                 "owner fields")
    return value


def patch_parser(value: str) -> str:
    value = once(value,
        "ESP8266WebServerTemplate<ServerType>::_parseRequest(ClientType& client) {\n"
        "  // Read the first line of HTTP request\n"
        "  String req = client.readStringUntil('\\r');\n"
        "  DBGWS(\"request: %s\\n\", req.c_str());\n"
        "  client.readStringUntil('\\n');",
        """ESP8266WebServerTemplate<ServerType>::_parseRequest(ClientType& client
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
    , const char* prefetchedFirstLine
#endif
) {
  // Research handoff: stock parser receives the exact bounded first line.
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
  String req = prefetchedFirstLine;
  DBGWS("request: %s\\n", req.c_str());
#else
  String req = client.readStringUntil('\\r');
  DBGWS("request: %s\\n", req.c_str());
  client.readStringUntil('\\n');
#endif""", "prefetched line")
    return value


def patch_impl(value: str) -> str:
    marker = "template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::handleClient() {"
    value = once(value, marker, METHODS + "\n" + marker, "preparse methods")
    value = once(value, "    _statusChange = millis();\n  }\n\n  bool keepCurrentClient",
        """    _statusChange = millis();
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
    _v08Started = _statusChange;
    _v08FirstLength = 0;
    _v08Closed = false;
#endif
  }

  bool keepCurrentClient""", "accept init")
    value = once(value,
        "    if (_currentClient.available() && _keepAlive) {\n      _currentStatus = HC_WAIT_READ;\n    }",
        """    if (_currentClient.available() && _keepAlive) {
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
      if (_currentStatus == HC_WAIT_CLOSE) {
        _v08FirstLength = 0;
        _v08Started = millis();
      }
#endif
      _currentStatus = HC_WAIT_READ;
    }""", "keepalive new request")
    value = once(value,
        "    case HC_WAIT_READ:\n      // Wait for data from client to become available\n"
        "      if (_currentClient.available()) {\n"
        "        switch (_parseRequest(_currentClient))",
        """    case HC_WAIT_READ:
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
      {
        const V08LineResult firstLine = _v08ReadFirstLine(_currentClient);
        if (firstLine == V08_LINE_PENDING) {
          keepCurrentClient = true;
          callYield = true;
          break;
        }
        if (firstLine != V08_LINE_LEGACY) {
          // Media namespace is deny-all; malformed lines also close here.
          _v08CloseOnce();
          break;
        }
        switch (_parseRequest(_currentClient, _v08FirstLine))
#else
      // Wait for data from client to become available
      if (_currentClient.available()) {
        switch (_parseRequest(_currentClient))
#endif""", "read dispatch")
    value = once(value,
        "          _currentClient.stop();\n          break;\n        case CLIENT_IS_GIVEN:",
        """#ifdef SHINO_V08_PREPARSE_EXPERIMENT
          _v08CloseOnce();
#else
          _currentClient.stop();
#endif
          break;
        case CLIENT_IS_GIVEN:""", "terminal close")
    value = once(value, "        } // switch _parseRequest()\n      } else {",
        """        } // switch _parseRequest()
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
        _v08FirstLength = 0;
        _v08Started = millis();
      }
#else
      } else {
""", "dispatch end")
    value = once(value,
        "      }\n      break;\n    case HC_WAIT_CLOSE:",
        """      }
      break;
    case HC_WAIT_CLOSE:""", "wait close context")
    # The stock no-data else remains compiled only without the experiment.
    value = once(value,
        "        callYield = true;\n      }\n      break;\n    case HC_WAIT_CLOSE:",
        """        callYield = true;
      }
#endif
      break;
    case HC_WAIT_CLOSE:""", "stock wait else")
    return value


def materialize(destination: Path = OUTPUT) -> dict[str, str]:
    pinned_sources()  # version and all six source hashes before any copying
    src = core_root() / LIB
    destination = destination.resolve()
    if destination == src.resolve() or src.resolve() in destination.parents:
        raise ValueError("REFUSE_SOURCE_PACKAGE_WRITE")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, destination, dirs_exist_ok=True)
    changed = {
        "ESP8266WebServer.h": patch_header,
        "Parsing-impl.h": patch_parser,
        "ESP8266WebServer-impl.h": patch_impl,
    }
    result = {}
    for name, transform in changed.items():
        target = destination / name
        original = target.read_text(encoding="utf-8")
        patched = transform(original)
        target.write_text(patched, encoding="utf-8", newline="\n")
        result[name] = hashlib.sha256(patched.encode()).hexdigest()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(materialize(args.dest))
