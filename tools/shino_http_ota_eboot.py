"""Pinned eboot copy and load prefix with RAM SPI seams and a captured jump.

No Xtensa execution, native timings, power-loss guarantee or device contact.
"""
import hashlib
import json
from shino_wifi_runner import ROOT
from v07_pinned_core_probe import core_root


def prepare_host(host,legacy=False):
    raw=(core_root()/"bootloaders/eboot/eboot.c").read_bytes().replace(b"\r\n",b"\n")
    pins=json.loads((ROOT/"tools/m9_signed_core_sources.json").read_text())
    if hashlib.sha256(raw).hexdigest()!=pins["bootloaders/eboot/eboot.c"]:
        raise ValueError("Wrong pinned eboot")
    text=raw.decode()
    first=text.index("uint8_t read_flash_byte(")
    byte_reader=text[first:text.index("unsigned char __attribute__",first)]
    first=text.index("int copy_raw(")
    copy=text[first:text.index("\nint main()",first)]
    first=text.index("int load_app_from_flash_raw(")
    prefix=text[first:text.index('    asm volatile(""',first)]
    # Only the final CPU stack setup/jump is replaced. SPIRead redirects loaded
    # physical DRAM/IRAM addresses into host RAM; application code is not run.
    loader=prefix+"    modelEntry=image_header.entry;return 0;\n}\n"
    (host/"pinned_http_eboot.inc").write_text(byte_reader+copy+loader,encoding="utf-8")
    flash_raw=(core_root()/"bootloaders/eboot/flash.h").read_bytes().replace(b"\r\n",b"\n")
    if hashlib.sha256(flash_raw).hexdigest()!="bdc9157f468fea2acbc610f49a8084c761cd83f2b3efee0bb488216e9da90b5e":
        raise ValueError("Wrong pinned Core3.1.2 eboot flash header")
    flash_header=flash_raw.decode()
    (host/"pinned_boot_flash.h").write_text(flash_header.replace(
        "#include <spi_flash_geometry.h>","#ifndef FLASH_SECTOR_SIZE\n#define FLASH_SECTOR_SIZE 4096\n#endif"),encoding="utf-8")
    if legacy:
        body=(ROOT/"ota/firmware/ShinoHttpOta.h").read_text(encoding="utf-8")
        start=body.index("    __attribute__((noinline)) bool read(")
        end=body.index("    __attribute__((noinline)) bool stagedImage()",start)
        # Restore only the old reader, retaining every other validation rule.
        old='''    __attribute__((noinline)) bool read(uint32_t at,void* out,size_t n){
        return at<=release_.bytes&&n<=release_.bytes-at&&
            ESP.flashRead(stage_+at,reinterpret_cast<uint32_t*>(out),n);
    }
'''
        (host/"legacy_receiver.h").write_text(body[:start]+old+body[end:],encoding="utf-8")


def prepare_safety_host(host):
    """Observation/fault seams in disposable copies, never the installed Core.

    Core control flow, buffer branch, receiver predicates and eboot copy are
    retained. Injected budget observations do not add production safety checks.
    """
    prepare_host(host)
    core=host.parent/"core"
    pins=json.loads((ROOT/"tools/m9_signed_core_sources.json").read_text())
    upstream=core_root()
    for name in ("bootloaders/eboot/eboot_command.c", "bootloaders/eboot/eboot_command.h",
                 "tools/sdk/ld/eagle.flash.4m2m.ld"):
        raw=(upstream/name).read_bytes().replace(b"\r\n",b"\n")
        if hashlib.sha256(raw).hexdigest()!=pins[name]:raise ValueError("Wrong pinned safety source: "+name)
    def replace_once(text,old,new):
        if text.count(old)!=1:raise ValueError("Safety seam drift: "+old)
        return text.replace(old,new)
    body=(core/"Updater.cpp").read_text()
    body=replace_once(body,"new (std::nothrow) uint8_t[_bufferSize]","safety_alloc(_bufferSize)")
    body=replace_once(body,"delete[] _buffer;","safety_free(_buffer);")
    (core/"Updater.cpp").write_text(body,encoding="utf-8")
    header=(core/"Updater.h").read_text()
    header=replace_once(header,"  private:","  private:\n    friend struct SafetyProbe;")
    (core/"Updater.h").write_text(header,encoding="utf-8")
    # Same 32 word writes and CRC implementation; each hardware store is a seam.
    body=(core/"eboot_command.c").read_text()
    body=replace_once(body,"RTC_MEM[i] = src[i];","shino_test_rtc_write(i, src[i]);")
    for field in ("magic","crc32"):
        old=f"RTC_MEM[offsetof(struct eboot_command, {field}) / sizeof(uint32_t)] = 0;"
        body=replace_once(body,old,f"shino_test_rtc_write(offsetof(struct eboot_command, {field}) / sizeof(uint32_t), 0);")
    (core/"eboot_command.c").write_text("void shino_test_rtc_write(unsigned, unsigned);\n"+body,encoding="utf-8")
    (host/"flash_hal.h").write_text("#pragma once\n#define FS_start safety_fs_start\n#define FS_end 0x405FA000u\n",encoding="utf-8")
    arduino=(ROOT/"experiments/m9_signed_ota/host/Arduino.h").read_text()
    declarations='''
uint32_t safety_heap();
extern uint32_t safety_fs_start;
void safety_phase(const char*);
uint8_t* safety_alloc(size_t);
void safety_free(uint8_t*);
bool safety_before(const char*,uint32_t,size_t);
void safety_after(const char*,uint32_t);
'''
    arduino=replace_once(arduino,"#include <cstdio>","#include <cstdio>\n"+declarations)
    arduino=replace_once(arduino,"return heap;","return safety_heap();")
    arduino=replace_once(arduino,"++readCalls;if(failRead",'++readCalls;if(!safety_before("stage_read",at,n)||failRead')
    arduino=replace_once(arduino,"std::memcpy(out,flash.data()+at,n);return true;",'std::memcpy(out,flash.data()+at,n);safety_after("stage_read",at);return true;')
    arduino=replace_once(arduino,"++writeCalls;if(failWrite",'++writeCalls;if(!safety_before("stage_write",at,n)||failWrite')
    arduino=replace_once(arduino,"std::memcpy(flash.data()+at,data,n);return true;",'std::memcpy(flash.data()+at,data,n);safety_after("stage_write",at);return true;')
    arduino=replace_once(arduino,"++eraseCalls;if(failErase",'++eraseCalls;if(!safety_before("stage_erase",s*4096,4096)||failErase')
    arduino=replace_once(arduino,"flash.begin()+(s+1)*4096,0xff);return true;",'flash.begin()+(s+1)*4096,0xff);safety_after("stage_erase",s*4096);return true;')
    (host/"Arduino.h").write_text(arduino,encoding="utf-8")
    body=(ROOT/"ota/firmware/ShinoHttpOta.h").read_text()
    for old,new in (
        ("    if(workspace.busy)return false;",'    safety_phase("hmac");\n    if(workspace.busy)return false;'),
        ("        release_=r;stage_=",'        safety_phase("stage_begin");\n        release_=r;stage_='),
        ("    bool add(uint8_t* p,size_t n,Budget b){",'    bool add(uint8_t* p,size_t n,Budget b){\n        safety_phase("receive");'),
        ("    __attribute__((noinline)) bool stagedImage(){",'    __attribute__((noinline)) bool stagedImage(){\n        safety_phase("sha_crc");'),
        ("    __attribute__((noinline)) bool segments(uint32_t off){",'    __attribute__((noinline)) bool segments(uint32_t off){\n        safety_phase(off?"app_segments":"boot_segments");'),
        ("        if(!core_.end(false))return fail();",'        safety_phase("commit");\n        if(!core_.end(false))return fail();'),
    ):body=replace_once(body,old,new)
    (host/"safety_receiver.h").write_text(body,encoding="utf-8")
