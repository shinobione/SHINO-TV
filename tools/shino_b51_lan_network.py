"""B5.1 HTTP interruption/fault matrix and LAN HMAC OTA, HOST_LOOPBACK only."""
import argparse
import hashlib
import http.client
import json
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler,HTTPPasswordMgrWithDefaultRealm

import shino_b5_provision as client
from shino_b51_lan_runner import compile_host
from shino_http_ota_network import PASSWORD
from test_shino_http_ota import fixture
from shino_update import inspect,signature


def run(binary=None,manifest=None,current_binary=None,current_manifest=None):
    device="0123456789abcdef";current_build="a"*64
    if binary:
        target,raw=inspect(binary,manifest);device=target["device"]
        current_build=("c" if target["build_id"]!="c"*64 else "d")*64
        if current_binary:
            current,_=inspect(current_binary,current_manifest)
            if current["device"]!=device or current["build_id"]==target["build_id"]:
                raise ValueError("Distinct same-device public releases required")
            current_build=current["build_id"]
    else:
        raw=fixture();target=dict(device=device,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),build_id="b"*64)
    rows=[]
    with tempfile.TemporaryDirectory(prefix="shino-b51-network-") as td:
        directory=Path(td);exe,env=compile_host(directory,device=device,current_build=current_build)
        if current_binary:env=dict(env,SHINO_TEST_CURRENT_BIN=str(Path(current_binary).resolve()))
        process=subprocess.Popen([str(exe)],cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            port_line=process.stdout.readline()
            if not port_line:raise RuntimeError(process.stderr.read())
            port=int(port_line);base=f"http://127.0.0.1:{port}"
            authority="192.168.4.1"
            mgr=HTTPPasswordMgrWithDefaultRealm();mgr.add_password("SHINO-StageA",base,"shino","PUBLIC-INERT-LAB-HTTP-FIXTURE")
            digest=client.ProvisionDigest(mgr,base)
            reader=build_opener(ProxyHandler({}),client.NoRedirect(),digest)
            def control(value):
                process.stdin.write(value+"\n");process.stdin.flush()
                reply=process.stdout.readline()
                if not reply:raise RuntimeError(process.stderr.read())
                return json.loads(reply)
            def exchange(path,body=None,token=None,extra=None):
                headers={"Host":authority,"Connection":"close","Content-Type":"application/octet-stream"}
                if token is not None:headers["X-Shino-Lan-Intent"]=token
                headers.update(extra or {})
                req=Request(base+path,data=body,headers=headers,method="GET" if body is None else "POST")
                try:
                    with reader.open(req,timeout=6) as response:return response.status,json.loads(response.read())
                except HTTPError as error:
                    with error:return error.code,json.loads(error.read() or b"{}")
            def intent():
                code,value=exchange("/api/v1/lan/intent");assert code==200,(code,value)
                return value["intent"]
            def reset():
                assert control("reset")=={"ok":True}
            payload=client.encode_change("TestHome","FakePass1234")
            def wire(data,token,declared=None,fragments=False,interrupt=False,duplicate=False,drop_reply=False):
                req=Request(base+"/api/v1/lan/provision",data=data,method="POST")
                auth=digest.get_authorization(req,digest.challenge)
                connection=http.client.HTTPConnection("127.0.0.1",port,timeout=6)
                connection.putrequest("POST","/api/v1/lan/provision",skip_host=True,skip_accept_encoding=True)
                for name,value in (("Host",authority),("Connection","close"),("Authorization","Digest "+auth),
                      ("Content-Type","application/octet-stream"),("Content-Length",str(len(data) if declared is None else declared)),
                      ("X-Shino-Lan-Intent",token)):
                    connection.putheader(name,value)
                if duplicate:connection.putheader("X-Shino-Lan-Intent",token)
                connection.endheaders()
                if fragments:
                    for at in range(0,len(data),3):connection.send(data[at:at+3]);time.sleep(.01)
                else:connection.send(data)
                if interrupt:connection.sock.shutdown(socket.SHUT_WR)
                if drop_reply:
                    # Main-thread stats is processed AFTER synchronous dispatch.
                    assert control("stats")["sdk_writes"]==1
                    connection.close();return None,{}
                try:
                    response=connection.getresponse();return response.status,json.loads(response.read() or b"{}")
                except (OSError,http.client.HTTPException):return None,{}
                finally:connection.close()
            def record(name,writes):
                stats=control("stats");assert stats["sdk_writes"]==writes,(name,stats)
                assert stats["flash_writes"]==0 and stats["restarts"]==0
                rows.append(dict(case=name,sdk_writes=writes,ap_preserved=stats["ap_active"]))

            code,status=exchange("/api/v1/lan/status");assert code==200 and status["credential_state"]=="EMPTY"
            record("empty_boot",0)
            key=intent();assert wire(payload,key,fragments=True)==(200,{"saved":True,"readback_verified":True})
            record("fragmented_body_verified",1)
            control("advance 2001");assert exchange("/api/v1/lan/provision",payload,key)[1]["error"]=="PROVISION_INTENT_INVALID"
            record("consumed_intent",1)
            control("boot saved");assert exchange("/api/v1/lan/status")[1]["state"]=="STA_CONNECTING"
            stats=control("stats");assert stats["wpa2_applied"] and stats["sdk_writes"]==1
            rows.append(dict(case="reboot_saved_reconnect_no_rewrite",sdk_writes=1,ap_preserved=True))
            key=intent();assert exchange("/api/v1/lan/provision",payload,key)[0]==200
            record("identical_saved_no_rewrite",1)
            for fault,error in (("sta","PROVISION_STA_ENABLE_FAILED"),("read","PROVISION_SDK_READ_FAILED"),
                  ("write","PROVISION_SDK_WRITE_FAILED_UNKNOWN"),("write-after","PROVISION_SDK_WRITE_FAILED_UNKNOWN"),
                  ("readback","PROVISION_READBACK_FAILED_UNKNOWN"),("mismatch","PROVISION_READBACK_MISMATCH_UNKNOWN"),
                  ("heap","PROVISION_MEMORY_HOLD")):
                reset();key=intent();control("fault "+fault)
                code,reply=exchange("/api/v1/lan/provision",payload,key)
                assert code==409 and reply=={"error":error},(fault,code,reply)
                record("sdk_fault_"+fault,1 if fault in ("write","write-after","readback","mismatch") else 0)
                if fault in ("write","write-after","readback","mismatch"):
                    assert exchange("/api/v1/lan/status")[1]["credential_state"]=="UNKNOWN"
            for kind in ("incomplete","interrupted","extra","duplicate_intent","bad_payload","expired","wrong_token"):
                reset();key=intent()
                if kind=="incomplete":code,reply=wire(payload[:8],key,declared=len(payload));assert code==409 and reply["error"]=="PROVISION_BODY_INCOMPLETE"
                elif kind=="interrupted":wire(payload[:8],key,declared=len(payload),interrupt=True)
                elif kind=="extra":code,reply=wire(payload+b"X",key,declared=len(payload));assert code==409 and reply["error"]=="PROVISION_BODY_EXTRA"
                elif kind=="duplicate_intent":code,_=wire(payload,key,duplicate=True);assert code is None
                elif kind=="bad_payload":code,reply=exchange("/api/v1/lan/provision",b"C\x00\x00",key);assert code==409 and reply["error"]=="PROVISION_PAYLOAD_INVALID"
                else:
                    if kind=="expired":control("advance 60001")
                    else:key="z"*32
                    code,reply=exchange("/api/v1/lan/provision",payload,key);assert code==409 and reply["error"]=="PROVISION_INTENT_INVALID"
                record(kind,0)
            reset();key=intent()
            other=http.client.HTTPConnection("127.0.0.1",port,timeout=6)
            other.request("GET","/api/v1/lan/status",headers={"Host":authority,"Connection":"close"})
            response=other.getresponse();assert response.status==401;response.read();other.close()
            code,_=exchange("/api/v1/lan/provision",payload,key);assert code==401
            record("concurrent_digest_nonce_post_not_replayed",0)
            reset();key=intent();wire(payload,key,drop_reply=True);record("lost_reply_after_write_no_replay",1)
            control("advance 2001");control("mode lan");authority="192.168.1.82"
            code,status=exchange("/api/v1/lan/status");assert code==200 and status["sta_online"] and status["lan_ip"]==authority
            sample=b'{"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120}'
            assert exchange("/api/v1/bridge/metrics",sample,extra={"Content-Type":"application/json"})[0]==200
            before=exchange("/api/v1/update/status")[1];assert before["metrics_fresh"] and before["fs_ok"]
            assert control("stats")["cards"]>=4
            record("lan_digest_metrics_four_cards",1)
            assert exchange("/api/v1/lan/intent")[0]==403
            assert exchange("/api/v1/lan/provision",payload,"a"*32)[0]==403
            record("lan_provision_refused",1)
            assert exchange("/api/v1/lan/status",extra={"Origin":"http://foreign.invalid"})[0]==403
            control("peer foreign");assert exchange("/api/v1/update/status")[0]==403
            record("foreign_origin_and_subnet_refused",1)
            control("mode lan")
            # Entire actual normal HMAC/Core path, including RAM staging/RTC.
            before=exchange("/api/v1/update/status")[1]
            headers={"Host":authority,"Content-Type":"application/octet-stream","Connection":"close",
                     "X-Shino-SHA256":target["sha256"],"X-Shino-Build":target["build_id"],"X-Shino-Nonce":before["nonce"]}
            headers["X-Shino-Proof"]=signature(dict(device=device,maintenance_password=PASSWORD),before["nonce"],target)
            connection=http.client.HTTPConnection("127.0.0.1",port,timeout=15)
            rejected=dict(headers,**{"X-Shino-Proof":"0"*64})
            connection.request("POST","/api/v1/update",body=raw,headers=rejected)
            response=connection.getresponse();assert response.status==503;response.read();connection.close()
            assert control("stats")["flash_writes"]==0
            before=exchange("/api/v1/update/status")[1];headers["X-Shino-Nonce"]=before["nonce"]
            headers["X-Shino-Proof"]=signature(dict(device=device,maintenance_password=PASSWORD),before["nonce"],target)
            connection=http.client.HTTPConnection("127.0.0.1",port,timeout=15)
            connection.request("POST","/api/v1/update",body=raw,headers=headers)
            response=connection.getresponse();receipt=json.loads(response.read());assert response.status==200 and receipt["status"]=="STAGED_PENDING_BOOT",receipt
            connection.close();stats=control("stats");assert stats["restarts"]==1
            process.stdin.write("stop\n");process.stdin.flush();out,err=process.communicate(timeout=8)
            if process.returncode:raise RuntimeError(err)
            final=json.loads(out);assert final["restarts"]==1 and final["flash_writes"]>0
            return dict(cases=len(rows),rows=rows,lan_hmac_ota=True,invalid_hmac_no_write=True,
                        exact_compiled_bin=binary is not None,exact_current_bin=current_binary is not None,
                        uploaded_bytes=len(raw),ota=receipt,network="HOST_LOOPBACK",radio_sdk_flash_rtc="MOCKED",
                        device_contacts=0,physical="NOT_RUN")
        finally:
            if process.poll() is None:process.kill();process.communicate()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("bin","manifest","current-bin","current-manifest"):parser.add_argument("--"+name,type=Path)
    a=parser.parse_args();print(json.dumps(run(a.bin,a.manifest,a.current_bin,a.current_manifest),indent=2))
