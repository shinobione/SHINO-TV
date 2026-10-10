"""SHINO Windows updater: offline verify, explicit install, actual boot check.

Private AP only. One upload, never retries it. Credentials stay in the owner's
local JSON, never command arguments, HTTP errors, receipts or progress logs.
"""
import argparse
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import build_opener, ProxyHandler, HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm, Request
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from m9_signed_release import validate_image
from push_fsless_metrics import NoRedirect

HOST="192.168.4.1"
DEFAULT_IDENTITY=Path(__file__).resolve().parents[1]/"research-local/m9-owner/owner-credentials.json"
HEX=re.compile(r"[0-9a-f]{64}\Z")
class UpdateError(ValueError):pass


def unique(pairs):
    out={}
    for key,value in pairs:
        if key in out:raise UpdateError("Duplicate JSON field")
        out[key]=value
    return out


def inspect(binary,manifest):
    binary=Path(binary);manifest=Path(manifest)
    if binary.is_symlink() or manifest.is_symlink() or not binary.is_file() or not manifest.is_file():raise UpdateError("Regular BIN and release.json required")
    if binary.stat().st_size>0xFEFF0 or manifest.stat().st_size>4096:raise UpdateError("Release file bounds")
    m=json.loads(manifest.read_text(encoding="utf-8"),object_pairs_hook=unique)
    if set(m)!={"schema","family","layout","protocol","device","bytes","sha256","build_id"} or type(m["schema"]) is not int or m["schema"]!=1 or m["family"]!="SHINO-StageA" or m["layout"]!="4m2m" or m["protocol"]!="shino-http-ota-1":raise UpdateError("Incompatible release")
    if type(m["bytes"]) is not int or not isinstance(m["sha256"],str) or not HEX.fullmatch(m["sha256"]) or not isinstance(m["build_id"],str) or not HEX.fullmatch(m["build_id"]) or not isinstance(m["device"],str) or not re.fullmatch("[0-9a-f]{16}",m["device"]):raise UpdateError("Invalid release identity")
    raw=binary.read_bytes()
    if len(raw)!=m["bytes"] or hashlib.sha256(raw).hexdigest()!=m["sha256"]:raise UpdateError("BIN differs from release.json")
    validate_image(raw)
    tag=f'SHINO-HTTP-OTA-1|{m["device"]}|{m["build_id"]}|4m2m|APP_ONLY'.encode()
    if raw.count(tag)!=1:raise UpdateError("BIN lacks the exact OTA family/device/build identity")
    return m,raw


def load_identity(path):
    from shino_owner_transition import validate_owner
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>4096:raise UpdateError("Private identity file unavailable")
    try:return validate_owner(json.loads(path.read_text(encoding="utf-8"),object_pairs_hook=unique))
    except (ValueError,TypeError,KeyError):raise UpdateError("Private identity file invalid") from None


def signature(identity,nonce,m):
    text=f'SHINO-HTTP-OTA-1\n{identity["device"]}\n{nonce}\n{m["bytes"]}\n{m["sha256"]}\n{m["build_id"]}'
    key=hashlib.sha256(identity["maintenance_password"].encode()).digest()
    return hmac.new(key,text.encode("ascii"),hashlib.sha256).hexdigest()


class Transport:
    def __init__(self,identity,host=HOST):
        if str(ipaddress.IPv4Address(host))!=HOST:raise UpdateError("Only the SHINO private AP is supported")
        self.host=host;self.base="http://"+host;mgr=HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password("SHINO-StageA",self.base,"shino",identity["digest_password"])
        self.reader=build_opener(ProxyHandler({}),NoRedirect(),HTTPDigestAuthHandler(mgr))
    def status(self):
        try:
            with self.reader.open(Request(self.base+"/api/v1/update/status",headers={"Connection":"close","Cache-Control":"no-store"}),timeout=5) as response:
                raw=response.read(4097)
                if response.status!=200 or len(raw)>4096:raise UpdateError("Status unavailable")
                return json.loads(raw,object_pairs_hook=unique)
        except HTTPError as error:
            error.close();raise UpdateError("Authenticated device status unavailable") from None
        except (OSError,ValueError,http.client.HTTPException):raise UpdateError("Authenticated device status unavailable") from None
    def upload(self,headers,raw,progress):
        connection=http.client.HTTPConnection(self.host,80,timeout=10);start=time.monotonic()
        try:
            connection.putrequest("POST","/api/v1/update",skip_accept_encoding=True)
            for key,value in headers.items():connection.putheader(key,value)
            connection.endheaders()
            for at in range(0,len(raw),4096):
                if time.monotonic()-start>=110:raise UpdateError("Upload deadline exceeded; result UNKNOWN")
                connection.send(raw[at:at+4096]);progress(min(at+4096,len(raw)),len(raw))
            connection.sock.settimeout(120)
            response=connection.getresponse();body=response.read(4097)
            if response.status!=200 or len(body)>4096:raise UpdateError("Device rejected upload; inspect status before any future attempt")
            data=json.loads(body,object_pairs_hook=unique)
            if data.get("status")!="STAGED_PENDING_BOOT" or any(type(data.get(k)) is not int for k in ("heap_min","block_min","stack_min","frag_max","samples")):raise UpdateError("Commit reply invalid; result UNKNOWN")
            if data["heap_min"]<20480 or data["block_min"]<16384 or data["stack_min"]<2048 or data["frag_max"]>25 or data["samples"]<1:raise UpdateError("Commit resource evidence failed; inspect device, no retry")
            return data
        except (OSError,http.client.HTTPException,ValueError) as exc:
            if isinstance(exc,UpdateError):raise
            raise UpdateError("Transfer reply lost or invalid; result UNKNOWN, no retry") from None
        finally:connection.close()


def check_status(s,identity):
    if not isinstance(s,dict) or s.get("protocol")!="shino-http-ota-1" or s.get("device")!=identity["device"] or s.get("ota_enabled") is not True or s.get("fs_ok") is not True or s.get("fs_files")!=24 or s.get("fs_bytes")!=181402:raise UpdateError("Running firmware or LittleFS is incompatible")
    for field,size in (("build_id",64),("sha256",64),("nonce",32),("boot_id",32)):
        if not isinstance(s.get(field),str) or not re.fullmatch(f"[0-9a-f]{{{size}}}",s[field]):raise UpdateError("Invalid running identity")
    for field in ("bytes","heap","block","stack","frag"):
        if type(s.get(field)) is not int:raise UpdateError("Invalid running measurements")
    if not 64000<=s["bytes"]<=0xFEFF0:raise UpdateError("Running application size invalid")
    if s["heap"]<20480 or s["block"]<16384 or s["stack"]<2048 or s["frag"]>25:raise UpdateError("Running resource floors failed")
    return s


def install(binary,manifest,identity_path,confirm_sha,progress=lambda n,total:None,transport=None,clock=time.monotonic,sleep=time.sleep,notify=lambda text:None,expected_current_sha256=None,attempt_marker=None):
    # Exact offline inspection and consent BEFORE identity load or networking.
    m,raw=inspect(binary,manifest)
    if confirm_sha!=m["sha256"]:raise UpdateError("Explicit confirmation of this SHA256 is required")
    if expected_current_sha256 is not None and (not isinstance(expected_current_sha256,str) or not HEX.fullmatch(expected_current_sha256)):
        raise UpdateError("Exact running A SHA256 is required")
    if attempt_marker is not None:
        marker=Path(attempt_marker)
        if marker.is_symlink() or marker.exists() or not marker.parent.is_dir():
            raise UpdateError("OTA attempt marker exists or its directory is unavailable: no retry")
    identity=load_identity(identity_path)
    if m["device"]!=identity["device"]:raise UpdateError("Release targets another device")
    io=transport or Transport(identity)
    before=check_status(io.status(),identity)
    if expected_current_sha256 is not None and before["sha256"]!=expected_current_sha256:
        raise UpdateError("Running firmware A does not match expected SHA256")
    if before["build_id"]==m["build_id"] or before["sha256"]==m["sha256"]:raise UpdateError("Selected release is already running")
    if before["heap"]<25600 or before["block"]<16384 or before["stack"]<2048 or before["frag"]>25:raise UpdateError("Running resource floors failed")
    if 0x200000-((len(raw)+4095)&~4095)<((before["bytes"]+4095)&~4095)+4096:raise UpdateError("Staging overlaps running application")
    headers={"Content-Type":"application/octet-stream","Content-Length":str(len(raw)),"Connection":"close",
             "X-Shino-SHA256":m["sha256"],"X-Shino-Build":m["build_id"],"X-Shino-Nonce":before["nonce"],
             "X-Shino-Proof":signature(identity,before["nonce"],m)}
    # Once this marker is durably created, the owner must never repeat an
    # upload based on an ambiguous response. No extra HTTP status read is made.
    if attempt_marker is not None:
        try:
            with Path(attempt_marker).open("x",encoding="ascii") as marker_file:
                marker_file.write("OTA_ONE_SHOT_STARTED_NO_AUTOMATIC_RETRY\n")
                marker_file.flush();os.fsync(marker_file.fileno())
        except OSError as error:
            raise UpdateError("Could not atomically reserve one OTA attempt") from None
    acknowledged=False
    try:acknowledged=io.upload(headers,raw,progress)
    except UpdateError:
        # Read-only postboot verification can resolve a lost reply. NEVER resend.
        pass
    notify("Transfert terminé ou réponse perdue : relancez LINK. Vérification du nouveau démarrage…")
    until=clock()+60
    while clock()<until:
        sleep(1)
        try:
            after=check_status(io.status(),identity)
            if after["build_id"]==m["build_id"] and after["sha256"]==m["sha256"] and after["bytes"]==m["bytes"] and after["boot_id"]!=before["boot_id"]:
                if after.get("metrics_fresh") is True and after["heap"]>=25600:
                    return dict(status="BOOT_AND_TELEMETRY_CONFIRMED",sha256=m["sha256"],build_id=m["build_id"],bytes=m["bytes"],
                                before_boot_id=before["boot_id"],boot_id=after["boot_id"],fs_preserved=True,fs_files=after["fs_files"],fs_bytes=after["fs_bytes"],
                                next_ota_available=True,postboot_measurements={field:after[field] for field in ("heap","block","stack","frag")},
                                transfer_measurements=acknowledged or "REPLY_LOST_UNKNOWN")
                # B booted; allow the normal LINK cadence to recover first.
        except (UpdateError,OSError):pass
    return dict(status="POSTBOOT_ACCEPTANCE_UNCONFIRMED" if acknowledged else "UNKNOWN_NO_RETRY",sha256=m["sha256"],physical_acceptance=False)


def save_receipt(path,result):
    if path:
        with Path(path).open("x",encoding="utf-8") as out:json.dump(result,out,indent=2)


def gui(initial_manifest=None,receipt=None):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    import threading,queue
    root=tk.Tk();root.title("SHINO // UPDATE");root.geometry("650x440")
    frame=ttk.Frame(root,padding=20);frame.pack(fill="both",expand=True)
    ttk.Label(frame,text="SHINO // UPDATE",font=("Segoe UI",20,"bold")).pack(anchor="w")
    ttk.Label(frame,text="Connectez le PC au Wi-Fi SHINO. Arrêtez LINK pendant le transfert,\npuis relancez-le pour confirmer les mesures. Gardez le SmallTV alimenté.").pack(anchor="w",pady=10)
    selected={};queue_=queue.Queue();status=tk.StringVar(value="Choisissez release.json ; la vérification reste hors ligne.")
    bar=ttk.Progressbar(frame,maximum=100);bar.pack(fill="x",pady=10)
    def choose(path=None):
        path=path or filedialog.askopenfilename(title="Choisir release.json",filetypes=[("Release SHINO","*.json")])
        if not path:return
        manifest=Path(path);binary=manifest.parent/".pio/build/esp12e_m9_4m2m_normal_qualification/firmware.bin"
        try:
            m,_=inspect(binary,manifest);selected.update(binary=binary,manifest=manifest,m=m)
            status.set(f'Vérifié : {m["bytes"]} octets\nSHA-256 : {m["sha256"]}');button.configure(state="normal")
        except (ValueError,OSError):status.set("Release invalide ou BIN absent.");button.configure(state="disabled")
    ttk.Button(frame,text="Choisir et vérifier la nouvelle version",command=choose).pack(anchor="w")
    def run():
        release=dict(selected);m=release["m"]
        if receipt and Path(receipt).exists():status.set("Un résultat existe déjà : installation bloquée pour éviter un second essai.");return
        if not messagebox.askyesno("Installer cette version exacte ?",f'SHA-256 : {m["sha256"]}\n\nCette action programme la flash par Wi-Fi puis redémarre le SmallTV.\nPas de rollback automatique. Autorisez-vous cette installation ?'):return
        button.configure(state="disabled")
        def work():
            try:
                result=install(release["binary"],release["manifest"],DEFAULT_IDENTITY,m["sha256"],lambda n,total:queue_.put(("progress",n*100/total)),notify=lambda text:queue_.put(("status",text)))
                save_receipt(receipt,result);queue_.put(("result",result))
            except UpdateError as error:queue_.put(("result",{"status":str(error)+" — no retry"}))
            except (ValueError,OSError):queue_.put(("result",{"status":"FAILED_OR_UNKNOWN_NO_RETRY"}))
        threading.Thread(target=work,daemon=True).start()
    button=ttk.Button(frame,text="Installer par Wi-Fi",command=run,state="disabled");button.pack(anchor="w",pady=12)
    ttk.Label(frame,textvariable=status,wraplength=600).pack(anchor="w")
    def poll():
        while not queue_.empty():
            kind,value=queue_.get()
            if kind=="progress":bar["value"]=value
            elif kind=="status":status.set(value)
            else:status.set(value["status"]+" — aucun nouvel upload automatique")
        root.after(100,poll)
    if initial_manifest:choose(initial_manifest)
    poll();root.mainloop()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--gui",action="store_true");p.add_argument("--bin",type=Path);p.add_argument("--manifest",type=Path)
    p.add_argument("--identity",type=Path,default=DEFAULT_IDENTITY);p.add_argument("--install",action="store_true");p.add_argument("--confirm-sha256")
    p.add_argument("--receipt",type=Path)
    p.add_argument("--expected-current-sha256")
    p.add_argument("--attempt-marker",type=Path)
    a=p.parse_args()
    if a.gui or not a.bin:gui(a.manifest,a.receipt);return 0
    try:
        if a.receipt and a.receipt.exists():raise UpdateError("Existing receipt: no further attempt")
        if not a.install:m,_=inspect(a.bin,a.manifest);result=dict(status="VERIFIED_OFFLINE",**m)
        else:result=install(a.bin,a.manifest,a.identity,a.confirm_sha256,lambda n,total:print(f"{n}/{total}",flush=True),notify=lambda text:print(text,flush=True),expected_current_sha256=a.expected_current_sha256,attempt_marker=a.attempt_marker)
        save_receipt(a.receipt,result)
        print(json.dumps(result));return 0 if result["status"] in ("VERIFIED_OFFLINE","BOOT_AND_TELEMETRY_CONFIRMED") else 2
    except UpdateError as error:print(str(error)+" — no automatic retry",file=sys.stderr);return 2
    except (ValueError,OSError):print("FAILED_OR_UNKNOWN — no automatic retry",file=sys.stderr);return 2

if __name__=="__main__":raise SystemExit(main())
