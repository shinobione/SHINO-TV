"""Owner-initiated local provisioning; requires approved/installed P1 firmware.

Secrets are prompted without echo, used in memory, never written to a file.
Never run automatically or against a device during offline implementation/CI.
"""
import argparse
import getpass
import json
import sys
from pathlib import Path
from urllib.request import (Request, build_opener, ProxyHandler,
                            HTTPPasswordMgrWithDefaultRealm, HTTPDigestAuthHandler,
                            parse_http_list, parse_keqv_list)
from push_fsless_metrics import NoRedirect, read_credentials, validate_host

AP_HOST="192.168.4.1"
BASE="/api/v1/bridge/wifi"

class ProvisionError(ValueError):
    pass

class WifiDigest(HTTPDigestAuthHandler):
    """Use the intent GET's real challenge before sending any password body.

    Pre-body refusal may reset a TCP peer which already sent an unauthorized
    body. Send Digest preemptively after the authenticated intent exchange.
    """
    def __init__(self,manager,root):
        super().__init__(manager);self.challenge=None;self.root=root
    def http_error_401(self,req,fp,code,msg,headers):
        value=headers.get('WWW-Authenticate','')
        if value.startswith('Digest '):
            self.challenge=parse_keqv_list(parse_http_list(value[7:]))
        return super().http_error_401(req,fp,code,msg,headers)
    def http_request(self,req):
        if self.challenge and req.full_url.startswith(self.root) and not req.has_header('Authorization'):
            auth=self.get_authorization(req,self.challenge)
            if auth: req.add_unredirected_header('Authorization','Digest '+auth)
        return req

def encode_change(ssid, password):
    try:
        name=ssid.encode('ascii'); secret=password.encode('ascii')
    except UnicodeError:
        raise ProvisionError('P1 supports printable ASCII Wi-Fi names and WPA2 keys') from None
    if not 1<=len(name)<=32 or not 8<=len(secret)<=64 or any(c<32 or c>126 for c in name+secret):
        raise ProvisionError('Invalid SSID or WPA2 key length/characters')
    if len(secret)==64 and any(c not in b'0123456789abcdefABCDEF' for c in secret):
        raise ProvisionError('A 64-character WPA2 key must be hexadecimal')
    return bytearray(b'C'+bytes((len(name),len(secret)))+name+secret)

def opener_for(host, credentials):
    user,password=read_credentials(credentials)
    root='http://'+validate_host(host)+BASE
    manager=HTTPPasswordMgrWithDefaultRealm()
    manager.add_password('SHINO-FirstBoot',root,user,password)
    return build_opener(ProxyHandler({}),NoRedirect(),WifiDigest(manager,root))

def exchange(opener, host, path, body=None, token=None):
    headers={'Accept':'application/json','Cache-Control':'no-store','Connection':'close'}
    if body is not None: headers['Content-Type']='application/octet-stream'
    if token is not None: headers['X-Shino-Wifi-Intent']=token
    request=Request('http://'+host+path,data=body,headers=headers,
                    method='GET' if body is None else 'POST')
    try:
        with opener.open(request,timeout=4) as response:
            if response.status!=200: raise ValueError()
            raw=response.read(513)
        if len(raw)>512: raise ValueError()
        result=json.loads(raw)
        if not isinstance(result,dict): raise ValueError()
        return result
    except Exception:
        raise ProvisionError('Provisioning unavailable or rejected; no automatic write retry. Check protected AP and saved-state status.') from None

def provision(opener, payload):
    try:
        result=exchange(opener,AP_HOST,BASE+'/intent')
        token=result.get('intent','')
        if type(token) is not str or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):
            raise ProvisionError('Invalid device intent')
        result=exchange(opener,AP_HOST,BASE,payload,token)
        if result!={'saved':True,'readback_verified':True}:
            raise ProvisionError('No verified storage acknowledgement; inspect state before repeating')
    finally:
        payload[:]=b'\0'*len(payload)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--change',action='store_true')
    actions.add_argument('--forget',action='store_true')
    actions.add_argument('--open-recovery',action='store_true',help='Enable protected AP for five minutes from an authenticated LAN target')
    parser.add_argument('--host',default=AP_HOST,help='Private LAN IP, ONLY for --open-recovery')
    parser.add_argument('--credentials-file',type=Path,required=True,help='Existing private Digest file path; never a Wi-Fi password argument')
    args=parser.parse_args(argv)
    payload=None
    try:
        if not sys.stdin.isatty(): raise ProvisionError('Interactive local terminal required; piped input refused')
        if args.open_recovery:
            host=validate_host(args.host)
            result=exchange(opener_for(host,args.credentials_file),host,BASE+'/recovery',bytearray())
            if result.get('protected_ap') is not True: raise ProvisionError('Recovery AP was not acknowledged')
            print('Protected SHINO AP requested for five minutes. Join it locally before Change/Forget.')
            return 0
        if args.host!=AP_HOST: raise ProvisionError('Wi-Fi credentials may only be sent over private SHINO recovery AP')
        if args.forget:
            if input('Type FORGET to remove saved household Wi-Fi: ')!='FORGET': raise ProvisionError('Cancelled')
            payload=bytearray(b'F')
        else:
            name=input('Household 2.4 GHz SSID (not saved on this PC): ')
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('error',getpass.GetPassWarning)
                password=getpass.getpass('Wi-Fi password (hidden; no file/log): ')
                confirmation=getpass.getpass('Confirm Wi-Fi password (hidden): ')
            if password!=confirmation: raise ProvisionError('Password confirmation differs')
            payload=encode_change(name,password)
            del password,confirmation,name
        provision(opener_for(AP_HOST,args.credentials_file),payload)
        print('SDK saved-state readback verified. No Wi-Fi secret saved on PC. Device retries automatically; physical connectivity is a separate check.')
        return 0
    except (Exception,KeyboardInterrupt):
        print('Provisioning stopped. No automatic write retry; inspect protected-AP status before retrying.',file=sys.stderr)
        return 1
    finally:
        if payload is not None: payload[:]=b'\0'*len(payload)

if __name__=='__main__': raise SystemExit(main())
