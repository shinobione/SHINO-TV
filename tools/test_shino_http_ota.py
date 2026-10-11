"""Native Core RAM fault matrix and exact Windows HMAC contract, no device."""
import contextlib
import argparse
import hashlib
import json
import os
import secrets
import struct
import sys
import tempfile
from pathlib import Path
from shino_wifi_runner import build,IO,ROOT
from m9_signed_fixture_image import inert_image
from m9_first_migration import arduino_crc
sys.path.insert(0,str(ROOT/"companion"))
from shino_update import signature,inspect
from shino_http_ota_exact_image_replay import replay
from shino_http_ota_eboot import prepare_safety_host


def fixture(build_id="b"*64,device="0123456789abcdef"):
    raw=bytearray(inert_image());tag=f"SHINO-HTTP-OTA-1|{device}|{build_id}|4m2m|APP_ONLY".encode()
    raw[0x2000:0x2000+len(tag)]=tag;raw[0x1010:0x1018]=bytes(8)
    checksum=0xef
    for x in raw[0x1010:0x1020]+raw[0x1028:len(raw)-8]:checksum^=x
    raw[-1]=checksum;struct.pack_into("<II",raw,0x1010,len(raw),arduino_crc(raw));return bytes(raw)


def run():
    with tempfile.TemporaryDirectory(prefix="shino-http-ota-ram-") as td:
        directory=Path(td);exe,env=build(directory,ROOT/"tools/shino_http_ota_lab.cpp")
        password=secrets.token_hex(32);identity=dict(device="0123456789abcdef",maintenance_password=password)
        raw=fixture();m=dict(schema=1,family="SHINO-StageA",layout="4m2m",protocol="shino-http-ota-1",device=identity["device"],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),build_id="b"*64)
        (directory/"firmware.bin").write_bytes(raw);(directory/"release.json").write_text(json.dumps(m),encoding="utf-8")
        assert inspect(directory/"firmware.bin",directory/"release.json")== (m,raw)
        exact = replay(directory/"firmware.bin", directory/"release.json", m["sha256"], lab=(exe,env))
        assert exact["status"] == "EXACT_IMAGE_CORE_REPLAY_PASS_OFFLINE_ONLY"
        rows=[]
        @contextlib.contextmanager
        def trial(name):
            io=IO(exe,env,password)
            try:
                yield io;row=io.report();assert row["fs_preserved"],name;rows.append(dict(name=name,**row))
            finally:io.close()
        def begin(io,release=m,proof=None):
            p=proof or signature(identity,"1"*32,release)
            return io.command(f'BEGIN {release["bytes"]} {release["sha256"]} {release["build_id"]} {p}')
        def upload(io,data=raw):
            for at in range(0,len(data),512):
                io.write(data[at:at+512]);assert io.read()==f"ACK {min(at+512,len(data))}"
        with trial("hmac_workspace_guard") as io:
            assert io.command("PROOF_GUARD")=="GUARD_OK"
            assert io.report()["writes"]==io.report()["erase"]==io.report()["commit"]==0
        # Independent Windows HMAC covers the decimal field's width transitions.
        for size in (64000,99999,100000,999999,1000000,0xFEFF0):
            with trial("hmac_size_"+str(size)) as io:
                release=dict(m,bytes=size);assert begin(io,release)=="READY"
                io.command("ABORT");assert io.report()["writes"]==io.report()["erase"]==io.report()["commit"]==0
        with trial("valid") as io:
            assert io.command("ALIGN_PROBE")=="ALIGN_OK", "Mock must reject native unaligned uint32_t flash reads"
            assert begin(io)=="READY";upload(io);assert io.command("FINISH")=="STAGED";assert io.report()["commit"]==1
        for name in ("wrong_hmac","oversize","wrong_build","low_heap","low_block","low_stack","observed_stack_1632","fragmented","low_admission"):
            with trial(name) as io:
                release=dict(m);p=None
                if name=="wrong_hmac":p="0"*64
                if name=="oversize":release["bytes"]=0xFEFF1
                if name=="wrong_build":release["build_id"]="a"*64
                if name.startswith("low") or name in ("fragmented","observed_stack_1632"):
                    values={"low_heap":"20479 50000 3248 1","low_block":"60000 16383 3248 1","low_stack":"60000 50000 2047 1","observed_stack_1632":"60000 50000 1632 1","fragmented":"60000 50000 3248 26","low_admission":"25599 50000 3248 1"}
                    io.command("BUDGET "+values[name])
                assert begin(io,release,p)=="ERR";assert io.report()["writes"]==io.report()["erase"]==0
        with trial("floor_after_hmac") as io:
            io.command("HEALTH 0");assert begin(io)=="ERR"
            assert io.report()["writes"]==io.report()["erase"]==io.report()["commit"]==0
        for name in ("bad_hash","bad_crc","wrong_identity","flash_corrupt","read_fail","erase_fail","write_fail","floor_during_transfer","floor_before_commit","deadline_during_verification","extra_bytes","gzip"):
            with trial(name) as io:
                data=bytearray(raw);release=dict(m)
                if name=="bad_hash":data[-32]^=1
                if name=="bad_crc":data[0x1014]^=1;release["sha256"]=hashlib.sha256(data).hexdigest()
                if name=="wrong_identity":data=bytearray(fixture("c"*64));release["sha256"]=hashlib.sha256(data).hexdigest()
                assert begin(io,release)=="READY"
                if name in ("erase_fail","write_fail"):
                    io.command("FAULT "+name.split("_")[0]);answer=""
                    for at in range(0,4608,512):io.write(data[at:at+512]);answer=io.read()
                    assert answer=="ERR"
                elif name in ("floor_during_transfer","gzip"):
                    if name=="floor_during_transfer":io.command("BUDGET 20479 50000 3248 1")
                    else:data[0]=0x1f
                    io.write(data[:512]);assert io.read()=="ERR"
                else:
                    upload(io,data)
                    if name=="flash_corrupt":io.command("CORRUPT 6000")
                    if name=="read_fail":io.command("FAULT read")
                    if name=="floor_before_commit":io.command("BUDGET 60000 50000 2047 1")
                    if name=="deadline_during_verification":io.command("HEALTH 0")
                    if name=="extra_bytes":io.write(b"extra");assert io.read()=="ERR"
                    else:assert io.command("FINISH")=="ERR"
                report=io.report();assert not report["commit"] and not report["running"],name
        cuts=0
        for cut in range(0,len(raw)+512,512):
            with trial("interruption_"+str(cut)) as io:
                assert begin(io)=="READY";upload(io,raw[:min(cut,len(raw))]);io.command("ABORT")
                assert not io.report()["commit"] and not io.report()["running"];cuts+=1
        return dict(cases=len(rows),interruption_boundaries=cuts,exact_image_replay=exact["status"],actual_pinned_core=True,actual_windows_hmac=True,
                    core_buffer=4096,flash_and_rtc="RAM_MOCK",device_contacts=0,rows=rows)

def safety_gate(binary=None,manifest=None):
    from unittest.mock import patch
    # The native executable has only stdin/file/RAM SPI seams. Block Python
    # sockets and HTTP constructors too, including the real updater fallback.
    with contextlib.ExitStack() as guards:
        blocked=[guards.enter_context(patch(name,side_effect=AssertionError("Offline test attempted I/O")))
                 for name in ("socket.socket","socket.create_connection","socket.getaddrinfo",
                              "http.client.HTTPConnection","shino_update.Transport")]
        try:
            return _safety_gate(binary,manifest)
        finally:
            for guard in blocked:guard.assert_not_called()


def _safety_gate(binary=None,manifest=None):
    """Pinned Core/eboot fault matrix. All images, flash and RTC are inert RAM.

    PASS means the assertions and risk detections ran; HOLD means this cannot
    establish native memory floors or authorize a real OTA transaction.
    """
    from shino_update import signature,inspect
    from v07_pinned_core_probe import core_root
    import re
    core=core_root()
    if '"version": "3.30102.0"' not in (core/"package.json").read_text():raise ValueError("Wrong Core package")
    layout=(core/"tools/sdk/ld/eagle.flash.4m2m.ld").read_text()
    linked={name:int(value,16) for name,value in re.findall(r"PROVIDE\s*\(\s*(_FS_start|_FS_end|_EEPROM_start)\s*=\s*(0x[0-9a-fA-F]+)",layout)}
    assert linked==dict(_FS_start=0x40400000,_FS_end=0x405FA000,_EEPROM_start=0x405FB000)
    assert linked["_FS_start"]-0x40200000==0x200000 and linked["_FS_end"]-0x40200000==0x3FA000
    if (binary is None)!=(manifest is None):raise ValueError("Both public BIN and manifest required")
    if binary is None:
        raw=fixture();m=dict(schema=1,family="SHINO-StageA",layout="4m2m",protocol="shino-http-ota-1",
            device="0123456789abcdef",bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),build_id="b"*64)
    else:
        m,raw=inspect(binary,manifest)
        # The only supplied image accepted by this gate is the inert public
        # graph. No owner-private image/identity is part of this command.
        if m["device"]!="0123456789abcdef" or m["build_id"]!="a"*64:
            raise ValueError("Public inert build required")
        from shino_http_ota_build import elf_layout
        assert elf_layout(Path(binary).with_suffix(".elf"))==linked
    stage=0x200000-((len(raw)+4095)&~4095)
    sectors=(len(raw)+4095)//4096
    secret=secrets.token_hex(32);identity=dict(device=m["device"],maintenance_password=secret)
    begin_text=f'BEGIN {len(raw)} {m["sha256"]} {m["build_id"]} {signature(identity,"1"*32,m)}'
    rows=[];floor_rows=[];counts=dict(staging=0,rtc=0,rtc_clear=0,eboot=0,begin_end=0)
    with tempfile.TemporaryDirectory(prefix="shino-ota-safety-") as td:
        directory=Path(td)
        from littlefs import LittleFS
        from m9_stage2_fs_candidate import reviewed_source,inspect_contents
        fs_files=reviewed_source(ROOT/"firmware/data")
        fs=LittleFS(block_size=8192,block_count=0x1FA000//8192,read_size=256,prog_size=256,disk_version=0x00020000)
        for folder in ("/web","/web/css","/web/js"):fs.mkdir(folder)
        for name,body in sorted(fs_files.items()):
            with fs.open("/"+name,"wb") as output:output.write(body)
        fs_bytes=bytes(fs.context.buffer);fs.unmount()
        fs_inventory=inspect_contents(fs_bytes,fs_files)
        fs_file=directory/"fs.inert";fs_file.write_bytes(fs_bytes)
        lab=build(directory,ROOT/"tools/shino_http_ota_lab.cpp",prepare_safety_host,
            defines=("SHINO_TEST_EBOOT=1","SHINO_TEST_OTA_SAFETY=1"))
        # Synthetic prior application, not installed B3: distinct tag and
        # non-erased bytes, same bootloader sector. Never executed on Xtensa.
        old=bytearray(raw);old_id=("c" if m["build_id"]!="c"*64 else "d")*64
        tag=f'SHINO-HTTP-OTA-1|{m["device"]}|{m["build_id"]}|4m2m|APP_ONLY'.encode()
        at=old.index(tag)+len(f'SHINO-HTTP-OTA-1|{m["device"]}|')
        old[at:at+64]=old_id.encode();old_file=directory/"current.inert";old_file.write_bytes(old)
        @contextlib.contextmanager
        def trial(name,different_boot=False,windows=False):
            exe,env=lab
            io=IO(exe,dict(env,SHINO_TEST_DEVICE="1123456789abcdef" if windows else m["device"]),secret)
            try:
                current_source=windows_current if windows else old_file
                assert io.command("LOAD_CURRENT "+current_source.as_posix())=="CURRENT_LOADED"
                if different_boot:
                    # LOAD_CURRENT with a differing first-sector byte exercises
                    # Core's real sector-zero rewrite rather than inventing a
                    # bootloader protection it does not have.
                    alternate=directory/"different-boot.inert"
                    changed=bytearray(current_source.read_bytes());changed[64]^=1;alternate.write_bytes(changed)
                    assert io.command("LOAD_CURRENT "+alternate.as_posix())=="CURRENT_LOADED"
                assert io.command("LOAD_FS "+fs_file.as_posix())=="FS_LOADED"
                yield io
                row=io.report()
                assert row["fs_preserved"] and row["reserved_preserved"],name
                # Neither success receipts nor unknown flash permit a retry.
                unknown=row["cut_seen"] or row.get("boot_erase",0)>0 or row.get("boot_writes",0)>0
                rows.append(dict(name=name,retry_allowed=False,
                    transaction_state="UNKNOWN_NO_RETRY" if unknown and not row.get("boot_model") else
                        "SIMULATED_BOOT_ONLY" if row.get("boot_model") else "NO_BOOT_ACCEPTANCE",**row))
            finally:io.close()
        def begin(io):
            assert io.command(begin_text)=="READY"
            row=io.report();assert row["core_stage"]==row["receiver_stage"]==stage
            assert row["allocation_requested"]==4096 and row["allocation_live"]==4096
        def upload(io):
            for pos in range(0,len(raw),512):
                chunk=raw[pos:pos+512];io.write(chunk);answer=io.read()
                if answer in ("CUT","ERR"):return answer
                assert answer==f"ACK {pos+len(chunk)}"
            return "FULL"
        def staged(io):
            begin(io);assert upload(io)=="FULL";assert io.command("FINISH")=="STAGED"
        # Natural (unforced) pinned Core branch at >8192 bytes; low-memory
        # 256-byte buffer is valid Core behaviour, never SHINO admission PASS.
        for heap,requested in ((8192,256),(8193,4096),(29560,4096),(25600,4096)):
            with trial("core_buffer_"+str(heap)) as io:
                io.command(f"RESOURCES {heap} 28152 2272 6")
                assert io.command(f"CORE_BEGIN {len(raw)}")=="READY"
                row=io.report();assert row["allocation_requested"]==requested
                assert row["heap"]==heap-requested-16 and row["core_stage"]==stage
                assert io.command("CORE_ABORT")=="ABORTED" and io.report()["allocation_live"]==0
        with trial("shino_rejects_256_path") as io:
            io.command("RESOURCES 8192 8000 2272 6")
            assert io.command(begin_text)=="ERR" and io.report()["allocation_requested"]==0
        with trial("allocation_failure") as io:
            io.command("ALLOC_FAIL");assert io.command(begin_text)=="ERR"
            row=io.report();assert row["allocation_live"]==row["writes"]==row["erase"]==row["commit"]==0
        for mode in ("before","after"):
            with trial("begin_allocation_cut_"+mode) as io:
                io.command("CUT allocation 0 "+mode);assert io.command(begin_text)=="CUT"
                row=io.report();assert row["cut_seen"] and row["current_preserved"] and not row["commit"]
                counts["begin_end"]+=1
        # Boundary values and geometry, including exact maximum 4m2m image.
        for size in (64000,65536,65537,407552,0xFEFF0):
            with trial("geometry_"+str(size)) as io:
                release=dict(m,bytes=size);proof=signature(identity,"1"*32,release)
                assert io.command(f'BEGIN {size} {m["sha256"]} {m["build_id"]} {proof}')=="READY"
                r=io.report();assert r["core_stage"]==r["receiver_stage"]==0x200000-((size+4095)&~4095)
                assert r["core_stage"]>=((len(old)+4095)&~4095)+4096
                io.command("ABORT");assert io.report()["allocation_live"]==0
        with trial("wrong_linked_geometry") as io:
            io.command("LAYOUT 1078984704") # 0x40500000; deliberate 4m1m-like mismatch
            assert io.command(begin_text)=="READY"
            r=io.report();assert r["core_stage"]!=r["receiver_stage"]
            assert r["writes"]==0;io.command("ABORT")
        for value in (0,1,3):
            with trial("header_flash_mode_mismatch_"+str(value)) as io:
                io.command("MODE "+str(value));begin(io);assert upload(io)=="FULL"
                assert io.command("FINISH")=="ERR"
                r=io.report();assert not r["commit"] and r["current_preserved"] and r["allocation_live"]==0
        with trial("safe_model_all_phases") as io:
            io.command("RESOURCES 29560 28152 2272 6");staged(io)
            r=io.report();assert not r["unsafe_seen"] and r["heap_min_model"]==25448
            assert {"hmac","stage_begin","allocation","receive","sha_crc","boot_segments","app_segments","commit"}<=r["observations"].keys()
            assert r["allocation_live"]==0 and r["current_preserved"]
            assert io.command("BOOT_SKIP_PROBE")=="SKIPPED"
            assert io.command("BOOT")=="BOOT_MODEL_OK" and not io.report()["commit"]
            after_fs=directory/"fs-after.inert"
            assert io.command("DUMP_FS "+after_fs.as_posix())=="FS_DUMPED"
            assert after_fs.read_bytes()==fs_bytes
            assert inspect_contents(after_fs.read_bytes(),fs_files)==fs_inventory
        # Inject floor breaches at actual phase boundaries. These observations
        # do NOT patch in checks absent from the running B3 source.
        for phase in ("hmac","stage_begin","allocation","receive","sha_crc","boot_segments","app_segments","commit"):
            for field,pressure in (("heap","40000 0 0 0"),("block","0 34000 0 0"),
                                   ("stack","0 0 1201 0"),("frag","0 0 0 26")):
                with trial("floor_"+phase+"_"+field) as io:
                    io.command(f"PRESSURE {phase} {pressure}")
                    answer=io.command(begin_text)
                    if answer=="READY":
                        answer=upload(io)
                        if answer=="FULL":answer=io.command("FINISH")
                    r=io.report();assert r["unsafe_seen"]
                    detected=phase in ("allocation","receive","sha_crc","boot_segments","app_segments") or \
                        field=="stack" and phase in ("hmac","stage_begin")
                    if detected:
                        assert answer=="ERR" and not r["commit"] and r["allocation_live"]==0
                    else:
                        assert answer=="STAGED" and r["commit"] # source gap, NOT an acceptable OTA
                    floor_rows.append(dict(phase=phase,field=field,aborted=detected,unsafe_peak=True))
        # All staging sectors: before, torn, after and explicit failure of
        # erase/write. Prior application is untouched, partial staging unknown.
        for sector in range(sectors):
            for kind in ("stage_erase","stage_write"):
                for mode in ("before","partial","after","fail"):
                    with trial(f"{kind}_{sector}_{mode}") as io:
                        begin(io);io.command(f"CUT {kind} {stage+sector*4096} {mode}")
                        assert upload(io)==("ERR" if mode=="fail" else "CUT")
                        r=io.report();assert not r["commit"] and r["current_preserved"]
                        if mode=="fail":assert r["allocation_live"]==0
                        counts["staging"]+=1
        for mode in ("before","after","fail"):
            with trial("end_header_read_"+mode) as io:
                begin(io);assert upload(io)=="FULL";io.command(f"CUT commit_read {stage} {mode}")
                assert io.command("FINISH")==("ERR" if mode=="fail" else "CUT")
                assert not io.report()["commit"] and io.report()["current_preserved"]
                counts["begin_end"]+=1
        # The real RTC CRC makes partial commands invalid. Cutting after the
        # last word arms eboot even though end(false) returned no receipt.
        for word in range(32):
            for mode in ("before","after"):
                with trial(f"rtc_{word}_{mode}") as io:
                    begin(io);assert upload(io)=="FULL";io.command(f"CUT rtc_word {word} {mode}")
                    assert io.command("FINISH")=="CUT"
                    r=io.report();assert r["current_preserved"] and bool(r["commit"])==(word==31 and mode=="after")
                    counts["rtc"]+=1
        with trial("rtc_dropped_store_no_error_channel") as io:
            begin(io);assert upload(io)=="FULL";io.command("CUT rtc_word 2 fail")
            assert io.command("FINISH")=="STAGED" and not io.report()["commit"]
        with trial("different_bootloader_sector_rewritten",different_boot=True) as io:
            staged(io);assert io.command("BOOT")=="BOOT_MODEL_OK"
            r=io.report();assert r["boot_erase"]==r["boot_writes"]==sectors and r["destination_sha_matches"]
        for word in (0,31):
            for mode in ("before","after"):
                with trial(f"rtc_clear_{word}_{mode}") as io:
                    staged(io);io.command(f"CUT rtc_word {word} {mode}")
                    assert io.command("BOOT")=="CUT"
                    r=io.report();assert r["boot_copy_result"]==0 and not r["boot_model"]
                    assert bool(r["commit"])==(word==0 and mode=="before")
                    counts["rtc_clear"]+=1
        for mode in ("before","after","fail"):
            with trial("eboot_sector_zero_compare_"+mode) as io:
                staged(io);io.command("CUT copy_destination_read 0 "+mode)
                assert io.command("BOOT")==("ERR" if mode=="fail" else "CUT")
                r=io.report();assert r["boot_erase"]==r["boot_writes"]==0 and r["current_preserved"]
                counts["eboot"]+=1
        # Copy the exact staged image through pinned eboot. Interrupt EVERY
        # destination sector, including sector zero when its bytes differ.
        for sector in range(sectors):
            for kind,modes in (("copy_read",("before","after","fail")),
                               ("copy_erase",("before","partial","after","fail")),
                               ("copy_write",("before","partial","after","fail"))):
                for mode in modes:
                    with trial(f"{kind}_{sector}_{mode}",different_boot=True) as io:
                        staged(io);at=stage+sector*4096 if kind=="copy_read" else sector*4096
                        io.command(f"CUT {kind} {at} {mode}")
                        assert io.command("BOOT")==("ERR" if mode=="fail" else "CUT")
                        r=io.report();assert not r["boot_model"]
                        if mode=="fail":assert not r["commit"] # eboot main clears even on copy failure
                        if sector>0:assert not r["current_preserved"] # previous app NOT rolled back
                        counts["eboot"]+=1
        with trial("postcommit_corruption_no_destination_verification") as io:
            staged(io);io.command("CORRUPT 6000")
            assert io.command("BOOT")=="ERR"
            r=io.report();assert r["boot_writes"]>0 and not r["current_preserved"] and not r["commit"]
            assert r["boot_copy_result"]==0 and not r["destination_sha_matches"]
            # BOOT_MODEL_OK requires independent host SHA; eboot copy itself
            # succeeded and copied this corruption without that verification.
        # Exercise the actual Windows one-shot install logic with the Core RAM
        # lab as its upload transport. All status replies and times are fake.
        from shino_update import install,UpdateError
        # The real client intentionally rejects the public fixture identity.
        # Reuse the existing synthetic Windows test image, NOT an owner image
        # or newly compiled private firmware. Do not bypass validate_owner.
        client_raw=fixture(device="1123456789abcdef")
        client_m=dict(m,device="1123456789abcdef",build_id="b"*64,bytes=len(client_raw),sha256=hashlib.sha256(client_raw).hexdigest())
        client_old=fixture("c"*64,device=client_m["device"])
        windows_current=directory/"windows-current.inert";windows_current.write_bytes(client_old)
        binary_file=directory/"pending.inert";binary_file.write_bytes(client_raw)
        manifest_file=directory/"release.json";manifest_file.write_text(json.dumps(client_m),encoding="utf-8")
        credentials=directory/"synthetic.json"
        credentials.write_text(json.dumps(dict(device=client_m["device"],maintenance_password=secret,
            build="d"*64,ap_psk="p"*32,api_token="t"*32,digest_password="h"*32)),encoding="utf-8")
        before=dict(protocol="shino-http-ota-1",device=client_m["device"],build_id="c"*64,
            sha256=hashlib.sha256(client_old).hexdigest(),bytes=len(client_old),nonce="1"*32,boot_id="1"*32,
            ota_enabled=True,fs_ok=True,fs_files=24,fs_bytes=181402,metrics_fresh=True,
            heap=60000,block=50000,stack=3248,frag=1)
        client_rows=[]
        for scenario in ("lost_before_body","validation_failed","lost_after_rtc","lost_during_copy",
                         "ack_without_boot","lost_reply_new_boot","new_boot_stale_metrics"):
            with trial("windows_"+scenario,windows=True) as io:
                ticks=[0];marker=directory/(scenario+".marker")
                class Transport:
                    posts=0;gets=0;boot=False
                    def status(self):
                        self.gets+=1
                        if not self.boot or self.gets==1:return dict(before)
                        return dict(before,build_id=client_m["build_id"],sha256=client_m["sha256"],bytes=len(client_raw),
                            boot_id="2"*32,metrics_fresh=scenario!="new_boot_stale_metrics")
                    def upload(self,headers,data,progress):
                        self.posts+=1;assert marker.read_text()=="OTA_ONE_SHOT_STARTED_NO_AUTOMATIC_RETRY\n"
                        assert self.posts==1 and data==client_raw
                        if scenario=="lost_before_body":raise UpdateError("Synthetic reply loss")
                        assert io.command(f'BEGIN {len(data)} {client_m["sha256"]} {client_m["build_id"]} {headers["X-Shino-Proof"]}')=="READY"
                        for pos in range(0,len(data),512):
                            chunk=data[pos:pos+512];io.write(chunk);assert io.read()==f"ACK {pos+len(chunk)}"
                        if scenario=="validation_failed":io.command("CORRUPT 6000")
                        if scenario=="lost_after_rtc":io.command("CUT rtc_word 31 after")
                        answer=io.command("FINISH")
                        if answer!="STAGED":raise UpdateError("Synthetic failed or lost reply")
                        if scenario=="lost_during_copy":io.command("CUT copy_write 4096 partial")
                        if scenario!="ack_without_boot":self.boot=io.command("BOOT")=="BOOT_MODEL_OK"
                        if scenario.startswith("lost_"):raise UpdateError("Synthetic reply loss")
                        return dict(status="STAGED_PENDING_BOOT",heap_min=25000,block_min=24000,stack_min=2272,frag_max=6,samples=800)
                transport=Transport()
                def sleep(seconds):ticks[0]+=seconds
                kwargs=dict(transport=transport,clock=lambda:ticks[0],sleep=sleep,
                    expected_current_sha256=before["sha256"],attempt_marker=marker)
                result=install(binary_file,manifest_file,credentials,client_m["sha256"],**kwargs)
                expected="BOOT_AND_TELEMETRY_CONFIRMED" if scenario=="lost_reply_new_boot" else \
                    "POSTBOOT_ACCEPTANCE_UNCONFIRMED" if scenario in ("ack_without_boot","new_boot_stale_metrics") else "UNKNOWN_NO_RETRY"
                assert result["status"]==expected and transport.posts==1
                gets=transport.gets;reserved=marker.read_bytes()
                try:install(binary_file,manifest_file,credentials,client_m["sha256"],**kwargs);raise AssertionError("Retry accepted")
                except UpdateError:pass
                assert transport.posts==1 and transport.gets==gets and marker.read_bytes()==reserved
                client_rows.append(dict(scenario=scenario,status=expected,posts=1,repeat_blocked_before_io=True))
    result=dict(OTA_OFFLINE_GATE="HOLD",simulation_matrix="PASS",cases=len(rows),sectors=sectors,
        image_bytes=len(raw),image_sha256=hashlib.sha256(raw).hexdigest(),public_inert=True,
        exact_core="ESP8266 Arduino 3.1.2 / package 3.30102.0",layout_symbols=linked,
        stage=stage,stage_end=stage+sectors*4096,fs_range=[0x200000,0x3FA000],reserved_range=[0x3FA000,0x400000],
        interruptions=counts,memory_floor_cases=floor_rows,
        windows_one_shot_cases=client_rows,littlefs_inventory_verified=fs_inventory["image_inventory_exact"],
        littlefs_files=fs_inventory["image_file_count"],littlefs_parser_writes=fs_inventory["parser_writes"],
        buffer_branches=[4096,256],low_memory_256_shino_admitted=False,
        rollback=False,automatic_retry=False,native_memory_proven=False,
        automatic_retry_scope="WINDOWS_POST_AND_TEST_DRIVER_ONLY",
        flash_and_rtc="RAM_MOCK",allocator_overhead_bytes_model=16,
        unsampled_peak_phases=["hmac","stage_begin","commit"],
        historical_stack_watermark_retained=True,
        postcommit_corruption_copied=True,rtc_write_has_no_error_channel=True,
        physical="NOT_RUN",device_contacts=0,network_calls=0,rows=rows)
    assert secret not in json.dumps(result) and "X-Shino-Proof" not in json.dumps(result)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--safety",action="store_true")
    parser.add_argument("--bin",type=Path);parser.add_argument("--manifest",type=Path)
    args=parser.parse_args()
    if not args.safety and (args.bin or args.manifest):parser.error("Image arguments require --safety")
    print(json.dumps(safety_gate(args.bin,args.manifest) if args.safety else run(),indent=2))
