"""Native Core RAM fault matrix and exact Windows HMAC contract, no device."""
import contextlib
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
        return dict(cases=len(rows),interruption_boundaries=cuts,actual_pinned_core=True,actual_windows_hmac=True,
                    core_buffer=4096,flash_and_rtc="RAM_MOCK",device_contacts=0,rows=rows)

if __name__=="__main__":print(json.dumps(run(),indent=2))
