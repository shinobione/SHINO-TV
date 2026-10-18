"""Freebox cache-only publisher. Disabled unless explicitly configured/approved.

Only GET/POST /api/v1/weather; no Digest/OTA authority, discovery or retries.
"""
import argparse
from contextlib import contextmanager
import datetime as dt
from decimal import Decimal
import ipaddress
import json
import math
import os
from pathlib import Path
import socket
import stat
import tempfile
import time
from . import protocol

APPROVAL='OWNER_APPROVED_B54_LAN_POST_V1'
DEFAULT_CONFIG=Path('/etc/shino-weather/publisher.json')
CACHE=Path('/var/lib/shino-weather/latest.json')
STATE=Path('/var/lib/shino-weather/publish-state.json')

def _pairs(items):
    out={}
    for k,v in items:
        if k in out:raise ValueError('DUPLICATE_JSON_KEY')
        out[k]=v
    return out

def read_json(path,limit):
    path=Path(path)
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('FILE_POLICY')
        raw=stream.read(limit+1)
    if len(raw)>limit:raise ValueError('FILE_LIMIT')
    try:return json.loads(raw,object_pairs_hook=_pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('JSON_CONSTANT')))
    except RecursionError:raise ValueError('JSON_DEPTH') from None

def epoch(value):
    if type(value) is not str or len(value)!=20:raise ValueError('TIME_FORMAT')
    stamp=dt.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
    result=int(stamp.timestamp())
    if not 1577836800<=result<=4102444799:raise ValueError('TIME_RANGE')
    return result

def validated_cache(path,now):
    d=read_json(path,16384)
    if type(d) is not dict or set(d)!={'schema','source','location','temperature_c','wmo_code','observed_at_utc','fetched_at_utc','expires_at_utc'}:
        raise ValueError('CACHE_SCHEMA')
    if type(d['schema']) is not int or d['schema']!=1 or d['source']!='open-meteo-https':raise ValueError('CACHE_SOURCE')
    loc=d['location']
    if type(loc) is not dict or set(loc)!={'name','latitude','longitude'} or loc['name']!='DEMO-CITY':raise ValueError('CACHE_LOCATION')
    for k,v in (('latitude',0.0),('longitude',0.0)):
        if type(loc[k]) not in (int,float) or not math.isfinite(loc[k]) or loc[k]!=v:raise ValueError('CACHE_LOCATION')
    t=d['temperature_c'];w=d['wmo_code']
    if type(t) not in (int,float) or not math.isfinite(t) or not -90<=t<=65:raise ValueError('CACHE_TEMPERATURE')
    tenths=Decimal(str(t))*10
    if tenths!=tenths.to_integral_value():raise ValueError('CACHE_PRECISION')
    if type(w) is not int or w not in protocol.WMO:raise ValueError('CACHE_WMO')
    observed=epoch(d['observed_at_utc']);fetched=epoch(d['fetched_at_utc']);expires=epoch(d['expires_at_utc'])
    if (expires!=observed+2700 or observed>now+60 or fetched>now+60 or fetched<observed-60 or
        fetched>=expires or now>=expires):raise ValueError('CACHE_AGE')
    return dict(observed=observed,ttl=2700,tenths=int(tenths),wmo=w)

def config(path):
    d=read_json(path,4096)
    if type(d) is not dict or set(d)!={'schema','enabled','authorization','target','device','location','key_file'}:
        raise ValueError('CONFIG_SCHEMA')
    if type(d['schema']) is not int or d['schema']!=1 or type(d['enabled']) is not bool:raise ValueError('CONFIG_SCHEMA')
    if not d['enabled']:return d
    if d['authorization']!=APPROVAL:raise ValueError('EXPLICIT_APPROVAL_REQUIRED')
    ip=ipaddress.ip_address(d['target'])
    if ip.version!=4 or not any(ip in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')):
        raise ValueError('LAN_IPV4_REQUIRED')
    for k in ('device','location'):
        v=d[k]
        if type(v) is not str or len(v)!=16 or any(c not in '0123456789abcdef' for c in v) or not any(bytes.fromhex(v)):
            raise ValueError('CONFIG_IDENTITY')
    if bytes.fromhex(d['location'])!=protocol.LOCATION:raise ValueError('CONFIG_LOCATION')
    return d

def read_key(path):
    path=Path(path)
    if path.is_symlink():raise ValueError('KEY_POLICY')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):raise ValueError('KEY_POLICY')
        if os.name=='posix' and info.st_mode&0o077:raise ValueError('KEY_PERMISSIONS')
        key=stream.read(33)
    if len(key)!=32 or not any(key):raise ValueError('KEY_LENGTH')
    return key

def atomic_json(path,value):
    path=Path(path)
    if path.is_symlink() or not path.parent.is_dir():raise ValueError('STATE_POLICY')
    raw=(json.dumps(value,separators=(',',':'))+'\n').encode()
    fd,name=tempfile.mkstemp(prefix='.publish-',dir=path.parent)
    try:
        os.chmod(name,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
        if os.name=='posix':
            directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(directory)
            finally:os.close(directory)
    finally:
        if os.path.exists(name):os.unlink(name)

@contextmanager
def locked(path):
    fd=os.open(str(path)+'.lock',os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        if os.name=='nt':
            import msvcrt
            if os.fstat(fd).st_size==0:os.write(fd,b'0')
            os.lseek(fd,0,0);msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd) # OS releases lock on exit/crash, no stale PID lease.

class LanTransport:
    """One numeric-IPv4 connection per call; capped headers/body and total2 s."""
    def _connect(self,peer,ip):peer.connect((str(ip),80))
    def exchange(self,ip,method,path,body=b''):
        prefix='/api/v1/weather/status/'
        status_path=(type(path) is str and path.startswith(prefix) and len(path)==len(prefix)+16 and
                     all(c in '0123456789abcdef' for c in path[len(prefix):]))
        if not ((method=='POST' and path=='/api/v1/weather' and type(body) is bytes and len(body)==80) or
                (method=='GET' and status_path and body==b'')):
            raise ValueError('ROUTE_POLICY')
        start=time.monotonic();deadline=start+2
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as peer:
            peer.settimeout(2);self._connect(peer,ip)
            headers=f'{method} {path} HTTP/1.1\r\nHost: {ip}\r\nConnection: close\r\nAccept: application/octet-stream\r\n'
            if method=='POST':headers+='Content-Type: application/octet-stream\r\nContent-Length: 80\r\n'
            peer.settimeout(max(0.001,deadline-time.monotonic()));peer.sendall(headers.encode('ascii')+b'\r\n'+body)
            raw=b''
            while b'\r\n\r\n' not in raw:
                left=deadline-time.monotonic()
                if left<=0:raise TimeoutError('HTTP_DEADLINE')
                peer.settimeout(left);block=peer.recv(min(512,2049-len(raw)))
                if not block:raise ValueError('HTTP_TRUNCATED_HEADERS')
                raw+=block
                if len(raw)>2048:raise ValueError('HTTP_HEADER_LIMIT')
            head,raw=raw.split(b'\r\n\r\n',1);lines=head.decode('ascii').split('\r\n')
            if lines[0] not in ('HTTP/1.1 200 OK','HTTP/1.0 200 OK'):raise ValueError('FIRMWARE_UNSUPPORTED_OR_HTTP_STATUS')
            fields={}
            for line in lines[1:]:
                name,sep,val=line.partition(':');name=name.lower();val=val.strip()
                if not sep or name in fields:raise ValueError('HTTP_HEADERS')
                fields[name]=val
            if (fields.get('content-length')!='80' or fields.get('content-type')!='application/octet-stream' or
                'transfer-encoding' in fields):raise ValueError('HTTP_FRAMING')
            while len(raw)<80:
                left=deadline-time.monotonic()
                if left<=0:raise TimeoutError('HTTP_DEADLINE')
                peer.settimeout(left);block=peer.recv(81-len(raw))
                if not block:raise ValueError('HTTP_TRUNCATED_BODY')
                raw+=block
            if len(raw)!=80 or time.monotonic()>=deadline:raise ValueError('HTTP_BODY_OR_DEADLINE')
            return raw

def run_once(config_path=DEFAULT_CONFIG,cache_path=CACHE,state_path=STATE,*,transport=None,now=None,nonce=None):
    d=config(config_path)
    if not d['enabled']:return 'DISABLED' # No key/cache/state/network access.
    now=int(time.time()) if now is None else now
    if type(now) is not int or not 1577836800<=now<=4102444799:raise ValueError('HOST_CLOCK')
    cached=validated_cache(cache_path,now);state_path=Path(state_path)
    with locked(state_path):
        ledger=read_json(state_path,2048) if state_path.exists() else None
        if ledger is not None:
            if (type(ledger) is not dict or set(ledger)!={'schema','device','boot','sequence','observed','attempted'} or
                type(ledger['schema']) is not int or ledger['schema']!=1 or ledger['device']!=d['device'] or
                any(type(ledger[k]) is not int for k in ('sequence','observed','attempted')) or
                not 1<=ledger['sequence']<=0xffffffff or
                not 1577836800<=ledger['observed']<=4102444799 or not 1577836800<=ledger['attempted']<=4102444799 or
                type(ledger['boot']) is not str or len(ledger['boot'])!=16 or
                any(c not in '0123456789abcdef' for c in ledger['boot']) or not any(bytes.fromhex(ledger['boot']))):raise ValueError('LEDGER_INVALID')
            if now<ledger['attempted'] or now-ledger['attempted']<1800:return 'CADENCE_HOLD'
        key=read_key(d['key_file']);device=bytes.fromhex(d['device']);location=bytes.fromhex(d['location'])
        challenge=os.urandom(8) if nonce is None else nonce
        if type(challenge) is not bytes or len(challenge)!=8:raise ValueError('CHALLENGE')
        transport=LanTransport() if transport is None else transport
        raw=transport.exchange(d['target'],'GET','/api/v1/weather/status/'+challenge.hex())
        status=protocol.verify(key,raw,2,device,location,challenge=challenge)
        if not 1577836800<=status['utc']<=4102444799 or abs(status['utc']-now)>60:raise ValueError('TARGET_CLOCK')
        if ledger and ledger['boot']==status['boot'].hex() and cached['observed']<=ledger['observed']:return 'ALREADY_ATTEMPTED'
        sequence=status['sequence']+1
        if sequence>0xffffffff:raise ValueError('SEQUENCE_EXHAUSTED')
        frame=protocol.sample(key,device,status['boot'],sequence,location=location,**cached)
        atomic_json(state_path,dict(schema=1,device=d['device'],boot=status['boot'].hex(),sequence=sequence,
                                   observed=cached['observed'],attempted=now))
        # Intent is durable BEFORE POST. No retry, including timeout/lost ACK.
        try:
            reply=transport.exchange(d['target'],'POST','/api/v1/weather',frame)
            ack=protocol.verify(key,reply,3,device,location,boot=status['boot'],challenge=frame[48:56])
            if ack['sequence']!=sequence:raise ValueError('ACK_SEQUENCE')
        except (OSError,ValueError):return 'UNKNOWN_NO_RETRY'
        return 'PUBLISHED'

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,default=DEFAULT_CONFIG)
    args=parser.parse_args(argv)
    try:result=run_once(args.config)
    except (OSError,ValueError,KeyError,TypeError,OverflowError):result='REFUSED_OR_UNAVAILABLE'
    print('SHINO-WEATHER PUBLISH '+result)
    return 0 if result in ('DISABLED','PUBLISHED','CADENCE_HOLD','ALREADY_ATTEMPTED') else 1
