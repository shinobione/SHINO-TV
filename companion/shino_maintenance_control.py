"""SHINO // Wi-Fi maintenance arm and dry-run transport.

SAFE DEFAULT: NO NETWORK. This is a pre-release client with real auth logic,
not a physical permission to access the owner's existing SmallTV. Requires
separate exact private image/user authorization before deployment.
"""
import argparse,getpass,hashlib,hmac,ipaddress,json,re,sys,urllib.request
from pathlib import Path
from shino_install import inspect,SocketIO,capability,InstallError,proof

QUALIFIED_NETWORK_PROBE=False
HEX16=re.compile(r'[0-9a-f]{16}\Z')
HEX32=re.compile(r'[0-9a-f]{32}\Z')
HEX64=re.compile(r'[0-9a-f]{64}\Z')

def parse_challenge(data,expected_device):
    if len(data)>512:raise InstallError('Oversize challenge')
    def no_duplicates(pairs):
        x={}
        for k,v in pairs:
            if k in x:raise InstallError('Duplicate challenge field')
            x[k]=v
        return x
    obj=json.loads(data.decode('ascii'),object_pairs_hook=no_duplicates)
    if set(obj)!={'nonce','device','build'} or not isinstance(obj['nonce'],str) or not HEX32.fullmatch(obj['nonce']) or not isinstance(obj['device'],str) or not HEX16.fullmatch(obj['device']) or obj['device']!=expected_device or not isinstance(obj['build'],str) or not HEX64.fullmatch(obj['build']):
        raise InstallError('Unauthenticated/wrong device challenge')
    return obj

def arm_message(device,build,nonce,mode):
    if mode not in ('PROBE','INSTALL') or not HEX16.fullmatch(device) or not HEX64.fullmatch(build) or not HEX32.fullmatch(nonce):
        raise InstallError('Invalid maintenance arm identity')
    return f'SHINO_ARM_1 {device} {build} {nonce} {mode}'

def prepare_arm(challenge,expected_device,password,mode):
    if len(password)<32:raise InstallError('Maintenance password must have >=32 characters')
    obj=parse_challenge(challenge,expected_device)
    key=hashlib.sha256(password.encode('utf-8')).digest()
    mac=hmac.new(key,arm_message(obj['device'],obj['build'],obj['nonce'],mode).encode('ascii'),hashlib.sha256).hexdigest()
    return obj,mac

def digest_open(host,user,password):
    if str(ipaddress.IPv4Address(host))!='192.168.4.1':
        raise InstallError('Only SHINO private AP 192.168.4.1 is supported')
    manager=urllib.request.HTTPPasswordMgrWithDefaultRealm()
    manager.add_password(None,f'http://{host}/',user,password)
    # No Basic handler. The private StageA requires HTTP Digest for reads.
    return urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(manager))

def arm_by_digest(opener,device,password,mode):
    root='http://192.168.4.1/api/v1/m9/maintenance/'
    with opener.open(urllib.request.Request(root+'challenge',method='GET'),timeout=5) as res:
        if res.status!=200:raise InstallError('No authenticated maintenance challenge')
        obj,signature=prepare_arm(res.read(513),device,password,mode)
    url=root+('probe' if mode=='PROBE' else 'install')
    req=urllib.request.Request(url,method='GET',headers={'X-Shino-Arm':signature})
    with opener.open(req,timeout=5) as res:
        if res.status!=202:raise InstallError('Maintenance request denied')
        answer=json.loads(res.read(512).decode('ascii'))
        if answer!={'pending':mode}:raise InstallError('Unexpected owner-arm reply')
    return obj

def upload_probe(io,device,password,manifest,image):
    # Same HMAC and exact chunk format as the writer protocol, but only a
    # PROBED reply is acceptable; STAGED is explicitly an ERROR for a probe.
    key=hashlib.sha256(password.encode('utf-8')).digest()
    from secrets import token_hex
    cn=token_hex(16)
    cap=capability(io,device,key,cn)
    if cap[3] != manifest['build_id'] and not HEX64.fullmatch(cap[3]):
        raise InstallError('Wrong receiver build ID')
    signed=f'AUTH {device} {cn} {cap[6]} 0 {len(image)} {manifest["sha256"]} {manifest["build_id"]}'
    io.line(f'AUTH 0 {len(image)} {manifest["sha256"]} {manifest["build_id"]} {proof(key,signed)}')
    if io.read()!='READY':raise InstallError('Probe admission denied')
    for at in range(0,len(image),512):
        io.write(image[at:at+512])
        if io.read()!=f'ACK {min(at+512,len(image))}':
            raise InstallError('Probe transfer stopped: no retry')
    io.line('COMMIT')
    if io.read()!=f'PROBED {manifest["build_id"]}':
        raise InstallError('Probe did not report RAM-only success; do NOT install')
    return 'PROBED_PENDING_HTTP_RESULT'

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--device',required=True)
    p.add_argument('--live-probe',action='store_true')
    a=p.parse_args(argv)
    m,_=inspect(a.image,a.manifest)
    if not HEX16.fullmatch(a.device):raise InstallError('Device identity must be 16 lowercase hex characters')
    if not a.live_probe:
        print(json.dumps({'status':'VERIFIED_OFFLINE_NO_DEVICE_CONTACT','image_sha256':m['sha256'],
                          'probe_protocol':'SHINO_ARM_1 then CAP/AUTH/PROBED','network_enabled':False}))
        return 0
    if not QUALIFIED_NETWORK_PROBE:
        raise InstallError('NO_GO: no owner-qualified private transition image; network probe disabled')
    # Future consent path only. It is unreachable in this offline artifact.
    user=input('StageA Digest username: ').strip()
    http_secret=getpass.getpass('StageA Digest password: ')
    maintenance_secret=getpass.getpass('Distinct maintenance password (>=32 chars): ')
    opener=digest_open('192.168.4.1',user,http_secret)
    arm_by_digest(opener,a.device,maintenance_secret,'PROBE')
    import time,socket
    io=None
    for _ in range(6):
        try:io=SocketIO('192.168.4.1');break
        except (socket.timeout,ConnectionRefusedError):time.sleep(0.2)
    if io is None:raise InstallError('Probe listener never appeared')
    try:print(upload_probe(io,a.device,maintenance_secret,m,a.image.read_bytes()))
    finally:io.close()
    with opener.open('http://192.168.4.1/api/v1/m9/maintenance/result',timeout=5) as res:
        status=json.loads(res.read(513).decode('ascii'))
    print(json.dumps(status,indent=2))
    return 0 if status.get('probe_qualified') is True else 2

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,TypeError) as ex:
        print('SHINO probe refused: '+str(ex),file=sys.stderr)
        raise SystemExit(2)
