"""Mission 6A isolated candidate. Mission 2/5 transformer stays historical.

No installed Core writes, route registration or media admission. Fingerprints
and single-anchor transforms are inherited from the previous overlay.
"""
from pathlib import Path
import hashlib
import shutil

import v08_native_overlay as previous
from v07_pinned_core_probe import core_root, pinned_sources

OUTPUT = previous.ROOT / 'experiments/v08_m6a/.pio/pinned_overlay'

CLASSIFY = r'''
      size_t first = 0;
      while (first < textLength && _v08FirstLine[first] != ' ') ++first;
      if (!first || first == textLength) return V08_LINE_REJECT;
      size_t second = first + 1;
      while (second < textLength && _v08FirstLine[second] != ' ') ++second;
      if (second == first + 1 || second == textLength || _v08FirstLine[first + 1] != '/')
        return V08_LINE_REJECT;
      const char* version = _v08FirstLine + second + 1;
      if (textLength - second - 1 != 8 || version[0]!='H' || version[1]!='T' ||
          version[2]!='T' || version[3]!='P' || version[4]!='/' || version[5]!='1' ||
          version[6]!='.' || (version[7]!='0' && version[7]!='1')) return V08_LINE_REJECT;

      // Pinned routing retains the RAW path; only argument parsing urlDecodes.
      // Inspect just the path for reservation. Never rewrite the parser input.
      // Query values (including percent literals/malformed escapes) are legacy.
      size_t pathEnd = first + 1;
      while (pathEnd < second && _v08FirstLine[pathEnd] != '?') ++pathEnd;
      char decoded[131];
      size_t decodedLength = 0;
      const auto nibble = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        if (c >= 'A' && c <= 'F') return c - 'A' + 10;
        return -1;
      };
      for (size_t i = first + 1; i < pathEnd; ++i) {
        uint8_t b = uint8_t(_v08FirstLine[i]);
        if (b == '%') {
          if (i + 2 >= pathEnd) return V08_LINE_REJECT;
          const int hi = nibble(_v08FirstLine[i + 1]), lo = nibble(_v08FirstLine[i + 2]);
          if (hi < 0 || lo < 0) return V08_LINE_REJECT;
          b = uint8_t((hi << 4) | lo); i += 2;
        }
        // Reject ambiguous path syntax rather than recursively normalizing it.
        // Nested escapes, separators and dot segments cannot alias into legacy.
        if (b < 0x20u || b > 0x7eu || b=='%' || b=='\\' || b=='?' || b=='#')
          return V08_LINE_REJECT;
        // Repeated slashes are collapsed ONLY in the reservation view.
        if (b=='/' && decodedLength && decoded[decodedLength-1]=='/') continue;
        decoded[decodedLength++] = char(b);
      }
      size_t segment = 1;
      for (size_t i = 1; i <= decodedLength; ++i) {
        if (i == decodedLength || decoded[i]=='/') {
          const size_t n = i - segment;
          if ((n==1 && decoded[segment]=='.') ||
              (n==2 && decoded[segment]=='.' && decoded[segment+1]=='.'))
            return V08_LINE_REJECT;
          segment = i + 1;
        }
      }
      const size_t mediaLength = sizeof(media) - 1;
      if (decodedLength >= mediaLength &&
          (decodedLength == mediaLength || decoded[mediaLength]=='/' ||
           decoded[mediaLength]==';' || decoded[mediaLength]==' ')) {
        size_t j = 0;
        while (j < mediaLength && decoded[j] == media[j]) ++j;
        if (j == mediaLength) return V08_LINE_MEDIA;
      }
      return V08_LINE_LEGACY;
'''

start = previous.METHODS.index('      // Stock routing decodes percent escapes.')
end = previous.METHODS.index('\n    }\n  }', start)
METHODS = previous.METHODS[:start] + CLASSIFY + previous.METHODS[end:]
METHODS = previous.once(METHODS, '    const int input = client.read();',
    '    if (uint32_t(millis() - _v08Started) >= 2000u) return V08_LINE_REJECT;\n'
    '    const int input = client.read();', 'within-slice deadline')
METHODS = previous.once(METHODS, "    if (byte == '\\n') {",
    "    if (byte == '\\n') {\n"
    '      if (uint32_t(millis() - _v08Started) >= 2000u) return V08_LINE_REJECT;',
    'handoff deadline')
METHODS = previous.once(METHODS,
    '  if (!client.connected() && client.available() <= 0)',
    '  if (uint32_t(millis() - _v08Started) >= 2000u) return V08_LINE_REJECT;\n'
    '  if (!client.connected() && client.available() <= 0)', 'slice-exit deadline')


def patch_impl(value: str) -> str:
    value = previous.patch_impl(value)
    value = previous.once(value, previous.METHODS, METHODS, 'candidate classifier')
    value = previous.once(value,
        '        if (firstLine == V08_LINE_PENDING) {\n          keepCurrentClient = true;',
        '''        if (firstLine == V08_LINE_PENDING) {
          // Restore pinned ready/full-queue policy after incremental drain.
          // The grace is strictly >30ms from the stock status-change clock.
          if (!_currentClient.available() &&
              (_server.hasClientData() || _server.hasMaxPendingClients()) &&
              uint32_t(millis() - _statusChange) > HTTP_MAX_DATA_AVAILABLE_WAIT) {
            _v08CloseOnce();
          } else {
            keepCurrentClient = true;
          }''', 'pending fairness')
    # The outer stock disconnected branch skips the reader. Clean it once too.
    value = previous.once(value,
        '    } // switch _currentStatus\n  }\n\n  if (!keepCurrentClient)',
        '''    } // switch _currentStatus
#ifdef SHINO_V08_PREPARSE_EXPERIMENT
  } else if (_currentStatus == HC_WAIT_READ) {
    _v08CloseOnce();
#endif
  }

  if (!keepCurrentClient)''', 'disconnected first-line cleanup')
    return value


def materialize(destination: Path = OUTPUT) -> dict[str, str]:
    pinned_sources()
    src = core_root() / previous.LIB
    destination = destination.resolve()
    if destination == src.resolve() or src.resolve() in destination.parents:
        raise ValueError('REFUSE_SOURCE_PACKAGE_WRITE')
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, destination, dirs_exist_ok=True)
    result = {}
    for name, transform in {'ESP8266WebServer.h': previous.patch_header,
                            'Parsing-impl.h': previous.patch_parser,
                            'ESP8266WebServer-impl.h': patch_impl}.items():
        text = transform((destination / name).read_text(encoding='utf-8'))
        (destination / name).write_text(text, encoding='utf-8', newline='\n')
        result[name] = hashlib.sha256(text.encode()).hexdigest()
    return result


if __name__ == '__main__':
    print(materialize())
