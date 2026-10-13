"""B5 only: one-time home 2.4 GHz Wi-Fi provisioning through recovery AP.

NO disk storage of SSID/password, no firmware update and NO automatic retries.
Use only after a separately approved B5 firmware is installed and qualified.
"""
from __future__ import annotations
import argparse
import getpass
import json
import re
import os
import warnings
from urllib.error import HTTPError
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'companion'))
from urllib.request import (Request,build_opener,ProxyHandler,
    HTTPPasswordMgrWithDefaultRealm)
from provision_home_wifi import WifiDigest,encode_change
from push_fsless_metrics import NoRedirect
from shino_update import DEFAULT_IDENTITY,load_identity
from shino_digest_coord import digest_exchange

HOST="192.168.4.1"
ROOT="http://"+HOST
API="/api/v1/lan"


class ProvisionHold(ValueError):
    pass


DEVICE_CODES=frozenset((
    "PROVISION_HOLD", "PROVISION_AP_ONLY", "PROVISION_AP_STATE",
    "PROVISION_BODY_INCOMPLETE", "PROVISION_BODY_EXTRA", "PROVISION_INTENT_INVALID",
    "PROVISION_PAYLOAD_INVALID", "PROVISION_LAYOUT_UNSAFE", "PROVISION_STA_ENABLE_FAILED",
    "PROVISION_MEMORY_HOLD", "PROVISION_SDK_READ_FAILED", "PROVISION_SDK_WRITE_FAILED_UNKNOWN",
    "PROVISION_READBACK_FAILED_UNKNOWN", "PROVISION_READBACK_MISMATCH_UNKNOWN",
    "NETWORK_POLICY", "HTTP_FRAMING", "GET_BODY", "INTENT_AP_ONLY", "READONLY_CONFIG_HOLD",
))


class ProvisionDigest(WifiDigest):
    """One GET challenge retry; NEVER replay a credential-bearing POST."""
    def http_error_401(self,req,fp,code,msg,headers):
        challenges=getattr(req,"_b51_challenges",0)
        if req.get_method()=="POST" or challenges>=1:
            raise HTTPError(req.full_url,code,msg,headers,fp)
        req._b51_challenges=challenges+1
        return super().http_error_401(req,fp,code,msg,headers)


def make_reader(identity):
    mgr=HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password("SHINO-StageA",ROOT,"shino",identity["digest_password"])
    return build_opener(ProxyHandler({}),NoRedirect(),ProvisionDigest(mgr,ROOT))


def request(reader,route,body=None,token=None):
    headers={"Accept":"application/json","Connection":"close","Cache-Control":"no-store"}
    if body is not None:
        headers["Content-Type"]="application/octet-stream"
        headers["X-Shino-Lan-Intent"]=token
    endpoint=ROOT+(route if route.startswith("/api/") else API+route)
    req=Request(endpoint,data=body,headers=headers,method="GET" if body is None else "POST")
    try:
        with reader.open(req,timeout=5) as response:
            raw=response.read(513)
            if response.status!=200 or len(raw)>512:
                raise ProvisionHold(route+": unexpected HTTP status/response bound — no retry")
        return json.loads(raw)
    except HTTPError as error:
        # Diagnostic contains only status and a whitelisted DEVICE ERROR CODE.
        # Never display the request body, Wi-Fi credentials, token or Digest data.
        status=error.code
        try:
            packet=json.loads(error.read(257))
            code=packet.get("error","") if isinstance(packet,dict) else ""
            code=code if isinstance(code,str) and code in DEVICE_CODES else "NO_DEVICE_ERROR_CODE"
        except (ValueError,UnicodeError,TypeError):
            code="NO_DEVICE_ERROR_CODE"
        finally:
            error.close()
        raise ProvisionHold(f"{route}: HTTP {status} / {code} — no retry") from None
    except ProvisionHold:
        raise
    except Exception as error:
        # A lost POST response is AMBIGUOUS even if the server saved Wi-Fi.
        # Do not silently retry it, regardless of the exception class.
        raise ProvisionHold(f"{route}: {type(error).__name__} / UNKNOWN_NO_RETRY") from None


def reserve(marker):
    marker=Path(marker)
    if marker.exists() or marker.is_symlink():raise ProvisionHold("Existing attempt marker: STOP before POST")
    with marker.open("x",encoding="utf-8") as out:
        out.write('{"operation":"B51_LAN_PROVISION","status":"RESERVED_NO_RETRY"}\n')
        out.flush();os.fsync(out.fileno())


def provision(reader,ssid,password,*,attempt_marker):
    marker=Path(attempt_marker)
    if marker.exists() or marker.is_symlink():raise ProvisionHold("Existing attempt marker: STOP before HTTP")
    payload=encode_change(ssid,password)
    try:
        intent=request(reader,"/intent")
        token=intent.get("intent") if isinstance(intent,dict) else None
        if type(token) is not str or len(token)!=32 or any(c not in "0123456789abcdef" for c in token):
            raise ProvisionHold("Intent mismatch")
        reserve(marker) # durable reservation BEFORE the only credential POST
        status=request(reader,"/provision",payload,token)
        if (not isinstance(status,dict) or set(status)!={"saved","readback_verified"} or
            status["saved"] is not True or status["readback_verified"] is not True):
            raise ProvisionHold("LAN credentials not verified")
        return "SDK_CREDENTIALS_VERIFIED_STA_CONNECTION_NOT_YET_PROVEN"
    finally:
        payload[:]=b"\x00"*len(payload)


def preflight(reader,expected_sha,expected_build):
    for value in (expected_sha,expected_build):
        if not re.fullmatch(r"[0-9a-f]{64}",value):raise ProvisionHold("Exact running SHA/build required")
    running=request(reader,"/api/v1/update/status")
    if not isinstance(running,dict) or running.get("sha256")!=expected_sha or running.get("build_id")!=expected_build:
        raise ProvisionHold("Running firmware identity mismatch")
    status=request(reader,"/status")
    if not isinstance(status,dict) or status.get("firmware")!="B5.1":
        raise ProvisionHold("B5.1 status required: old B5 saved-state is unreliable")
    if status.get("credential_state")=="VERIFIED":
        return "ALREADY_SAVED_NO_POST"
    if status.get("credential_state")!="EMPTY" or status.get("state")!="NO_SAVED_WIFI":
        raise ProvisionHold("Existing or unknown LAN state: STOP before POST")
    return "EMPTY"


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--change",action="store_true",required=True,
                   help="One explicit owner provisioning operation, after B5 installation")
    p.add_argument("--identity",type=Path,default=DEFAULT_IDENTITY)
    p.add_argument("--expected-current-sha256",required=True)
    p.add_argument("--expected-current-build-id",required=True)
    p.add_argument("--attempt-marker",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--paste-once",action="store_true",
                   help="Compatibility option: one hidden prompt is now the default")
    a=p.parse_args(argv)
    import sys
    if not sys.stdin.isatty():
        print("B5_PROVISION_HOLD: interactive terminal required")
        return 2
    try:
        if a.attempt_marker.exists() or a.attempt_marker.is_symlink() or a.receipt.exists() or a.receipt.is_symlink():
            raise ProvisionHold("Existing attempt/receipt: no new operation")
        identity=load_identity(a.identity)
        reader=make_reader(identity)
        with digest_exchange(HOST):
            state=preflight(reader,a.expected_current_sha256,a.expected_current_build_id)
        if state=="ALREADY_SAVED_NO_POST":
            print("Identifiants SDK deja verifies : aucun mot de passe demande, aucun POST. Verifier DHCP separement.")
            return 0
        ssid=input("SSID Freebox 2.4 GHz : ")
        with warnings.catch_warnings():
            warnings.simplefilter("error",getpass.GetPassWarning)
            password=getpass.getpass("Mot de passe Wi-Fi (masque, coller une fois) : ")
        with digest_exchange(HOST):
            if preflight(reader,a.expected_current_sha256,a.expected_current_build_id)!="EMPTY":
                raise ProvisionHold("Saved state changed: no POST")
            result=provision(reader,ssid,password,attempt_marker=a.attempt_marker)
        del ssid,password
        try:
            with a.receipt.open("x",encoding="utf-8") as out:
                json.dump({"status":result,"sha256":a.expected_current_sha256,"build_id":a.expected_current_build_id},out)
                out.flush();os.fsync(out.fileno())
        except OSError:
            raise ProvisionHold("SDK_CREDENTIALS_VERIFIED / LOCAL_RECEIPT_WRITE_FAILED_NO_RETRY") from None
        print(result)
        print("Sauvegarde relue. DHCP reste a verifier. Aucun retry automatique ; conserver le marqueur.")
        return 0
    except ProvisionHold as error:
        print("B5_PROVISION_HOLD:",str(error),file=sys.stderr)
        return 2
    except Exception:
        print("B5_PROVISION_HOLD: local validation error (details redacted)",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
