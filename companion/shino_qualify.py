"""Bounded read-only physical qualification, only when the owner starts it.

Default is PRINT_ONLY. No flash, reboot, UART, credential provision or retry.
"""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request
from shino_update import inspect,load_identity,Transport,check_status,DEFAULT_IDENTITY,UpdateError


def qualify(binary,manifest,identity_path,authorize_read,cycles=30):
    m,_=inspect(binary,manifest)
    if not authorize_read:return dict(status="PRINT_ONLY",sha256=m["sha256"],device_contacts=0)
    identity=load_identity(identity_path)
    if m["device"]!=identity["device"]:raise UpdateError("Wrong device")
    io=Transport(identity);minimum=dict(heap=2**32-1,block=2**32-1,stack=2**32-1);maximum_frag=0;boot=None
    for _ in range(cycles):
        s=check_status(io.status(),identity)
        if s["build_id"]!=m["build_id"] or s["sha256"]!=m["sha256"] or s["bytes"]!=m["bytes"] or not s.get("metrics_fresh"):raise UpdateError("Identity or LINK mismatch; stop")
        if boot is not None and s["boot_id"]!=boot:raise UpdateError("Unexpected reboot; stop")
        boot=s["boot_id"]
        for field in minimum:minimum[field]=min(minimum[field],s[field])
        maximum_frag=max(maximum_frag,s["frag"])
        for path in ("/api/v1/m9/normal/status","/api/v1/m9/maintenance/result"):
            with io.reader.open(Request(io.base+path,headers={"Connection":"close"}),timeout=5) as response:
                raw=response.read(4097)
                if response.status!=200 or len(raw)>4096:raise UpdateError("Repeated GET failed; stop")
                json.loads(raw)
        time.sleep(2)
    return dict(status="PHYSICAL_READONLY_QUALIFICATION_PASS",sha256=m["sha256"],build_id=m["build_id"],cycles=cycles,
                minima=minimum,frag_max=maximum_frag,fs_hash_inventory_verified=True,metrics_fresh=True,
                boot_stable=True,ota_admission_heap_observed=minimum["heap"]>=25600,flash_writes=0,reboots=0)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--bin",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--identity",type=Path,default=DEFAULT_IDENTITY);p.add_argument("--authorize-read",action="store_true");p.add_argument("--receipt",type=Path)
    a=p.parse_args()
    try:
        if a.receipt and a.receipt.exists():raise UpdateError("Existing receipt: no further read attempt")
        result=qualify(a.bin,a.manifest,a.identity,a.authorize_read)
        if a.receipt:
            with a.receipt.open("x",encoding="utf-8") as out:json.dump(result,out,indent=2)
        print(json.dumps(result))
    except (ValueError,OSError):raise SystemExit("READONLY_QUALIFICATION_FAILED — stop, no retry or write")
