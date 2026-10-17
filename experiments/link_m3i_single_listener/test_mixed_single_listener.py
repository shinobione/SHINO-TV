"""M3-I: real loopback TCP with *one* server process, 2 isolated auth schemes.

- Original FslessMetrics.cpp/ArduinoJson 7.4.3 in this very process;
- Original dashboard assets and M3-G disposable Digest/session model;
- Original M3-C actual prebody HMAC/SHA256/canonical-body Gate.
All tokens, credentials and keys below are PUBLIC TEST VECTORS. NO DEVICE.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
import unittest

DEVICE="1234567890abcdef"
BOOT="1234567890abcdef1234567890abcdef"
HOST_HEADER="192.168.4.1"  # Never used as a network destination.
KEY=bytes(range(1,33))
USERNAME="shino"
PASSWORD="disposable-only-never-owner-password"
REALM="SHINO-FirstBoot"
NONCE="0123456789abcdef0123456789abcdef"
TX1="00000000000000000000000000000001"
TX2="00000000000000000000000000000002"
TX3="00000000000000000000000000000003"

def md5(value):
    return hashlib.md5(value.encode("ascii")).hexdigest()

def digest(method,path):
    ha1=md5(f"{USERNAME}:{REALM}:{PASSWORD}")
    ha2=md5(f"{method}:{path}")
    cnonce="abcDEF0123456789"
    response=md5(f"{ha1}:{NONCE}:00000001:{cnonce}:auth:{ha2}")
    fields=[f'username="{USERNAME}"',f'realm="{REALM}"',
            f'nonce="{NONCE}"',f'uri="{path}"',
            'algorithm=MD5','qop=auth','nc=00000001',
            f'cnonce="{cnonce}"',f'response="{response}"']
    return "Digest "+", ".join(fields)

def legacy(method,path,body=b"",*,auth=None,cookie=None):
    heads=[f"{method} {path} HTTP/1.1",f"Host: {HOST_HEADER}"]
    if auth: heads.append("Authorization: "+auth)
    if cookie: heads.append("Cookie: "+cookie)
    if method=="POST" and path=="/api/v1/bridge/metrics":
        heads+=["Content-Type: application/json",f"Content-Length: {len(body)}"]
    return ("\r\n".join(heads+["Connection: close"])+"\r\n\r\n").encode()+body

def m3_packet(revision=0,tx=TX1,mode="MUSIC"):
    # Canonical body byte order defined by real pinned M3-C header parser.
    body=json.dumps({
        "boot":BOOT,"device":DEVICE,"mode":mode,
        "protocol":"shino-display-control-1","revision":revision,"tx":tx
    },sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
    body_hash=hashlib.sha256(body).hexdigest()
    signed="\n".join([
        "SHINO-M3-CONTROL-1","POST","/api/v1/display/mode",
        HOST_HEADER,DEVICE,BOOT,str(revision),mode,tx,
        str(len(body)),body_hash]).encode("ascii")
    mac=hmac.new(KEY,signed,hashlib.sha256).hexdigest()
    header=(
        "POST /api/v1/display/mode HTTP/1.1\r\n"
        f"Host: {HOST_HEADER}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        f"X-Shino-Device: {DEVICE}\r\n"
        f"X-Shino-Boot: {BOOT}\r\n"
        f"X-Shino-Revision: {revision}\r\n"
        f"X-Shino-Mode: {mode}\r\n"
        f"X-Shino-Tx: {tx}\r\n"
        f"X-Shino-Body-Sha256: {body_hash}\r\n"
        f"X-Shino-Proof: {mac}\r\n\r\n").encode("ascii")
    return header,body

def extract(raw):
    parts=raw.split(b"\r\n\r\n",1)
    if len(parts)!=2:
        raise AssertionError(f"Bad response from host lab: {raw[:100]!r}")
    first=parts[0].split(b"\r\n",1)[0].split(b" ")
    return int(first[1]),parts[0].decode("latin1"),parts[1]

SAMPLE={
    "ok":True,"cpu_usage":22.5,"gpu_usage":34.5,
    "memory_used_gb":8.0,"memory_total_gb":16.0,
    "gpu_vram_mb":2048.0,"gpu_temp_c":56.0,
    "gpu_power":120.0,"gpu_available":True
}

class SingleListenerMixedIntegration(unittest.TestCase):
    def test_shared_listener_alternating_metrics_and_m3_hmac(self):
        binpath=Path(os.environ["M3I_MIXED_BINARY"])
        self.assertTrue(binpath.is_file())
        count=19
        proc=subprocess.Popen([str(binpath),str(count)],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              text=True,bufsize=1)
        try:
            first=proc.stdout.readline().strip()
            self.assertTrue(first.startswith("INTEGRATED_FIXTURE_PORT "),first)
            port=int(first.split()[-1])
            requests=0
            def call(frame,*,half_close=False,allow_transport_reset=False):
                nonlocal requests
                requests+=1
                with socket.create_connection(("127.0.0.1",port),timeout=4) as s:
                    s.settimeout(4)
                    s.sendall(frame)
                    if half_close: s.shutdown(socket.SHUT_WR)
                    chunks=[]
                    try:
                        while True:
                            part=s.recv(8192)
                            if not part:break
                            chunks.append(part)
                    except ConnectionResetError:
                        # Linux may reset a connection closed with unread
                        # INVALID surplus bytes; allowed for this exact
                        # negative test only. Never silently mask good traffic.
                        if not allow_transport_reset:
                            raise
                        return None,"",b""
                    return extract(b"".join(chunks))
            met="/api/v1/bridge/metrics"
            status,header,_=call(legacy("GET","/"))
            self.assertEqual(status,401)
            self.assertIn("WWW-Authenticate: Digest ",header)
            status,header,page=call(legacy("GET","/",auth=digest("GET","/")))
            self.assertEqual(status,200)
            self.assertIn(b"<!doctype html>",page)
            match=re.search(r"Set-Cookie: (SHINO_READ_SESSION=[0-9a-f]{32});",header)
            self.assertIsNotNone(match)
            cookie=match.group(1)
            status,_,body=call(legacy("GET",met,cookie=cookie))
            self.assertEqual(status,200)
            self.assertFalse(json.loads(body)["received"])
            sample=json.dumps(SAMPLE,separators=(",",":")).encode("ascii")
            status,_,body=call(legacy("POST",met,sample,auth=digest("POST",met)))
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)["persisted"],False)
            status,_,body=call(legacy("GET",met,cookie=cookie))
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)["cpu_usage"],22.5)

            # A forged M3 header must be rejected WITHOUT sending ANY body
            # (and without blocking to wait for that body). No half-close.
            h,b=m3_packet()
            forged=h.replace(b"X-Shino-Mode: MUSIC",b"X-Shino-Mode: AUTO")
            started=time.monotonic()
            status,_,body=call(forged)
            self.assertEqual(status,403)
            self.assertLess(time.monotonic()-started,1.9)
            self.assertIn(b"applied",body)

            status,headers,body=call(h+b,half_close=True)
            self.assertEqual(status,202)
            self.assertIn("M3I_ONLY_NO_DEVICE",headers)
            self.assertFalse(json.loads(body)["applied"])

            status,_,body=call(legacy("GET",met,cookie=cookie))
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)["cpu_usage"],22.5)

            # Exact repeated transaction fails prebody as revision advanced.
            status,_,_=call(h)
            self.assertEqual(status,403)
            h2,b2=m3_packet(1,TX2,"MONITORING")
            status,_,body=call(h2+b2,half_close=True)
            self.assertEqual(status,202)
            self.assertFalse(json.loads(body)["applied"])

            # Tampering with accepted header's body fails SHA/canonical check.
            h3,b3=m3_packet(2,TX3,"AUTO")
            tampered=bytearray(b3)
            tampered[20]^=1
            status,_,_=call(h3+tampered,half_close=True)
            self.assertEqual(status,403)
            # Extra data beyond declared length is rejected before simulated CAS.
            status,_,_=call(h3+b3+b"EXTRA",half_close=True,
                              allow_transport_reset=True)
            # Either explicit 403, or RST on surplus unread TCP bytes.
            # Both must leave revision unchanged, proved by a subsequent
            # valid request with the same revision/tx below.
            self.assertIn(status,(403,None))
            # An ordinary HTTP client without writing FIN waits at most 2s.
            status,_,_=call(h3+b3)
            self.assertEqual(status,408)
            # Legacy telemetry continues even after M3 errors.
            sample2=dict(SAMPLE);sample2["cpu_usage"]=48.0
            status,_,_=call(legacy("POST",met,
                json.dumps(sample2,separators=(",",":")).encode("ascii"),
                auth=digest("POST",met)))
            self.assertEqual(status,200)
            status,_,payload=call(legacy("GET",met,cookie=cookie))
            self.assertEqual(status,200)
            self.assertEqual(json.loads(payload)["cpu_usage"],48)
            # A rejected M3 command never accidentally mutates the M3 ledger.
            status,_,body=call(h3+b3,half_close=True)
            self.assertEqual(status,202)
            self.assertFalse(json.loads(body)["applied"])
            # Disabled sensitive routes cannot be reached via either path.
            status,_,_=call(legacy("POST","/api/v1/bridge/ota/upload"))
            self.assertEqual(status,403)
            status,_,_=call(legacy("POST","/api/v1/bridge/factory-return",
                                  auth=digest("POST","/api/v1/bridge/factory-return")))
            self.assertEqual(status,403)
            status,_,script=call(legacy("GET","/ui.js",cookie=cookie))
            self.assertEqual(status,200)
            self.assertIn(b"fetch(",script)
            self.assertEqual(requests,count)
            out,err=proc.communicate(timeout=6)
            self.assertEqual(proc.returncode,0,err)
            self.assertIn("M3HMAC_REVIEW_ONLY_NO_SCENE 1",out)
            self.assertIn("DEVICE_WRITER 0",out)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=3)

if __name__=="__main__":
    unittest.main(verbosity=2)
