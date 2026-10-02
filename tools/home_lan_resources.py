"""Exact linked P0/P1 resources and pinned SDK storage evidence, offline only."""
import hashlib,json,re
from pathlib import Path
from v07_pinned_core_probe import core_root
from v08_m8_stack_gate import run_tool
from v08_m8r_memory import inspect
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'experiments/home_lan/.pio/build'

def report():
    core=core_root()
    paths=('tools/sdk/ld/eagle.flash.4m3m.ld','cores/esp8266/core_esp8266_phy.cpp',
           'cores/esp8266/core_esp8266_main.cpp','libraries/ESP8266WiFi/src/ESP8266WiFiSTA.cpp',
           'libraries/ESP8266WiFi/src/ESP8266WiFiGeneric.cpp','tools/sdk/include/user_interface.h',
           'tools/platformio-build.py','tools/sdk/lib/NONOSDK22x_190703/libmain.a')
    hashes={p:hashlib.sha256((core/p).read_bytes()).hexdigest() for p in paths}
    expected=json.loads((ROOT/'tools/home_lan_storage_manifest.json').read_text(encoding='utf-8'))
    assert hashes==expected,'Pinned P1 Core/SDK storage source or archive drift'
    ld=(core/paths[0]).read_text(encoding='utf-8'); phy=(core/paths[1]).read_text(encoding='utf-8'); builder=(core/paths[-2]).read_text(encoding='utf-8')
    assert '_FS_start = 0x40300000' in ld and '_FS_end = 0x405FA000' in ld and '_EEPROM_start = 0x405fb000' in ld
    assert 'return flashchip->chip_size/SPI_FLASH_SEC_SIZE - 4;' in phy
    assert '("SDK22x_190703", "NONOSDK22x_190703")' in builder
    graphs={n:inspect(BUILD/n/'firmware.elf') for n in ('p0_compile','p1_compile','p1_oem_compile')}
    base,candidate=graphs['p0_compile'],graphs['p1_compile']
    assert base['bin_bytes']==449072 and base['persistent_DRAM_sections']==54016,'P0 matched baseline drift'
    frames={}
    for file in (BUILD/'p1_compile').rglob('*.su'):
        if file.name not in ('HomeLan.cpp.su','FirstBootBridge.cpp.su'):continue
        for row in file.read_text(encoding='utf-8').splitlines():
            m=re.match(r'^.*?:\d+:\d+:(.*?)\t(\d+)\t(.*)$',row)
            if m and ('HomeLan::' in m[1] or '::_parseRequest(' in m[1] or '::handleClient(' in m[1]):
                frames[m[1]]={'bytes':int(m[2]),'kind':m[3]}
    asm=run_tool('objdump','-d','-C',BUILD/'p1_compile/firmware.elf')
    funcs={}
    spans=list(re.finditer(r'^([0-9a-f]+) <(.+)>:$',asm,re.M))
    for i,m in enumerate(spans):
        if m[2] in ('wifi_station_set_config','wifi_station_set_config_current','wifi_station_get_config_default','system_param_save_with_protect','user_rf_cal_sector_set','wifi_station_ap_number_set'):
            funcs[m[2]]=asm[m.start():spans[i+1].start() if i+1<len(spans) else len(asm)]
    assert len(funcs)==6
    # Stripped SDK helpers share the symbol range of station_ap_number_set.
    helper=funcs['wifi_station_ap_number_set']
    assert 'system_param_save_with_protect' in helper and 'system_param_load' in helper
    assert re.search(r'addi\s+a2, a2, -3',helper),'SDK params start at chip sectors minus 3'
    assert re.search(r'movi.n\s+a3, 1',funcs['wifi_station_set_config'])
    assert re.search(r'movi.n\s+a3, 0',funcs['wifi_station_set_config_current'])
    out={'scope':'public guarded full links; no installable owner image or device measurement',
         'graphs':graphs,'delta':{'bin_bytes':candidate['bin_bytes']-base['bin_bytes'],
             'static_DRAM_bytes':candidate['persistent_DRAM_sections']-base['persistent_DRAM_sections']},
         'pinned_core_storage_hashes':hashes,'sdk':'NONOSDK22x_190703, NONOSDK=0x22100; same SDK as P0',
         'layout_offsets':{'application_and_OTA_end':0x100000,'unmounted_FS_start':0x100000,'unmounted_FS_end':0x3fa000,
                           'EEPROM_start_unused':0x3fb000,'RF_calibration':0x3fc000,'SDK_system_start':0x3fd000,'SDK_system_end':0x400000},
         'linked_storage_functions':{name:hashlib.sha256(body.encode()).hexdigest() for name,body in funcs.items()},
         'sdk_disassembly_checks':{'shared_helper_protected_save_and_load':True,'sector_start_chip_minus_3':True,'persistent_selector_1_current_selector_0':True},
         'compiler_frames_not_high_water':frames,
         'new_persistent_application_heap_allocations':0,'provisioning_body_cap_bytes':99,
         'sdk_station_config_bytes':112,'physical_heap':'NOT RUN','physical_largest_block':'NOT RUN',
         'physical_stack':'NOT RUN','physical_power_loss_storage':'NOT RUN','physical_OEM_return_after_storage':'NOT RUN',
         'device_contacts':0,'device_writes':0}
    # Historical M8 margins are arithmetic warnings, not P1 heap predictions.
    delta=out['delta']['static_DRAM_bytes']
    out['historical_M8_only_arithmetic']={'prior_settled_heap':16384,'prior_settled_block':12496,
        'subtract_P0_and_P1_static_only':1600+delta,
        'heap_after_static_subtraction_only':16384-1600-delta,
        'block_after_static_subtraction_only_NOT_allocator_prediction':12496-1600-delta,
        'SDK_AP_STA_extra_cost':'unknown; physical measurement required before installation'}
    assert candidate['bin_bytes']<494144 and out['delta']['static_DRAM_bytes']<2048
    return out
if __name__=='__main__':print(json.dumps(report(),indent=2))
