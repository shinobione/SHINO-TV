import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from owner_install_packet_gate import PacketError, assess
from verify_factory_ota import inspect_archive


def fake_image(size, mode=2):
    seed = b"".join(hashlib.sha256(i.to_bytes(4,"little")).digest()
                    for i in range((size+31)//32))
    return bytes([0xE9,2,mode,0x40,0x40,0xF4,0x10,0x40]) + seed[:size-8]


class OwnerOfflinePairGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.oem_bin = fake_image(494144)
        self.zip = self.root / "original.zip"
        with ZipFile(self.zip,"w",ZIP_DEFLATED) as z:
            z.writestr("FW-Smalltv-Ultra-V9.0.44.bin",self.oem_bin)
        self.manifest = self.root / "official_pin.json"
        self.manifest.write_text(json.dumps(inspect_archive(self.zip)))
        self.candidate = self.root/"private_candidate.bin"
        self.policy = self.root/"shino_private_policy.h"
        self.credentials = self.root/"credentials.txt"
        self.ini = self.root/"candidate.ini"
        self.ini.write_text("[env:esp12e]\nboard=esp12e\nboard_build.flash_size=4MB\n"
                            "board_build.flash_mode=dio\nboard_build.ldscript=eagle.flash.4m3m.ld\n")
        self.loader_ini = self.root/"loader.ini"
        self.loader_ini.write_text("[env:esp12e_recovery]\nboard=esp12e\n"
                                   "board_build.flash_size=4MB\nboard_build.flash_mode=dio\n"
                                   "board_build.ldscript=eagle.flash.4m1m.ld\n")
        self.loader = self.root/"loader.bin"
        self.loader.write_bytes(fake_image(312256))
        self.ap="ap_private_unique_per_build_00"
        self.http="digest_private_unique_per_build_11"
        self.token="api_private_unique_per_build_222"
        self.oem_md5=hashlib.md5(self.oem_bin,usedforsecurity=False).hexdigest()
        self.make_policy()
        self.make_candidate()

    def tearDown(self):
        self.temp.cleanup()

    def make_policy(self, fs="0", restore="1", factory_md5=None):
        expected=json.loads(self.manifest.read_text())
        self.policy.write_text(
            '#define SHINO_BOOT_PROFILE 0\n'
            f'#define SHINO_FS_IMAGE_PRESENT {fs}\n'
            '#define SHINO_ENABLE_FS_MIGRATION 0\n'
            f'#define SHINO_ENABLE_FACTORY_RESTORE {restore}\n'
            '#define SHINO_FACTORY_BYTES 494144\n'
            f'#define SHINO_FACTORY_MD5 "{factory_md5 or self.oem_md5}"\n'
            f'#define SHINO_FACTORY_SHA256 "{expected["firmware_sha256"]}"\n'
            f'#define SHINO_SETUP_AP_PSK "{self.ap}"\n'
            f'#define SHINO_BOOTSTRAP_API_TOKEN "{self.token}"\n'
            '#define SHINO_RESCUE_HTTP_USER "shino"\n'
            f'#define SHINO_RESCUE_HTTP_PASSWORD "{self.http}"\n'
        )
        self.credentials.write_text(
            "PRIVATE owner one-use credentials\n"
            "First-boot Wi-Fi SSID: SHINO-FirstBoot-<chip-id>\n"
            f"Setup/rescue Wi-Fi password: {self.ap}\n"
            f"Initial API bearer token: {self.token}\n"
            "Rescue HTTP Digest user: shino\n"
            f"Rescue HTTP Digest password: {self.http}\n"
        )

    def make_candidate(self, *, restore=True, pin=True):
        markers=(b"FIRST_BOOT_BRIDGE" + b"FSLESS_PC_TELEMETRY_RAM_ONLY" +
                 b"READ_ONLY_FS_MIGRATION_PLAN" + b"RAM_SAMPLE_ACCEPTED" +
                 (b"Verified OEM application image" if restore else b"") +
                 (self.oem_md5.encode() if pin else b"") +
                 self.ap.encode() + self.http.encode())
        self.candidate.write_bytes(fake_image(398544-len(markers)) + markers)

    def check(self, with_loader=False):
        return assess(self.zip,self.manifest,self.candidate,self.policy,
                      self.credentials,self.ini,self.loader if with_loader else None,
                      self.loader_ini if with_loader else None)

    def test_direct_report_has_zero_inferred_FS_overlap_and_never_grants_flash(self):
        result=self.check()
        self.assertEqual(result["reviewed_candidate"]["bytes"],398544)
        self.assertTrue(result["direct_install_model"]["nominal_no_overlap"])
        self.assertEqual(result["direct_install_model"]["overlaps_inferred_stock_file_sectors_bytes"],0)
        self.assertEqual(result["running_shino_to_oem_application_model"]["overlaps_inferred_stock_file_sectors_bytes"],0)
        self.assertEqual(result["status"],"PRIVATE_OFFLINE_PACKET_CHECKED__OWNER_FLASH_NOT_AUTHORIZED")
        self.assertFalse(result["permission_to_flash"])
        self.assertFalse(result["physical_device_contacted"])
        content=json.dumps(result)
        for secret in (self.ap,self.http,self.token):
            self.assertNotIn(secret,content)

    def test_two_hop_is_not_misrepresented_as_preserving_stock_files(self):
        result=self.check(with_loader=True)
        self.assertGreater(result["optional_two_hop_model"]["inferred_original_file_sectors_affected_bytes"],0)
        self.assertTrue(result["optional_two_hop_model"]["not_a_stock_data_preserving_fallback"])

    def test_wrong_private_pair_refused(self):
        self.credentials.write_text(self.credentials.read_text().replace(self.ap,"not-the-build-password"))
        with self.assertRaisesRegex(PacketError,"Credentials do not correspond"):
            self.check()

    def test_compiled_candidate_from_different_secret_build_refused(self):
        self.make_candidate()
        self.policy.write_text(self.policy.read_text().replace(self.http,"another_sufficiently_long_digest_password"))
        self.credentials.write_text(self.credentials.read_text().replace(self.http,"another_sufficiently_long_digest_password"))
        with self.assertRaisesRegex(PacketError,"compiled active"):
            self.check()

    def test_wrong_oem_pin_refused(self):
        self.make_policy(factory_md5="a"*32)
        with self.assertRaisesRegex(PacketError,"updater digest"):
            self.check()

    def test_default_readonly_candidate_not_mistaken_for_restorable_image(self):
        self.make_policy(restore="0")
        with self.assertRaisesRegex(PacketError,"SHINO_ENABLE_FACTORY_RESTORE"):
            self.check()
        self.make_policy()
        self.make_candidate(restore=False)
        with self.assertRaisesRegex(PacketError,"experimental pinned OEM return"):
            self.check()

    def test_old_4m2m_runtime_map_refused(self):
        self.ini.write_text(self.ini.read_text().replace("4m3m","4m2m"))
        with self.assertRaisesRegex(PacketError,"stock-like 4m3m"):
            self.check()

    def test_missing_compiled_original_pin_and_fsless_marker_refused(self):
        self.make_candidate(pin=False)
        with self.assertRaisesRegex(PacketError,"manufacturer application MD5"):
            self.check()
        self.make_candidate()
        self.make_policy(fs="1")
        with self.assertRaisesRegex(PacketError,"SHINO_FS_IMAGE_PRESENT"):
            self.check()

    def test_original_zip_mismatch_stops_without_exposing_credentials(self):
        self.zip.write_bytes(b"not the OEM ZIP")
        with self.assertRaises(ValueError):
            self.check()

    def test_image_larger_than_reviewed_original_does_not_pass(self):
        image=self.candidate.read_bytes()
        self.candidate.write_bytes(fake_image(494144-len(image)) + image)
        with self.assertRaisesRegex(PacketError,"exceeds conservative"):
            self.check()


if __name__ == "__main__":
    unittest.main()
