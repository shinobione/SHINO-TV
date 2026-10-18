"""SHINO-WX v1 fixed binary contract; no I/O."""
import hashlib
import hmac
import struct

DOMAINS = {1:b'SHINO-WX/SAMPLE/1',2:b'SHINO-WX/STATUS/1',3:b'SHINO-WX/ACK/1'}
LOCATION = b'DEMO0001'
FRAME_BYTES = 80
WMO = frozenset((0,1,2,3,45,48,51,53,55,56,57,61,63,65,66,67,71,73,75,77,80,81,82,85,86,95,96,99))

def sample(key, device, boot, sequence, observed, ttl, tenths, wmo, location=LOCATION):
    if (type(sequence) is not int or not 1<=sequence<=0xffffffff or
        type(observed) is not int or not 1577836800<=observed<=4102444799 or
        type(ttl) is not int or not 1<=ttl<=2700 or
        type(tenths) is not int or not -900<=tenths<=650 or
        type(wmo) is not int or wmo not in WMO):
        raise ValueError('SAMPLE_FIELDS')
    identities(device,boot,location)
    fields=struct.pack('!4sBBH8s8sIIHhB3s8s',b'SWX1',1,1,80,device,boot,
                       sequence,observed,ttl,tenths,wmo,b'\0'*3,location)
    return sign(key,fields)

def identities(device,boot,location):
    if any(type(v) is not bytes or len(v)!=8 or not any(v) for v in (device,boot,location)):
        raise ValueError('IDENTITY_FIELDS')

def sign(key,fields):
    if type(key) is not bytes or len(key)!=32 or type(fields) is not bytes or len(fields)!=48:
        raise ValueError('MAC_INPUT')
    kind=fields[5]
    if kind not in DOMAINS:raise ValueError('TYPE')
    return fields+hmac.digest(key,DOMAINS[kind]+fields,'sha256')

def status(key,device,boot,sequence,challenge,utc,location=LOCATION,kind=2):
    identities(device,boot,location)
    if (kind not in (2,3) or type(sequence) is not int or not 0<=sequence<=0xffffffff or
        type(challenge) is not bytes or len(challenge)!=8 or
        type(utc) is not int or not 0<=utc<=4102444799):raise ValueError('STATUS_FIELDS')
    return sign(key,struct.pack('!4sBBH8s8sI8sI8s',b'SWX1',1,kind,80,device,boot,
                               sequence,challenge,utc,location))

def verify(key,wire,kind,device,location=LOCATION,boot=None,challenge=None):
    if (type(wire) is not bytes or len(wire)!=80 or kind not in DOMAINS or
        wire[:4]!=b'SWX1' or wire[4:8]!=bytes((1,kind,0,80))):raise ValueError('FRAME')
    expected=sign(key,wire[:48])[48:]
    if not hmac.compare_digest(expected,wire[48:]):raise ValueError('MAC')
    if wire[8:16]!=device or wire[40:48]!=location:raise ValueError('TARGET')
    if not any(wire[16:24]) or (boot is not None and wire[16:24]!=boot):raise ValueError('BOOT')
    seq=struct.unpack_from('!I',wire,24)[0]
    out=dict(device=wire[8:16],boot=wire[16:24],sequence=seq,location=wire[40:48])
    if kind==1:
        obs,ttl,temp,code=struct.unpack_from('!IHhB',wire,28)
        if wire[37:40]!=b'\0'*3:raise ValueError('RESERVED')
        sample(key,device,wire[16:24],seq,obs,ttl,temp,code,location)
        out.update(observed=obs,ttl=ttl,tenths=temp,wmo=code)
    else:
        if challenge is None or wire[28:36]!=challenge:raise ValueError('CHALLENGE')
        out.update(utc=struct.unpack_from('!I',wire,36)[0])
    return out
