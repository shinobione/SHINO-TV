#!/usr/bin/env python3
"""Inspect GeekMagic manufacturer OTA archives offline. Never connects to a device."""
import argparse
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path

FLASH_MODES = {0: 'QIO', 1: 'QOUT', 2: 'DIO', 3: 'DOUT'}
FLASH_SIZES = {0: '512 KB', 1: '256 KB', 2: '1 MB', 3: '2 MB', 4: '4 MB', 5: '2 MB', 6: '4 MB', 8: '8 MB', 9: '16 MB'}
FREQUENCIES = {0: '40 MHz', 1: '26 MHz', 2: '20 MHz', 15: '80 MHz'}

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def parse_esp8266_image(data):
    """Read basic ESP8266 image fields; do not confuse header flash size with a measured chip."""
    if len(data) < 8 or data[0] != 0xE9:
        return {'recognized': False, 'reason': 'No ESP8266 0xE9 image header at offset zero'}
    count, mode, info, entry = data[1], data[2], data[3], struct.unpack_from('<I', data, 4)[0]
    if count == 0 or count > 16:
        return {'recognized': False, 'reason': f'Unusual segment count: {count}'}
    segments = []
    cursor = 8
    for i in range(count):
        if cursor + 8 > len(data):
            return {'recognized': False, 'reason': f'Truncated segment header {i}'}
        addr, size = struct.unpack_from('<II', data, cursor)
        cursor += 8
        if size > len(data) - cursor:
            return {'recognized': False, 'reason': f'Truncated segment payload {i}'}
        segments.append({'index': i, 'load_address': f'0x{addr:08x}', 'size': size,
                         'data_offset': cursor})
        cursor += size
    return {'recognized': True, 'segment_count': count,
            'flash_mode': FLASH_MODES.get(mode, f'unknown ({mode})'),
            'flash_size_claim': FLASH_SIZES.get(info >> 4, f'unknown ({info >> 4})'),
            'flash_frequency': FREQUENCIES.get(info & 0xf, f'unknown ({info & 0xf})'),
            'entrypoint': f'0x{entry:08x}', 'segments': segments,
            'last_segment_end': cursor, 'payload_bytes_after_segments': len(data) - cursor}

def printable_strings(data, length=10, limit=30):
    result = []
    for match in re.finditer(rb'[ -~]{%d,}' % length, data):
        string = match.group().decode('ascii')
        if re.search(r'https?://|/(?:api|update|upload|image|gif|set|.*[.]json)|ESP|LittleFS|SPIFFS', string, re.I):
            result.append({'offset': f'0x{match.start():x}', 'text': string[:160]})
            if len(result) >= limit:
                break
    return result

def inspect(path):
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        members = []
        firmwares = []
        manifest_text = []
        for info in zf.infolist():
            blob = zf.read(info)
            members.append({'name': info.filename, 'size': len(blob), 'sha256': sha256(blob)})
            if info.filename.lower().endswith('.bin'):
                firmwares.append({'name': info.filename, 'size': len(blob),
                                  'sha256': sha256(blob), 'header': parse_esp8266_image(blob),
                                  'strings_sample': printable_strings(blob)})
            if 'md5' in info.filename.lower() and len(blob) < 8192:
                manifest_text.append(blob.decode('utf-8', 'replace').strip())
        return {'archive': path.name, 'archive_sha256': sha256(path.read_bytes()),
                'members': members, 'firmwares': firmwares, 'vendor_md5_text': manifest_text}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('archives', nargs='+', type=Path, help='Official ZIP files on your own PC')
    ap.add_argument('--json', action='store_true', help='Print machine-readable JSON')
    args = ap.parse_args()
    result = [inspect(p) for p in args.archives]
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for item in result:
            print(item['archive'], item['archive_sha256'])
            for fw in item['firmwares']:
                print('  ', fw['name'], 'size', fw['size'], 'sha256', fw['sha256'])
                print('  ', json.dumps(fw['header']))
                for string in fw['strings_sample']:
                    print('   ', string['offset'], string['text'])
            for line in item['vendor_md5_text']:
                print('  vendor md5:', line)

if __name__ == '__main__':
    main()
