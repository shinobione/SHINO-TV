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
