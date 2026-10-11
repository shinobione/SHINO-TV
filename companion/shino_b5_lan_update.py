"""B5+ LAN OTA adapter: exact current/target SHAs and one-shot marker.

For future B5 -> successor releases only. Never for B4's AP-only OTA.
No device operation happens on import or in offline tests.
"""
import argparse
import json
from pathlib import Path
from urllib.request import (build_opener,ProxyHandler,HTTPDigestAuthHandler,
                            HTTPPasswordMgrWithDefaultRealm,Request)
from push_fsless_metrics import NoRedirect,validate_host
from shino_update import (DEFAULT_IDENTITY,Transport,load_identity,inspect,
                          install,save_receipt,UpdateError)


class LanTransport(Transport):
    def __init__(self,identity,host):
        self.host=validate_host(host)
        if self.host=="192.168.4.1":
            raise UpdateError("LAN updater refuses recovery AP target")
        self.base="http://"+self.host
        mgr=HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password("SHINO-StageA",self.base,"shino",identity["digest_password"])
        self.reader=build_opener(ProxyHandler({}),NoRedirect(),HTTPDigestAuthHandler(mgr))

    def lan_online(self):
        try:
            with self.reader.open(Request(self.base+"/api/v1/lan/status",
                  headers={"Connection":"close","Cache-Control":"no-store"}),timeout=5) as response:
                raw=response.read(513)
                if response.status!=200 or len(raw)>512:
                    raise UpdateError("LAN status unavailable")
                data=json.loads(raw)
            return (isinstance(data,dict) and data.get("state")=="STA_ONLINE"
                    and data.get("sta_online") is True
                    and data.get("lan_ip")==self.host)
        except Exception:
            return False


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host",required=True,help="Numeric Freebox LAN IP, not recovery AP")
    p.add_argument("--bin",required=True,type=Path)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--identity",type=Path,default=DEFAULT_IDENTITY)
    p.add_argument("--confirm-sha256",required=True)
    p.add_argument("--expected-current-sha256",required=True)
    p.add_argument("--attempt-marker",required=True,type=Path)
    p.add_argument("--receipt",required=True,type=Path)
    p.add_argument("--install",action="store_true",required=True)
    a=p.parse_args()
    try:
        if a.attempt_marker.exists() or a.receipt.exists():
            raise UpdateError("Existing attempt/receipt blocks new transfer")
        release,_=inspect(a.bin,a.manifest)
        if release["sha256"]!=a.confirm_sha256:
            raise UpdateError("Target BIN not expressly approved")
        identity=load_identity(a.identity)
        transport=LanTransport(identity,a.host)
        if not transport.lan_online():
            raise UpdateError("STA/LAN address not confirmed")
        result=install(a.bin,a.manifest,a.identity,a.confirm_sha256,
                       transport=transport,
                       expected_current_sha256=a.expected_current_sha256,
                       attempt_marker=a.attempt_marker,
                       progress=lambda n,t:print(f"{n}/{t}",flush=True))
        save_receipt(a.receipt,result)
        print(json.dumps(result))
        return 0 if result["status"]=="BOOT_AND_TELEMETRY_CONFIRMED" else 2
    except Exception:
        print("LAN_OTA_HOLD_OR_UNKNOWN — no retry; preserve any attempt marker")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
