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

def report(reference=None, host_report=None):
    baseline=inspect(BASE/'baseline_compile/firmware.elf')
    a=inspect(BASE/'previous_pilot_compile/firmware.elf')
    small=inspect(BASE/'scene128_compile/firmware.elf')
    b=inspect(BASE/'pilot_compile/firmware.elf')
    before, after=frames('previous_pilot_compile'),frames('pilot_compile')
    # Reviewed public prior graph must match the retained pre-scene evidence.
    assert a['bin_bytes']==443616 and a['persistent_DRAM_sections']==52936
    assert baseline['persistent_DRAM_sections']==52416
    assert baseline['objects']['m7Receiver']==1120
    # The scene buffer/captions/providers fit a 2KiB static increment envelope;
    # no extra renderer heap/image allocation. This is an offline budget, not
    # a measured physical heap/stack gate. Native LCD demonstration stays HOLD.
    assert 0 <= b['persistent_DRAM_sections']-a['persistent_DRAM_sections']<2048
    assert b['bin_bytes']<494144 and b['linked_metadata_layout']==[4,8,8,8,2048]
    assert small['linked_metadata_layout']==b['linked_metadata_layout']
    shadow=ROOT/'experiments/artwork_pilot/.pio/shadow'
    main=(shadow/'src/main.cpp').read_text()
    assert 'shinoArtworkOfflineGuard=0' in main
    bridge=(shadow/'src/boot/FirstBootBridge.cpp').read_text()
    loop=bridge[bridge.index('void loop()'):bridge.index('} // namespace FirstBootBridge')]
    assert loop.index('server.handleClient()')<loop.index('artworkPilotAfterHttp()')
    assert 'if (networkReady) artworkPilotAfterHttp();' in loop
    gfx=ROOT/'experiments/artwork_pilot/.pio/libdeps/pilot_compile/GFX Library for Arduino/src'
    driver_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                   (gfx/'Arduino_TFT.cpp',gfx/'databus/Arduino_HWSPI.cpp',gfx/'display/Arduino_ST7789.cpp',gfx/'font/glcdfont.h')}
    result={'scope':'previous PR40 ec20f32 versus scenes; equivalent offline public full graphs, unstarted volatile guard',
            'macro_disabled_receiver':baseline,'previous_pilot':a,'scene_128':small,'scene_160':b,
            'delta':{'bin_bytes':b['bin_bytes']-a['bin_bytes'],
                     'text_data_bss':{k:b['size_text_data_bss'][k]-a['size_text_data_bss'][k] for k in a['size_text_data_bss']},
                     'persistent_DRAM_bytes':b['persistent_DRAM_sections']-a['persistent_DRAM_sections']},
            'pilot_objects':objects(BASE/'pilot_compile/firmware.elf'),
            'compiler_frames_previous':before,'compiler_frames_scene':after,
            'compiler_frames_scene_128':frames('scene128_compile'),
            'compiler_frames_macro_disabled':frames('baseline_compile'),
            'driver_source_hashes':driver_hashes,
            'additional_renderer_heap_allocations':0,'renderer_scanline_bytes':448,
            'full_240_framebuffer_native':False,
            'timing':{'native_LCD_us':'NOT MEASURED',
                      '96px_previous_cover_data_only_us_at_40MHz':3686.4,
                      '128px_cover_data_only_us_at_40MHz':6553.6,
                      '160px_cover_data_only_us_at_40MHz':10240,
                      '128px_cover_row_slice_pixels':512,
                      '160px_cover_row_slice_pixels':800,
                      '128px_cover_row_data_only_us_at_40MHz':204.8,
                      '160px_cover_row_data_only_us_at_40MHz':320,
                      'title_row_slice_pixels':448,
                      'limitations':'Wire-time arithmetic excludes commands, glyph/SPI/SDK costs. No native high-water or elapsed LCD timing claim.'},
            'selected_scale':5,
            'scale_review':'Same 448-byte text/art row and linked DRAM for 4x/5x; 5x cover is 32 slices of 800 pixels, fits metadata below y176. No extra image.',
            'static_increment_budget_bytes':2048,
            'device_contacts':0,'device_writes':0}
    if host_report:
        h=json.loads(host_report.read_text(encoding='utf-8-sig'))
        assert h['scale']==5 and h['render_heap_allocations']==0
        pixels=h['max_slice_pixel_writes_upper_bound']
        assert pixels<=10000
        result['timing']['host_tested_max_slice_pixel_writes_upper_bound']=pixels
        result['timing']['max_slice_data_only_us_at_40MHz']=pixels*0.4
        result['timing']['max_transfer_requests_upper_bound']=h['max_slice_transfer_requests_upper_bound']
    if reference:
        frozen=inspect(reference)
        assert frozen['bin_bytes']==446944 and frozen['bin_sha256']=='269fcf2be7e61b4f581f892f36c519cca5ebf1ef41759d9923d9df90aad682fa'
        result['frozen_M8_candidate']=frozen
        result['reference_note']='Existing ELF/BIN read only. Public graph uses inert OEM policy; paired delta isolates renderer. Pilot BIN is not an owner installation candidate.'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path)
    p.add_argument('--host-report',type=Path)
    args=p.parse_args()
    print(json.dumps(report(args.reference,args.host_report),indent=2))
