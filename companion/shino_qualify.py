"""Bounded read-only qualification. Default PRINT_ONLY; no write or retry.

Diagnostics contain only fixed operation names, codes and typed measurements.
Never print exception text, response bodies, HTTP headers or credentials.
"""
import argparse
import http.client
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request
from shino_update import inspect,load_identity,Transport,check_status,unique,DEFAULT_IDENTITY,UpdateError


class QualificationFailure(UpdateError):
    def __init__(self,code,cycle,operation,**details):
        self.diagnostic=dict(code=code,cycle=cycle,operation=operation,**details)
        super().__init__(code)

    def result(self):
        return dict(status="READONLY_QUALIFICATION_FAILED",diagnostic=self.diagnostic,
                    physical_acceptance=False,flash_writes=0,reboots=0)


def fail(code,cycle,operation,**details):
    raise QualificationFailure(code,cycle,operation,**details)


def read_json(io,path,cycle):
    operation="GET "+path
    try:
        with io.reader.open(Request(io.base+path,headers={"Connection":"close","Cache-Control":"no-store"}),timeout=5) as response:
            if response.status!=200:
                code=response.status if type(response.status) is int else None
                fail("HTTP_STATUS",cycle,operation,http_status=code)
            raw=response.read(4097)
            if len(raw)>4096:fail("HTTP_BODY_TOO_LARGE",cycle,operation,limit=4096)
            value=json.loads(raw,object_pairs_hook=unique)
            if not isinstance(value,dict):fail("JSON_OBJECT_REQUIRED",cycle,operation)
            return value
    except QualificationFailure:raise
    except HTTPError as error:
        code=error.code if type(error.code) is int else None
        error.close()
        fail("HTTP_STATUS",cycle,operation,http_status=code)
    except (TimeoutError,URLError) as error:
        timeout=isinstance(error,TimeoutError) or isinstance(getattr(error,"reason",None),TimeoutError)
        fail("NETWORK_TIMEOUT" if timeout else "NETWORK_UNAVAILABLE",cycle,operation)
    except OSError as error:
        number=error.errno if type(error.errno) is int else None
        fail("NETWORK_UNAVAILABLE",cycle,operation,errno=number)
    except http.client.HTTPException:fail("HTTP_PROTOCOL_ERROR",cycle,operation)
    except (ValueError,UnicodeError):fail("JSON_INVALID",cycle,operation)


def validate_status(s,identity,m,cycle,path,boot):
    operation="GET "+path
    try:check_status(s,identity)
    except UpdateError as error:
        if str(error)=="Running resource floors failed":
            violations=[]
            for field,floor in (("heap",20480),("block",16384),("stack",2048)):
                if s[field]<floor:violations.append(dict(field=field,observed=s[field],minimum=floor))
            if s["frag"]>25:violations.append(dict(field="frag",observed=s["frag"],maximum=25))
            fail("RESOURCE_FLOOR_FAILED",cycle,operation,violations=violations)
        codes={"Running firmware or LittleFS is incompatible":"FIRMWARE_OR_FILESYSTEM_INCOMPATIBLE",
               "Invalid running identity":"IDENTITY_INVALID","Invalid running measurements":"MEASUREMENTS_INVALID",
               "Running application size invalid":"APPLICATION_SIZE_INVALID"}
        fail(codes.get(str(error),"STATUS_INVALID"),cycle,operation)
    fields=[field for field in ("build_id","sha256","bytes") if s[field]!=m[field]]
    if fields:fail("RELEASE_IDENTITY_MISMATCH",cycle,operation,fields=fields)
    if boot is not None and s["boot_id"]!=boot:fail("UNEXPECTED_REBOOT",cycle,operation)
    if s.get("metrics_fresh") is not True:fail("LINK_METRICS_NOT_FRESH",cycle,operation)
    if s["heap"]<25600:
        fail("FUTURE_OTA_HEAP_BELOW_FLOOR",cycle,operation,violations=[dict(field="heap",observed=s["heap"],minimum=25600)])
    return s


def qualify(binary,manifest,identity_path,authorize_read,cycles=30,transport=None,sleep=time.sleep):
    if type(cycles) is not int or not 1<=cycles<=30:fail("INVALID_CYCLE_COUNT",0,"INPUT",minimum=1,maximum=30)
    try:m,_=inspect(binary,manifest)
    except (ValueError,OSError,KeyError,TypeError):fail("BIN_OR_MANIFEST_INVALID",0,"OFFLINE_VERIFY")
    if not authorize_read:return dict(status="PRINT_ONLY",sha256=m["sha256"],device_contacts=0)
    try:identity=load_identity(identity_path)
    except (ValueError,OSError,KeyError,TypeError):fail("PRIVATE_IDENTITY_UNAVAILABLE",0,"LOCAL_IDENTITY")
    if m["device"]!=identity["device"]:fail("WRONG_DEVICE",0,"LOCAL_IDENTITY")
    io=transport or Transport(identity)
    minimum=dict(heap=2**32-1,block=2**32-1,stack=2**32-1);maximum_frag=0;boot=None
    for cycle in range(1,cycles+1):
        for path in ("/api/v1/update/status","/api/v1/m9/normal/status","/api/v1/m9/maintenance/result"):
            s=read_json(io,path,cycle)
            if path=="/api/v1/m9/normal/status":
                if s.get("mode")!="M9_NORMAL_STAGE_A":fail("NORMAL_STATUS_INVALID",cycle,"GET "+path)
                continue
            validate_status(s,identity,m,cycle,path,boot);boot=s["boot_id"]
            for field in minimum:minimum[field]=min(minimum[field],s[field])
            maximum_frag=max(maximum_frag,s["frag"])
        if cycle!=cycles:sleep(2)
    return dict(status="PHYSICAL_READONLY_QUALIFICATION_PASS",sha256=m["sha256"],build_id=m["build_id"],cycles=cycles,
                minima=minimum,frag_max=maximum_frag,fs_hash_inventory_verified=True,metrics_fresh=True,
                boot_stable=True,ota_admission_heap_observed=True,flash_writes=0,reboots=0)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--bin",type=Path,required=True);p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--identity",type=Path,default=DEFAULT_IDENTITY);p.add_argument("--authorize-read",action="store_true");p.add_argument("--receipt",type=Path)
    a=p.parse_args(argv)
    try:
        if a.receipt and a.receipt.exists():fail("RECEIPT_ALREADY_EXISTS",0,"RECEIPT")
        result=qualify(a.bin,a.manifest,a.identity,a.authorize_read)
    except QualificationFailure as error:result=error.result()
    except (ValueError,OSError,KeyError,TypeError):
        result=QualificationFailure("LOCAL_INPUT_INVALID",0,"INPUT").result()
    if a.receipt and result.get("diagnostic",{}).get("code")!="RECEIPT_ALREADY_EXISTS":
        try:
            with a.receipt.open("x",encoding="utf-8") as out:json.dump(result,out,indent=2)
        except OSError:
            if result["status"]!="READONLY_QUALIFICATION_FAILED":
                result=QualificationFailure("RECEIPT_WRITE_FAILED",0,"RECEIPT").result()
            result["receipt_saved"]=False
    print(json.dumps(result))
    if result["status"]=="READONLY_QUALIFICATION_FAILED":
        d=result["diagnostic"]
        print(f'Cycle {d["cycle"]}, {d["operation"]}: {d["code"]}',file=sys.stderr)
        for v in d.get("violations",[]):
            bound="minimum" if "minimum" in v else "maximum"
            print(f'  {v["field"]}: observed={v["observed"]}, {bound}={v[bound]}',file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":raise SystemExit(main())
