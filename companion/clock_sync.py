"""B5.2 paired-PC clock source. CLI is inspect-only; writes require explicit opt-in.

No private identity loader, firmware build or device operation runs on import.
The library writer uses the normal Digest coordinator and never replays a POST.
"""
from __future__ import annotations
import argparse
import contextlib
import http.client
import json
import math
import hashlib
import hmac
import struct
import socket
import threading
import time
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler,HTTPPasswordMgrWithDefaultRealm,HTTPHandler
from provision_home_wifi import WifiDigest
from push_fsless_metrics import NoRedirect
from shino_digest_coord import digest_exchange,CoordinationBusy,_safe_host

MAX_LEASE_S=120
TRANSIT_MARGIN_S=8
MIN_UTC,MAX_UTC=1577836800,4102444799
PROTOCOL="shino-pc-clock-2"
FRAME_BYTES=64
CHALLENGE_MS=2000
KEY_DOMAIN=b"SHINO-PC-CLOCK-KEY-2\n"
SYNC_DOMAIN=b"SHINO-PC-CLOCK-SYNC-2\n"
TOTAL_EXCHANGE_S=1.0

class ClockHold(ValueError):pass

class Deadline:
    """One absolute locked exchange budget; trickles cannot renew it."""
    def __init__(self):
        self.until=time.monotonic()+TOTAL_EXCHANGE_S
        self.expired=threading.Event();self.sockets=[];self.mutex=threading.Lock()
        self.posts=0;self.requests=0
        self.timer=threading.Timer(TOTAL_EXCHANGE_S,self.abort)
        self.timer.daemon=True;self.timer.start()
    def _close_sockets(self):
        with self.mutex:peers=tuple(self.sockets)
        for peer in peers:
            try:peer.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            try:peer.close()
            except OSError:pass
    def abort(self):
        self.expired.set();self._close_sockets()
    def check(self):
        if self.expired.is_set() or time.monotonic()>=self.until:
            raise ClockHold("CLOCK_TIMEOUT")
    def timeout(self):
        self.check();return max(.001,self.until-time.monotonic())
    def register(self,peer):
        with self.mutex:self.sockets.append(peer)
        try:self.check()
        except ClockHold:
            self._close_sockets();raise
    def close(self):
        self.timer.cancel();self._close_sockets()

class ClockConnection(http.client.HTTPConnection):
    def __init__(self,host,guard,**kwargs):
        self.guard=guard
        kwargs["timeout"]=guard.timeout()
        super().__init__(host,**kwargs)
    def connect(self):
        self.guard.check();super().connect();self.guard.register(self.sock)
    def request(self,method,url,body=None,headers=None,**kwargs):
        self.guard.check()
        if ((method=="GET" and (url!="/api/v1/clock/status" or body is not None)) or
            (method=="POST" and (url!="/api/v1/clock/sync" or type(body) is not bytes or len(body)!=FRAME_BYTES)) or
            method not in ("GET","POST") or self.guard.requests>=3 or
            (method=="POST" and self.guard.posts)):
            raise ClockHold("CLOCK_REQUEST_HOLD")
        self.guard.requests+=1
        if method=="POST":self.guard.posts+=1 # before connect/send
        return super().request(method,url,body,headers or {},**kwargs)

class ClockHTTPHandler(HTTPHandler):
    def __init__(self,owner):super().__init__();self.owner=owner
    def http_open(self,req):
        guard=self.owner._active_guard()
        return self.do_open(lambda host,**kwargs:ClockConnection(host,guard,**kwargs),req)

def capture_pc_clock(*,wall=time.time,local=lambda n:datetime.fromtimestamp(n).astimezone()):
    instant=wall()
    if type(instant) not in (int,float) or not math.isfinite(instant) or not MIN_UTC<=instant<MAX_UTC+1:
        raise ClockHold("CLOCK_UNAVAILABLE")
    utc=int(instant)
    def offset_at(epoch):
        value=local(epoch).utcoffset()
        if value is None:raise ClockHold("CLOCK_TIMEZONE_UNAVAILABLE")
        seconds=value.total_seconds()
        if not math.isfinite(seconds) or seconds%60 or not -720<=seconds/60<=840:
            raise ClockHold("CLOCK_TIMEZONE_INVALID")
        return int(seconds/60)
    offset=offset_at(utc)
    lease=MAX_LEASE_S
    # Expire BEFORE an OS offset transition, with conservative transit slack.
    if offset_at(utc+MAX_LEASE_S)!=offset:
        for delta in range(1,MAX_LEASE_S+1):
            if offset_at(utc+delta)!=offset:
                lease=delta-TRANSIT_MARGIN_S
                break
        if lease<1:raise ClockHold("CLOCK_OFFSET_TRANSITION")
    return dict(schema=1,utc_s=utc,offset_min=offset,lease_s=lease)

def encode(sample):
    if (type(sample) is not dict or set(sample)!={"schema","utc_s","offset_min","lease_s"} or
        any(type(v) is not int for v in sample.values()) or sample["schema"]!=1 or
        not MIN_UTC<=sample["utc_s"]<=MAX_UTC or not -720<=sample["offset_min"]<=840 or
        not 1<=sample["lease_s"]<=MAX_LEASE_S):
        raise ClockHold("CLOCK_SAMPLE_INVALID")
    return b"SHINOCL2"+struct.pack("<IhH",sample["utc_s"],sample["offset_min"],sample["lease_s"])

def derive_key(password):
    if type(password) is not str or not password:raise ClockHold("CLOCK_KEY_UNAVAILABLE")
    return hmac.digest(password.encode("utf-8"),KEY_DOMAIN,"sha256")

def challenge_tokens(status):
    if (type(status) is not dict or status.get("protocol")!=PROTOCOL or status.get("clock_enabled") is not True or
        type(status.get("challenge_ms")) is not int or status["challenge_ms"]!=CHALLENGE_MS):
        raise ClockHold("CLOCK_CHALLENGE_INVALID")
    tokens=[]
    for name in ("boot","challenge"):
        value=status.get(name)
        if type(value) is not str or len(value)!=32 or any(c not in "0123456789abcdef" for c in value):
            raise ClockHold("CLOCK_CHALLENGE_INVALID")
        token=bytes.fromhex(value)
        if not any(token):raise ClockHold("CLOCK_CHALLENGE_INVALID")
        tokens.append(token)
    if tokens[0]==tokens[1]:raise ClockHold("CLOCK_CHALLENGE_INVALID")
    return tuple(tokens)

def seal(sample,status,key):
    if type(key) is not bytes or len(key)!=32:raise ClockHold("CLOCK_KEY_UNAVAILABLE")
    boot,nonce=challenge_tokens(status)
    body=encode(sample)+nonce
    return body+hmac.digest(key,SYNC_DOMAIN+boot+body,"sha256")

class ClockDigest(WifiDigest):
    def http_error_401(self,req,fp,code,msg,headers):
        retries=getattr(req,"_clock_challenges",0)
        if req.get_method()=="POST" or retries>=1:
            raise HTTPError(req.full_url,code,msg,headers,fp)
        req._clock_challenges=retries+1
        return super().http_error_401(req,fp,code,msg,headers)

class ClockTransport:
    """Construct only in a separately authorized owner session; no secrets logged."""
    def __init__(self,host,username,digest_password):
        self.host=_safe_host(host)
        self.clock_key=derive_key(digest_password)
        self.base="http://"+self.host
        self._deadline=None;self._owner_thread=None
        passwords=HTTPPasswordMgrWithDefaultRealm()
        passwords.add_password("SHINO-StageA",self.base,username,digest_password)
        self.reader=build_opener(ProxyHandler({}),NoRedirect(),ClockHTTPHandler(self),ClockDigest(passwords,self.base))
    def _active_guard(self):
        if self._deadline is None or self._owner_thread!=threading.get_ident():
            raise ClockHold("CLOCK_SESSION_REQUIRED")
        self._deadline.check();return self._deadline
    @contextlib.contextmanager
    def session(self):
        if self._deadline is not None:raise ClockHold("CLOCK_BUSY")
        self._deadline=Deadline();self._owner_thread=threading.get_ident()
        try:
            yield
            self._deadline.check()
        finally:
            self._deadline.close();self._deadline=None;self._owner_thread=None
    def _request(self,body=None):
        guard=self._active_guard()
        req=Request(self.base+("/api/v1/clock/status" if body is None else "/api/v1/clock/sync"),
            data=body,method="GET" if body is None else "POST",
            headers={"Content-Type":"application/octet-stream","Connection":"close","Cache-Control":"no-store"})
        try:
            with self.reader.open(req,timeout=guard.timeout()) as response:
                raw=response.read(385)
                guard.check()
                if response.status!=200 or len(raw)>384:raise ClockHold("CLOCK_RESPONSE_BOUND")
        except HTTPError as error:
            error.close()
            raise
        packet=json.loads(raw)
        guard.check()
        if type(packet) is not dict:raise ClockHold("CLOCK_RESPONSE_INVALID")
        return packet
    def prepare(self):return self._request()
    def post(self,raw):return self._request(raw)

def publish_clock(host,transport,*,authorize_clock_sync=False,cancelled=None):
    if authorize_clock_sync is not True:return "CLOCK_DISABLED_NO_IO"
    host=_safe_host(host)
    if isinstance(transport,ClockTransport) and transport.host!=host:
        raise ClockHold("CLOCK_HOST_MISMATCH")
    posted=False
    try:
        if cancelled is not None and cancelled():return "CLOCK_STOPPED_NO_RETRY"
        with digest_exchange(host,wait_seconds=0):
            with transport.session() if isinstance(transport,ClockTransport) else contextlib.nullcontext():
                if cancelled is not None and cancelled():return "CLOCK_STOPPED_NO_RETRY"
                status=transport.prepare()
                if type(status) is not dict or status.get("protocol")!=PROTOCOL or status.get("clock_enabled") is not True:
                    return "CLOCK_COMPATIBILITY_HOLD"
                challenge_tokens(status)
                sample=capture_pc_clock() # after lock/auth/status readiness
                frame=seal(sample,status,transport.clock_key)
                if cancelled is not None and cancelled():return "CLOCK_STOPPED_NO_RETRY"
                posted=True
                reply=transport.post(frame) # one call; no refresh or retry
                if type(reply) is dict and set(reply)=={"status","persisted"} and reply.get("status")=="CLOCK_SAMPLE_ACCEPTED" and reply.get("persisted") is False:
                    return "CLOCK_SAMPLE_ACCEPTED"
                return "CLOCK_UNKNOWN_NO_RETRY"
    except CoordinationBusy:return "CLOCK_COORDINATION_HOLD"
    except HTTPError as error:
        if not posted and error.code in (404,405):return "CLOCK_COMPATIBILITY_HOLD"
        return "CLOCK_UNKNOWN_NO_RETRY" if posted else "CLOCK_SOURCE_HOLD"
    except Exception:
        return "CLOCK_UNKNOWN_NO_RETRY" if posted else "CLOCK_SOURCE_HOLD"

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("inspect",))
    args=parser.parse_args(argv)
    if args.mode=="inspect":
        sample=capture_pc_clock()
        print(json.dumps(dict(mode="OFFLINE_INSPECT",device_contacts=0,packet_bytes=FRAME_BYTES,sample_bytes=len(encode(sample)),
            sample=sample,source="LOCAL_PC_SYSTEM_CLOCK",windows_time_service_accuracy="NOT_VERIFIED")))
if __name__=="__main__":main()

