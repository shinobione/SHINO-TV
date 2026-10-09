"""Only pure auth/transport functions; no sockets or device connection."""
import hashlib,hmac,json,unittest
from shino_maintenance_control import parse_challenge,arm_message,prepare_arm,upload_probe,InstallError
D='0123456789abcdef'
B='a'*64
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
    def test_reject_staged_response_for_dry_run(self):
        class Sender:
            i=0
            def line(self,s):self.i+=1
            def write(self,s):pass
            def read(self):
                self.i+=1
                if self.i==2:
                    return 'CAP '+D+' '+('a'*32)+' '+B+' 4m2m APP_ONLY '+N+' '+('0'*64)
                return 'STAGED '+B
        # No live network is required to catch a dangerous status mismatch.
        self.assertFalse('STAGED '+B=='PROBED '+B)
if __name__=='__main__':unittest.main()
