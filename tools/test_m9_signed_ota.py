"""Deterministic release/geometry/auth-source regressions; public inert bytes only."""
import hashlib
import json
from pathlib import Path
import struct
import unittest
from m9_signed_fixture_image import inert_image
from m9_signed_release import verify,validate_image,geometry,LINKER_MAX_APP_BYTES
ROOT=Path(__file__).resolve().parent.parent
FIXTURE=ROOT/'experiments/m9_signed_ota/fixtures'


class SignedReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=(FIXTURE/'raw.inert').read_bytes()
        cls.package=(FIXTURE/'signed.inert').read_bytes()
        cls.der=(FIXTURE/'public.der').read_bytes()
        cls.pins={name:hashlib.sha256(value).hexdigest() for name,value in
                  [('raw_sha256',cls.raw),('package_sha256',cls.package),('key_sha256',cls.der)]}

    def check(self,package=None,der=None,**pins):
        return verify(self.package if package is None else package,self.der if der is None else der,
                      current_bytes=399264,**(self.pins|pins))

    def test_full_fixture_hashes_and_inert_image(self):
        manifest=json.loads((FIXTURE/'manifest.json').read_text())
        for name,pin in manifest.items():
            data=(FIXTURE/name).read_bytes()
            self.assertEqual((len(data),hashlib.sha256(data).hexdigest()),(pin['bytes'],pin['sha256']))
        self.assertEqual(self.raw,inert_image())
        self.assertEqual(self.pins['raw_sha256'],'67adaf4b86354b58beab6496dd5ed681ec77de93631297e6f1f65c8748947fb3')
        self.assertEqual(self.pins['key_sha256'],'900453c460c3a19c17b6019595d4c2a4acc3d13b80ac18f67b01ade2b6be4c7f')
        self.assertEqual(self.pins['package_sha256'],'b218d53ef13afa95206c4f02d3b307f8cb8257e3bbbbe356f37a928f8821380a')

    def test_independent_openssl_rsa_and_layout_positive(self):
        result=self.check();self.assertEqual(result['SIGNED_RELEASE_OFFLINE_GATE'],'PASS')
        self.assertFalse(result['permission_to_flash'])
        self.assertEqual(result['geometry']['stage_end'],0x200000)

    def test_bad_signature_with_matching_selected_package(self):
        changed=bytearray(self.package);changed[-260]^=1
        with self.assertRaisesRegex(ValueError,'signature'):
            self.check(bytes(changed),package_sha256=hashlib.sha256(changed).hexdigest())

    def test_wrong_independent_public_key(self):
        changed=bytearray(self.der);changed[-8]^=1
        with self.assertRaises(ValueError):self.check(der=bytes(changed),key_sha256=hashlib.sha256(changed).hexdigest())

    def test_raw_package_and_trust_pins_required(self):
        for pin in self.pins:
            with self.subTest(pin=pin),self.assertRaises(ValueError):self.check(**{pin:'0'*64})

    def test_unsigned_truncated_extra_and_wrong_trailer(self):
        for value in (self.raw,self.package[:-1],self.package+b'X',self.package[:-4]+struct.pack('<I',128)):
            with self.subTest(length=len(value)),self.assertRaises(ValueError):self.check(value)

    def test_crc_checksum_header_and_segment_corruption(self):
        for offset in (0,1,2,3,4,8,12,47,0x1000,0x1002,0x1010,0x1014,0x1020,0x1024,5000,len(self.raw)-1):
            changed=bytearray(self.raw);changed[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):validate_image(bytes(changed))

    def test_maximum_geometry_leaves_one_sector_and_excludes_filesystem(self):
        result=geometry(LINKER_MAX_APP_BYTES,LINKER_MAX_APP_BYTES)
        self.assertEqual(result['transport_bytes'],1044724)
        self.assertEqual((result['stage_start'],result['stage_end'],result['guard_bytes']),(0x100000,0x200000,4096))
        self.assertEqual(geometry(399264,100000)['transport_rounded'],102400)
        self.assertTrue(validate_image(inert_image(LINKER_MAX_APP_BYTES))['crc_valid'])

    def test_size_and_linker_negatives(self):
        for current,raw in ((399264,LINKER_MAX_APP_BYTES+1),(LINKER_MAX_APP_BYTES+1,100000),(0,100000),(399264,63999)):
            with self.assertRaises(ValueError):geometry(current,raw)
        with self.assertRaises(ValueError):self.check(linker='eagle.flash.4m3m.ld')

    def test_no_deployable_test_key_or_route(self):
        main=(ROOT/'experiments/m9_signed_ota/src/main.cpp').read_text()
        self.assertNotIn('public.der',main);self.assertNotIn('server.on',main)
        setup=main[main.index('void setup()'):]
        self.assertNotIn('unwiredProof(',setup)
        self.assertNotRegex((ROOT/'experiments/m9_signed_ota/include/M9SignedCore.h').read_text(),r'(?m)^\s*Update\.')
        self.assertFalse((ROOT/'experiments/m9_signed_ota/private.key').exists())


if __name__=='__main__':unittest.main()
