"""Only pure auth/transport functions; no sockets or device connection."""
import hashlib,hmac,json,unittest
from shino_maintenance_control import parse_challenge,arm_message,prepare_arm,upload_probe,InstallError
D='0123456789abcdef'
B='a'*64
NEXT='b'*64
N='0102030405060708090a0b0c0d0e0f10'
P='not-a-fixture-maintenance-password-which-is-long-enough'
CH=json.dumps({'nonce':N,'device':D,'build':B}).encode()
class ArmClient(unittest.TestCase):
    def test_real_hmac_arm_message(self):
        x,got=prepare_arm(CH,D,P,'PROBE')
        key=hashlib.sha256(P.encode()).digest()
        want=hmac.new(key,f'SHINO_ARM_1 {D} {B} {N} PROBE'.encode(),hashlib.sha256).hexdigest()
        self.assertEqual(got,want)
        self.assertEqual(x['build'],B)
        self.assertNotEqual(prepare_arm(CH,D,P,'INSTALL')[1],got)
    def test_reject_wrong_device_and_duplicate_json(self):
        for data in (CH, b'{"nonce":"1","nonce":"2","device":"'+D.encode()+b'","build":"'+B.encode()+b'"}'):
            with self.assertRaises(InstallError):parse_challenge(data,'0000000000000000')
        with self.assertRaises(InstallError):
            parse_challenge(b'{"nonce":"1","nonce":"2","device":"'+D.encode()+b'","build":"'+B.encode()+b'"}',D)
    def test_reject_modes_and_short_key(self):
        with self.assertRaises(InstallError):arm_message(D,B,N,'RESET')
        with self.assertRaises(InstallError):prepare_arm(CH,D,'too-short','PROBE')
    def test_probe_rejects_staged_reply_and_accepts_probed_only(self):
        class IO:
            def __init__(self,reply):
                self.reply=reply
                self.pending=''
                self.sent=0
            def line(self,data):
                self.pending=data
            def write(self,data):
                self.sent+=len(data)
                self.pending='DATA'
            def read(self):
                if self.pending.startswith('CAP '):
                    _,device,cn=self.pending.split(' ')
                    # Exact native receiver CAP proof using the same HMAC key.
                    key=hashlib.sha256(P.encode()).digest()
                    value=f'CAP {device} {cn} {B} 4m2m APP_ONLY {N}'
                    return value+' '+hmac.new(key,value.encode(),hashlib.sha256).hexdigest()
                if self.pending.startswith('AUTH '):return 'READY'
                if self.pending=='DATA':return f'ACK {self.sent}'
                if self.pending=='COMMIT':return self.reply+' '+NEXT
                raise AssertionError(self.pending)
        raw=b'hello'
        m=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),build_id=NEXT)
        self.assertEqual(upload_probe(IO('PROBED'),D,P,m,raw,expected_current_build=B),
                         'PROBED_PENDING_HTTP_RESULT')
        with self.assertRaisesRegex(InstallError,'RAM-only'):
            upload_probe(IO('STAGED'),D,P,m,raw,expected_current_build=B)
        wrong_build=IO('PROBED')
        with self.assertRaisesRegex(InstallError,'build changed'):
            upload_probe(wrong_build,D,P,m,raw,expected_current_build='c'*64)
        self.assertEqual(wrong_build.sent,0)
        already_installed=IO('PROBED')
        with self.assertRaisesRegex(InstallError,'already installed'):
            upload_probe(already_installed,D,P,dict(m,build_id=B),raw,
                         expected_current_build=B)
        self.assertEqual(already_installed.sent,0)
if __name__=='__main__':unittest.main()
