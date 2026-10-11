"""B5 only: one-time home 2.4 GHz Wi-Fi provisioning through recovery AP.

NO disk storage of SSID/password, no firmware update and NO automatic retries.
Use only after a separately approved B5 firmware is installed and qualified.
"""
from __future__ import annotations
import argparse
import getpass
import json
from pathlib import Path
from urllib.request import (Request,build_opener,ProxyHandler,
    HTTPPasswordMgrWithDefaultRealm)
from provision_home_wifi import WifiDigest,encode_change
from push_fsless_metrics import NoRedirect
from shino_update import DEFAULT_IDENTITY,load_identity

HOST="192.168.4.1"
ROOT="http://"+HOST
API="/api/v1/lan"


class ProvisionHold(ValueError):
    pass


def make_reader(identity):
    mgr=HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password("SHINO-StageA",ROOT+API,"shino",identity["digest_password"])
    return build_opener(ProxyHandler({}),NoRedirect(),WifiDigest(mgr,ROOT+API))


def request(reader,route,body=None,token=None):
    headers={"Accept":"application/json","Connection":"close","Cache-Control":"no-store"}
    if body is not None:
        headers["Content-Type"]="application/octet-stream"
        headers["X-Shino-Lan-Intent"]=token
    req=Request(ROOT+API+route,data=body,headers=headers,method="GET" if body is None else "POST")
    try:
        with reader.open(req,timeout=5) as response:
            raw=response.read(513)
            if response.status!=200 or len(raw)>512:raise ProvisionHold("Response boundedness")
        return json.loads(raw)
    except Exception:
        raise ProvisionHold("LAN provision rejected/unknown; do not retry a lost response") from None


def provision(reader,ssid,password):
    payload=encode_change(ssid,password)
    try:
        intent=request(reader,"/intent")
        token=intent.get("intent") if isinstance(intent,dict) else None
        if type(token) is not str or len(token)!=32 or any(c not in "0123456789abcdef" for c in token):
            raise ProvisionHold("Intent mismatch")
        status=request(reader,"/provision",payload,token)
        if status!={"saved":True,"readback_verified":True}:
            raise ProvisionHold("LAN credentials not verified")
        return "SDK_CREDENTIALS_VERIFIED_STA_CONNECTION_NOT_YET_PROVEN"
    finally:
        payload[:]=b"\x00"*len(payload)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--change",action="store_true",required=True,
                   help="One explicit owner provisioning operation, after B5 installation")
    p.add_argument("--identity",type=Path,default=DEFAULT_IDENTITY)
    a=p.parse_args()
    import sys
    if not sys.stdin.isatty():
        print("B5_PROVISION_HOLD: interactive terminal required")
        return 2
    try:
        identity=load_identity(a.identity)
        ssid=input("SSID Freebox 2.4 GHz : ")
        password=getpass.getpass("Mot de passe Wi-Fi (masque) : ")
        again=getpass.getpass("Confirmation (masquee) : ")
        if password!=again:raise ProvisionHold("Mismatch")
        if input("Taper PROVISION B5 pour envoyer UNE fois : ")!="PROVISION B5":
            raise ProvisionHold("Cancelled")
        result=provision(make_reader(identity),ssid,password)
        print(result)
        print("B5 can now attempt DHCP; check LAN IP separately. No automatic retry.")
        return 0
    except Exception:
        print("B5_PROVISION_HOLD: input, authentication or device response rejected; no retry")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
