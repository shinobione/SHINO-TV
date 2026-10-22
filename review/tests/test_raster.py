"""Render the exact HOST SceneEngine into native-size PNGs using only stdlib."""
import hashlib
import shutil
import struct
import subprocess
import unittest
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.build'/'raster'
SOURCE=ROOT/'tests'/'raster_scene.cpp'
SIZE=240

def png_chunk(kind,data):
    payload=kind+data
    return struct.pack('>I',len(data))+payload+struct.pack('>I',zlib.crc32(payload)&0xffffffff)

def ppm_to_png(ppm,png):
    raw=ppm.read_bytes()
    header=b'P6\n240 240\n255\n'
    if not raw.startswith(header) or len(raw)!=len(header)+SIZE*SIZE*3:
        raise AssertionError("Raster PPM is not exactly 240x240 RGB")
    rgb=raw[len(header):]
    rows=b''.join(b'\0'+rgb[y*SIZE*3:(y+1)*SIZE*3] for y in range(SIZE))
    ihdr=struct.pack('>IIBBBBB',SIZE,SIZE,8,2,0,0,0)
    png.write_bytes(b'\x89PNG\r\n\x1a\n'+png_chunk(b'IHDR',ihdr)+png_chunk(b'IDAT',zlib.compress(rows,9))+png_chunk(b'IEND',b''))
    # Inspect PNG structure, CRCs, IHDR and exact decompressed RGB pixels.
    # Compressed file byte size is NOT a valid rendering gate.
    result=png.read_bytes()
    if not result.startswith(b'\x89PNG\r\n\x1a\n'):
        raise AssertionError('Invalid PNG signature')
    offset=8
    chunks=[]
    encoded=b''
    while offset<len(result):
        if offset+12>len(result):
            raise AssertionError('Truncated PNG chunk')
        length=struct.unpack('>I',result[offset:offset+4])[0]
        kind=result[offset+4:offset+8]
        end=offset+12+length
        if end>len(result):
            raise AssertionError('PNG chunk exceeds file')
        payload=result[offset+8:offset+8+length]
        crc=struct.unpack('>I',result[end-4:end])[0]
        if (zlib.crc32(kind+payload)&0xffffffff)!=crc:
            raise AssertionError('PNG CRC error')
        chunks.append(kind)
        if kind==b'IHDR' and payload!=ihdr:
            raise AssertionError('Incorrect PNG dimensions or pixel format')
        if kind==b'IDAT':
            encoded+=payload
        offset=end
    if chunks!=[b'IHDR',b'IDAT',b'IEND'] or zlib.decompress(encoded)!=rows:
        raise AssertionError('PNG pixels differ from rendered RGB output')
    return hashlib.sha256(rgb).hexdigest()

class Raster(unittest.TestCase):
    def test_real_renderer_pngs_and_edge_cases(self):
        from build_host import compiler_environment
        compiler,env=compiler_environment()
        msvc=Path(compiler).name.lower()=='cl.exe'
        OUT.mkdir(parents=True,exist_ok=True)
        binary=OUT/('raster_scene.exe' if msvc else 'raster_scene')
        if msvc:
            cmd=[compiler,'/nologo','/std:c++20','/EHsc','/O2',
                 '/I'+str(ROOT/'host'),str(SOURCE),'/Fe:'+str(binary)]
        else:
            cmd=[compiler,'-std=c++20','-O2','-Wall','-Wextra','-Werror',
                 '-I'+str(ROOT/'host'),str(SOURCE),'-o',str(binary)]
        subprocess.run(cmd,check=True,timeout=90,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        run=subprocess.run([str(binary),str(OUT)],check=True,timeout=45,capture_output=True,text=True)
        self.assertIn('B54_UI_RASTER_HOST_PASS',run.stdout)
        names=('01_monitoring','02_horloge_meteo','03_horloge_meteo_manuel',
               '04_monitoring_limites','05_meteo_perimee')
        hashes={}
        for name in names:
            hashes[name]=ppm_to_png(OUT/(name+'.ppm'),OUT/(name+'.png'))
        self.assertEqual(hashes['02_horloge_meteo'],hashes['03_horloge_meteo_manuel'])
        self.assertNotEqual(hashes['01_monitoring'],hashes['02_horloge_meteo'])
        self.assertNotEqual(hashes['01_monitoring'],hashes['04_monitoring_limites'])
        (OUT/'README.txt').write_text(
            'B5.4 renderer HOST, genuine shared SceneEngine.h / 5x7 font; synthetic values.\n'
            '240x240 RGB565 raster converted to PNG by Python stdlib. NOT physical LCD.\n'
            +run.stdout,encoding='utf-8')
