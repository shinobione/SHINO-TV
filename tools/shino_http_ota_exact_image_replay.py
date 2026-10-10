"""Offline replay of exact owner BIN through real ShinoHttpOta Transfer/Core.

Simulated 4 MiB flash + RTC, ephemeral fake maintenance credential, NO device
contact, UART, Wi-Fi, owner secrets, or network. This is NOT native memory
qualification and cannot authorize a hardware installation.
"""
import argparse
import hashlib
import json
import secrets
import tempfile
import sys
import struct
import contextlib
from pathlib import Path

from shino_wifi_runner import build, IO, ROOT

sys.path.insert(0, str(ROOT / "companion"))
from shino_update import inspect, signature
from shino_http_ota_eboot import prepare_host
from m9_signed_release import validate_image
from m9_first_migration import arduino_crc


def replay(binary: Path, manifest: Path, expected_sha256: str, lab=None, current_binary=None):
    # Offline image and exact 4m2m segment/tag validation occurs before any
    # host lab is started. The actual BIN is never copied into the repository.
    m, raw = inspect(binary, manifest)
    if not isinstance(expected_sha256, str) or m["sha256"] != expected_sha256:
        raise ValueError("Exact expected release SHA-256 does not match")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Input BIN changed after inspection")

    # This key is synthetic and discarded immediately after the simulation.
    secret = secrets.token_hex(32)
    identity = {"device": m["device"], "maintenance_password": secret}
    nonce = "1" * 32
    with tempfile.TemporaryDirectory(prefix="shino-exact-core-replay-") as td:
        directory = Path(td)
        exe, env = lab if lab is not None else build(directory, ROOT / "tools/shino_http_ota_lab.cpp",prepare_host,defines=("SHINO_TEST_EBOOT=1",))
        io = IO(exe, dict(env, SHINO_TEST_DEVICE=m["device"]), secret)
        try:
            if io.command("ALIGN_PROBE") != "ALIGN_OK":
                raise ValueError("Host flash model accepted a forbidden unaligned word read")
            if current_binary is not None:
                current=Path(current_binary);validate_image(current.read_bytes())
                if io.command("LOAD_CURRENT "+current.resolve().as_posix())!="CURRENT_LOADED":
                    raise ValueError("Exact current image could not be loaded into RAM")
            else:
                other=("c" if m["build_id"]!="c"*64 else "d")*64
                if io.command("CURRENT_BUILD "+other)!="CURRENT_SET":raise ValueError("Model current build failed")
            tag = signature(identity, nonce, m)
            begin = f'BEGIN {len(raw)} {m["sha256"]} {m["build_id"]} {tag}'
            if io.command(begin) != "READY":
                raise ValueError("Core staging admission failed in offline replay")
            for at in range(0, len(raw), 512):
                block = raw[at:at + 512]
                io.write(block)
                if io.read() != f"ACK {at + len(block)}":
                    raise ValueError("Exact image rejected during simulated flash staging")
            if io.command("FINISH") != "STAGED":
                raise ValueError("Exact staged release did not pass CRC/segments/flash validation")
            report = io.report()
            if report["commit"] != 1 or not report["fs_preserved"] or not report["reserved_preserved"] or not report["current_preserved"] or report["received"] != len(raw):
                raise ValueError("Simulated eboot/FS/result acceptance failed")
            boot=None
            if "boot_model" in report:
                if io.command("BOOT")!="BOOT_MODEL_OK":raise ValueError("Pinned eboot copy/load model failed")
                boot=io.report()
                if not boot["boot_model"] or boot["commit"] or not boot["fs_preserved"] or not boot["reserved_preserved"] or boot["loaded_segments"]<1:
                    raise ValueError("Copied image or captured application entry failed")
        finally:
            io.close()
    return {
        "status": "EXACT_IMAGE_CORE_REPLAY_PASS_OFFLINE_ONLY",
        "sha256": expected_sha256,
        "bytes": len(raw),
        "flash_model": "4MiB_RAM_STRICT_4_BYTE_READ_ALIGNMENT",
        "core_flash_staged": True,
        "crc_segments_identity": "PASS",
        "simulated_eboot_command": True,
        "simulated_fs_preserved": True,
        "simulated_reserved_24KiB_preserved": True,
        "simulated_running_image_preserved_until_commit": True,
        "pinned_eboot_copy_load_model": boot is not None,
        "application_jump": "CAPTURED_NO_XTENSA_EXECUTION" if boot is not None else "NOT_RUN",
        "device_contact": 0,
        "physical_ota": "NOT_RUN",
        "native_stack_proven": False,
    }


def qualify(binary,manifest,expected_sha256,current_binary=None):
    """Exact full BIN: real Core, negative mutations, every sector interruption,
    legacy-reader regression and pinned eboot copy/load prefix. RAM only.
    """
    m,raw=inspect(binary,manifest)
    if m["sha256"]!=expected_sha256:raise ValueError("Wrong externally pinned SHA")
    secret=secrets.token_hex(32);identity=dict(device=m["device"],maintenance_password=secret)
    rows=[]
    with tempfile.TemporaryDirectory(prefix="shino-full-core-") as td:
        directory=Path(td);new=directory/"new";new.mkdir();old=directory/"old";old.mkdir()
        lab=build(new,ROOT/"tools/shino_http_ota_lab.cpp",prepare_host,defines=("SHINO_TEST_EBOOT=1",))
        legacy=build(old,ROOT/"tools/shino_http_ota_lab.cpp",lambda h:prepare_host(h,legacy=True),
                     defines=("SHINO_TEST_EBOOT=1","SHINO_TEST_LEGACY_FLASH_READER=1"))
        positive=replay(binary,manifest,expected_sha256,lab,current_binary)
        @contextlib.contextmanager
        def trial(name,which=lab):
            exe,env=which;io=IO(exe,dict(env,SHINO_TEST_DEVICE=m["device"]),secret)
            try:
                if current_binary is not None:
                    assert io.command("LOAD_CURRENT "+Path(current_binary).resolve().as_posix())=="CURRENT_LOADED"
                else:assert io.command("CURRENT_BUILD "+("c" if m["build_id"]!="c"*64 else "d")*64)=="CURRENT_SET"
                yield io
                report=io.report()
                assert not report["commit"] and not report["running"] and not report["boot_model"],name
                assert report["fs_preserved"] and report["reserved_preserved"] and report["current_preserved"],name
                assert io.command("BOOT")=="ERR",name
                assert io.report()["boot_writes"]==io.report()["boot_erase"]==0,name
                rows.append(dict(name=name,**report))
            finally:io.close()
        def begin(io,release):
            p=signature(identity,"1"*32,release)
            assert io.command(f'BEGIN {release["bytes"]} {release["sha256"]} {release["build_id"]} {p}')=="READY"
        def upload(io,data):
            for at in range(0,len(data),512):
                block=data[at:at+512];io.write(block);assert io.read()==f"ACK {at+len(block)}"
        with trial("legacy_reader_exact_valid_bin",legacy) as io:
            begin(io,m);upload(io,raw);assert io.command("FINISH")=="ERR"
            assert io.report()["rejected_word_reads"]>=1
        # Correctly authenticated bad CRC, metadata, header and segment checksum
        # must be rejected independently of the streaming SHA check.
        for name in ("corrupt_stream","bad_crc","bad_metadata_size","bad_checksum",
                     "bad_entry","flash_read_fault","staging_bit_flip","full_abort",
                     "floor_before_commit","floor_during_readback"):
            with trial(name) as io:
                data=bytearray(raw);release=dict(m)
                if name=="corrupt_stream":data[-32]^=1
                elif name=="bad_crc":data[0x1014]^=1
                elif name=="bad_metadata_size":struct.pack_into("<I",data,0x1010,len(data)-16)
                elif name=="bad_checksum":
                    data[-1]^=1;struct.pack_into("<I",data,0x1014,arduino_crc(data))
                elif name=="bad_entry":
                    struct.pack_into("<I",data,0x1004,0x40120000)
                    struct.pack_into("<I",data,0x1014,arduino_crc(data))
                if name in ("bad_crc","bad_metadata_size","bad_checksum","bad_entry"):
                    release["sha256"]=hashlib.sha256(data).hexdigest()
                begin(io,release);upload(io,data)
                if name=="flash_read_fault":io.command("FAULT read")
                if name=="staging_bit_flip":io.command("CORRUPT 6000")
                if name=="floor_before_commit":io.command("BUDGET 60000 50000 2047 1")
                if name=="floor_during_readback":io.command("HEALTH_AFTER 64")
                if name=="full_abort":io.command("ABORT")
                else:assert io.command("FINISH")=="ERR"
        for fault in ("erase","write"):
            with trial(fault+"_fault") as io:
                begin(io,m);io.command("FAULT "+fault)
                for at in range(0,8192,512):
                    io.write(raw[at:at+512]);answer=io.read()
                    if answer=="ERR":break
                assert answer=="ERR"
        # All Core sector flush boundaries, plus partial first/last packet,
        # last byte and every segment's final byte. Historical 512B fixture
        # matrix is also retained in test_shino_http_ota.py.
        cuts={0,4,511,512,4095,4096,4097,len(raw)//2,len(raw)-1,len(raw)}
        cuts.update(range(4096,len(raw),4096))
        for offset in (0,0x1000):
            at=offset+8
            for _ in range(raw[offset+1]):
                count=struct.unpack_from("<I",raw,at+4)[0];at+=8+count
                cuts.update((at-1,at))
        for cut in sorted(cuts):
            with trial("interrupt_"+str(cut)) as io:
                begin(io,m);upload(io,raw[:cut]);io.command("ABORT")
        return dict(status="EXACT_IMAGE_QUALIFICATION_PASS_OFFLINE_ONLY",positive=positive,
                    cases=len(rows),interruption_boundaries=len(cuts),legacy_valid_image_rejected=True,
                    actual_pinned_core=True,pinned_eboot_copy_load=True,
                    flash_and_resources="RAM_AND_MOCKED",native_stack_proven=False,
                    device_contacts=0,physical="NOT_RUN",rows=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bin", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--current-bin",type=Path)
    p.add_argument("--qualify",action="store_true")
    args = p.parse_args()
    try:
        result=(qualify(args.bin,args.manifest,args.expected_sha256,args.current_bin) if args.qualify else
                replay(args.bin,args.manifest,args.expected_sha256,current_binary=args.current_bin))
        print(json.dumps(result,indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as e:
        print("EXACT_IMAGE_CORE_REPLAY_HOLD: " + type(e).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
