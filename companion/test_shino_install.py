import hashlib,json,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import shino_install as app
from m9_signed_fixture_image import inert_image
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.p=Path(self.temp.name)
        self.raw=inert_image();self.image=self.p/'candidate.bin';self.image.write_bytes(self.raw)
        self.m=dict(schema=1,family='SHINO-StageA',layout='4m2m',protocol='shino-install-1',bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest(),build_id='b'*64)
        self.manifest=self.p/'candidate.json';self.save()
    def save(self):self.manifest.write_text(json.dumps(self.m),encoding='utf-8')
    def test_valid_exact_manifest_offline(self):
        with patch.object(socket,'create_connection',side_effect=AssertionError('network')) as network:
            self.assertEqual(app.inspect(self.image,self.manifest),(self.m,self.raw));network.assert_not_called()
    def test_manifest_identity_and_layout(self):
        for key,value in [('layout','4m3m'),('family','OEM'),('protocol','stock'),('bytes',len(self.raw)-1),('sha256','f'*64),('build_id','bad'),('bytes',True)]:
            with self.subTest(key=key,value=value):
                previous=self.m[key];self.m[key]=value;self.save()
                with self.assertRaises(ValueError):app.inspect(self.image,self.manifest)
                self.m[key]=previous
    def test_duplicate_and_extra_manifest_fields(self):
        self.manifest.write_text('{"schema":1,"schema":1}')
        with self.assertRaises(ValueError):app.inspect(self.image,self.manifest)
        self.m['unexpected']='data';self.save()
        with self.assertRaises(ValueError):app.inspect(self.image,self.manifest)
    def test_corrupt_and_truncated_binary(self):
        for data in (self.raw[:-1],b'\x1f'+self.raw[1:],self.raw+b'\0'):
            with self.subTest(length=len(data)):
                self.image.write_bytes(data);self.m['bytes']=len(data);self.m['sha256']=hashlib.sha256(data).hexdigest();self.save()
                with self.assertRaises(ValueError):app.inspect(self.image,self.manifest)
    def test_current_delivery_never_opens_device(self):
        with patch.object(socket,'create_connection',side_effect=AssertionError('network')) as network,patch.object(app.getpass,'getpass',side_effect=AssertionError('private credential read')) as credentials:
            with self.assertRaisesRegex(app.InstallError,'NO_GO'):app.live(self.image,self.manifest,'0'*16,'secret','192.168.4.1')
            self.assertEqual(app.main(['--bin',str(self.image),'--manifest',str(self.manifest),'--live','--device','0'*16,'--confirm-sha256',self.m['sha256']]),2)
            network.assert_not_called();credentials.assert_not_called()
    def test_absent_or_spoofed_receiver_cannot_authorize(self):
        class IO:
            lines=[]
            def line(self,s):self.lines.append(s)
            def read(self):return 'StageA does not have an OTA receiver'
        io=IO()
        with self.assertRaisesRegex(app.InstallError,'receiver unavailable'):app.send(io,'0'*16,'p'*32,self.m,self.raw)
        self.assertEqual(len(io.lines),1);self.assertTrue(io.lines[0].startswith('CAP '))
    def test_weak_maintenance_password_never_probes(self):
        with self.assertRaises(app.InstallError):app.send(None,'0'*16,'short',self.m,self.raw)
if __name__=='__main__':unittest.main()
