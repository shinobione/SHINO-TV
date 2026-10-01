"""Numeric offline linked resource comparison, never contacts the SmallTV."""
import argparse, hashlib, json, re
from pathlib import Path
from v08_m8r_memory import inspect
from v08_m8_stack_gate import run_tool
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'experiments/artwork_pilot/.pio/build'

def frames(environment):
    result = {}
    for p in (BASE/environment).rglob('*.su'):
        for row in p.read_text().splitlines():
            m = re.match(r'^.*?:\d+:\d+:(.*?)\t(\d+)\t(.*)$',row)
            if m and any(n in m[1] for n in ('artworkPilotAfterHttp','ArtworkPilot::Renderer',
                    'ArtworkLcd::','m7::metadata(', 'm7::Receiver::receive(',
                    'FirstBootBridge::loop()', 'Arduino_GFX::drawChar(',
                    'Arduino_HWSPI::writePixels(', 'Arduino_TFT::draw16bitRGBBitmap(',
                    'Arduino_TFT::writeFillRectPreclipped(', 'Arduino_GFX::write(')):
                result[m[1]] = {'bytes':int(m[2]),'kind':m[3]}
    return result

def objects(elf):
    result = {}
    for row in run_tool('nm','-S','-C',elf).splitlines():
        parts=row.split(maxsplit=3)
        if len(parts)==4 and any(parts[3].endswith(n) for n in
                ('artworkRenderer','artworkLcd','artworkTiming','m7Receiver')):
            result[parts[3]] = int(parts[1],16)
    return result

def report(reference=None):
    a=inspect(BASE/'baseline_compile/firmware.elf')
    b=inspect(BASE/'pilot_compile/firmware.elf')
    before, after=frames('baseline_compile'),frames('pilot_compile')
    assert b['persistent_DRAM_sections']-a['persistent_DRAM_sections']<1024
    assert b['bin_bytes']<494144 and b['linked_metadata_layout']==[4,8,8,8,2048]
    shadow=ROOT/'experiments/artwork_pilot/.pio/shadow'
    main=(shadow/'src/main.cpp').read_text()
    assert 'shinoArtworkOfflineGuard=0' in main
    bridge=(shadow/'src/boot/FirstBootBridge.cpp').read_text()
    loop=bridge[bridge.index('void loop()'):bridge.index('} // namespace FirstBootBridge')]
    assert loop.index('server.handleClient()')<loop.index('artworkPilotAfterHttp()')
    gfx=ROOT/'experiments/artwork_pilot/.pio/libdeps/pilot_compile/GFX Library for Arduino/src'
    driver_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   (gfx/'Arduino_TFT.cpp',gfx/'databus/Arduino_HWSPI.cpp',gfx/'display/Arduino_ST7789.cpp',gfx/'font/glcdfont.h')}
    result={'scope':'paired equivalent offline full graphs; public inert OEM policy, unstarted volatile guard',
            'baseline':a,'pilot':b,
            'delta':{'bin_bytes':b['bin_bytes']-a['bin_bytes'],
                     'text_data_bss':{k:b['size_text_data_bss'][k]-a['size_text_data_bss'][k] for k in a['size_text_data_bss']},
                     'persistent_DRAM_bytes':b['persistent_DRAM_sections']-a['persistent_DRAM_sections']},
            'pilot_objects':objects(BASE/'pilot_compile/firmware.elf'),
            'compiler_frames_baseline':before,'compiler_frames_pilot':after,
            'driver_source_hashes':driver_hashes,
            'additional_renderer_heap_allocations':0,'renderer_scanline_bytes':192,
            'full_240_framebuffer_native':False,
            'timing':{'native_LCD_us':'NOT MEASURED',
                      '96px_cover_SPI_data_only_minimum_us_at_40MHz':3686.4,
                      'clear_top_SPI_data_only_minimum_us_at_40MHz':10752,
                      'max_tested_slice_9840_pixels_SPI_data_only_minimum_us_at_40MHz':3936,
                      'limitations':'Wire-time arithmetic excludes commands, glyph/SPI/SDK costs. No native high-water or elapsed LCD timing claim.'},
            'device_contacts':0,'device_writes':0}
    if reference:
        frozen=inspect(reference)
        assert frozen['bin_bytes']==446944 and frozen['bin_sha256']=='269fcf2be7e61b4f581f892f36c519cca5ebf1ef41759d9923d9df90aad682fa'
        result['frozen_M8_candidate']=frozen
        result['reference_note']='Existing ELF/BIN read only. Public graph uses inert OEM policy; paired delta isolates renderer. Pilot BIN is not an owner installation candidate.'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path)
    print(json.dumps(report(p.parse_args().reference),indent=2))
