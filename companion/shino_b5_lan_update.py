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
