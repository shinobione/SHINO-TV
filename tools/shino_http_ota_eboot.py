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
