"""Synthetic-only Phase B image/range/source/recovery safety regressions."""
import ast
import hashlib
import json
import re
import struct
import tempfile
import unittest
from pathlib import Path

from m9_first_migration import (
    MigrationError, application_extent, arduino_crc, inspect_candidate, render_commands,
)
from m9_fsless_gate import FslessGateError, ROOT, inspect_source, inspect_build
from m9_master_restore_preflight import (
    EXPECTED_BYTES, MasterPreflightError, inspect_master, restore_gate, verify_readback,
)


def v1_image(payload, address=0x40100000):
    data = bytearray(struct.pack("<BBBBI", 0xE9, 1, 2, 0x40, 0x40100000))
    data += struct.pack("<II", address, len(payload)) + payload
    checksum = 0xEF
    for byte in payload:
        checksum ^= byte
    while len(data) % 16 != 15:
        data += b"\0"
    return data + bytes([checksum])


def candidate_fixture():
    # Synthetic eboot plus IROM application; never an owner or OEM dump.
    data = v1_image(b"\x42" * 32)
    data += b"\xaa" * (0x1000 - len(data))
    data += v1_image(b"\0" * 8 + b"\x25" * 32, 0x40201010)
    struct.pack_into("<II", data, 0x1010, len(data), arduino_crc(data))
    return data


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.bin"
        self.path.write_bytes(candidate_fixture())

    def test_candidate_report_has_bounded_extent_and_no_authority(self):
        report = inspect_candidate(self.path)
        self.assertEqual(report["sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(report["sector_rounded_write_extent"], 0x2000)
        self.assertEqual(report["flash_target_address"], 0)
        self.assertEqual(report["expected_physical_flash_bytes"], 0x400000)
        self.assertEqual(report["expected_linker_profile"], "4m2m")
        self.assertEqual(report["filesystem_start"], 0x200000)
        self.assertEqual(report["filesystem_end_exclusive"], 0x3FA000)
        for name in ("physical_authorization", "filesystem_write_performed",
                     "erase_all_performed", "serial_io_performed",
                     "application_write_overlaps_0x100000", "linker_profile_proven_by_bin_alone"):
            self.assertIs(report[name], False)
        json.dumps(report)

    def test_frozen_sized_application_never_touches_old_fs(self):
        self.assertEqual(application_extent(399152), 0x62000)
        self.assertEqual(application_extent(1044464), 0xFF000)
        for size in (0xFF001, 0xFFFFF, 0x100000, 0x100001, 0x400000, 0, -1):
            with self.subTest(size=size), self.assertRaises(MigrationError):
                application_extent(size)

    def test_sector_boundaries(self):
        for size, expected in ((1, 0x1000), (0x1000, 0x1000), (0x1001, 0x2000)):
            self.assertEqual(application_extent(size), expected)

    def test_malformed_images_close_gate(self):
        original = candidate_fixture()
        for data in (b"", b"\xff" * 128, original[:7], original[:0x1018],
                     original + b"\0", bytes([0]) + original[1:]):
            with self.subTest(length=len(data)), self.assertRaises(MigrationError):
                self.path.write_bytes(data)
                inspect_candidate(self.path)

    def test_corrupted_payload_and_crc_close_gate(self):
        for offset in (20, 0x1010, 0x1014, 0x1018, -1):
            data = candidate_fixture()
            data[offset] ^= 1
            self.path.write_bytes(data)
            with self.subTest(offset=offset), self.assertRaises(MigrationError):
                inspect_candidate(self.path)

    def test_bad_header_and_segment_bounds(self):
        for offset, value in ((1, 17), (2, 9), (3, 0x30), (0x1001, 0)):
            data = candidate_fixture()
            data[offset] = value
            self.path.write_bytes(data)
            with self.subTest(offset=offset), self.assertRaises(MigrationError):
                inspect_candidate(self.path)
        data = candidate_fixture()
        struct.pack_into("<I", data, 12, 0xFFFFFFFF)
        self.path.write_bytes(data)
        with self.assertRaises(MigrationError):
            inspect_candidate(self.path)

    def test_oversized_file_rejected_before_read(self):
        with self.path.open("wb") as stream:
            stream.truncate(0x100000)
        with self.assertRaises(MigrationError):
            inspect_candidate(self.path)

    def test_missing_and_directory_close_gate(self):
        for path in (self.path.parent, self.path.parent / "missing"):
            with self.assertRaises(MigrationError):
                inspect_candidate(path)

    def test_commands_are_placeholders_and_explicitly_unauthorized(self):
        report = render_commands()
        self.assertEqual(report["esptool_version_required"], "5.4.0")
        for key in ("identification", "stage1", "master_restore", "post_restore_readback"):
            self.assertEqual(report[key]["authorization"], "NOT AUTHORIZED BY PHASE B")
        text = json.dumps(report)
        self.assertIn("<PORT>", text)
        self.assertNotRegex(text, r"COM\d+|/dev/tty")
        self.assertNotIn("--erase-all", report["stage1"]["command"])
        for flag in ("--flash-mode keep", "--flash-freq keep", "--flash-size keep"):
            self.assertIn(flag, report["master_restore"]["command"])
        self.assertIn("0x000000", report["stage1"]["command"])
        self.assertIn("read-flash 0x000000 0x400000", report["post_restore_readback"]["command"])


class FslessSourceTests(unittest.TestCase):
    def test_active_source_is_fsless(self):
        self.assertEqual(inspect_source()["status"], "PASS_FSLESS_SOURCE_REGRESSIONS")

    def test_unreviewed_startup_storage_call_closes_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in inspect_source()["source_sha256"]:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((ROOT / path).read_text(encoding="utf-8"), encoding="utf-8")
            main = root / "firmware/src/main.cpp"
            main.write_text(main.read_text(encoding="utf-8").replace(
                "FirstBootBridge::run();", "LittleFS.begin(); FirstBootBridge::run();"), encoding="utf-8")
            with self.assertRaises(FslessGateError):
                inspect_source(root)

    def test_synthetic_link_evidence_and_disabled_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy, symbols = Path(tmp) / "policy.h", Path(tmp) / "symbols.txt"
            flags = ("SHINO_BOOT_PROFILE", "SHINO_ENABLE_FS_MIGRATION", "SHINO_ENABLE_NATIVE_SIGNED_OTA",
                     "SHINO_ENABLE_FACTORY_RESTORE", "SHINO_FS_IMAGE_PRESENT")
            policy.write_text("\n".join(f"#define {f} 0" for f in flags))
            nm = ("40400000 A _FS_start\n405fa000 A _FS_end\n405fb000 A _EEPROM_start\n"
                  "40201010 T FirstBootBridge::run()\n40201020 T FirstBootBridge::loop()\n"
                  "40201030 T FslessWebUI::PAGE\n40201040 T FslessWebUI::SCRIPT\n"
                  "40201050 T FslessMetrics::apply()\n")
            symbols.write_text(nm)
            self.assertFalse(inspect_build(policy, symbols)["physical_boot_proven"])
            for bad in (nm.replace("40400000", "40300000"), nm + "40202000 T EEPROMClass::begin()\n"):
                symbols.write_text(bad)
                with self.assertRaises(FslessGateError):
                    inspect_build(policy, symbols)
            symbols.write_text(nm)
            for flag in flags:
                policy.write_text("\n".join(f"#define {f} {int(f == flag)}" for f in flags))
                with self.subTest(flag=flag), self.assertRaises(FslessGateError):
                    inspect_build(policy, symbols)

    def test_phase_b_tools_have_no_io_runner_or_embedded_master_digest(self):
        allowed = {"__future__", "argparse", "hashlib", "json", "struct", "pathlib", "re", "m9_flash_layout"}
        for name in ("m9_first_migration.py", "m9_master_restore_preflight.py", "m9_fsless_gate.py"):
            text = (ROOT / "tools" / name).read_text(encoding="utf-8")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name, allowed)
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, allowed)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, ("eval", "exec", "__import__"))
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertIsNone(re.fullmatch("[0-9a-fA-F]{64}", node.value))

    def test_ci_uses_synthetic_tests_and_publishes_no_binary_or_master(self):
        text = (ROOT / ".github/workflows/m9-flash-layout.yml").read_text(encoding="utf-8")
        self.assertIn("test_m9_first_migration.py", text)
        self.assertIn("m9_first_migration.py", text)
        self.assertIn("m9_fsless_gate.py", text)
        artifact = text.split("- name: Upload safe numeric evidence only")[1].split("- name:")[0]
        self.assertNotIn(".bin", artifact)
        self.assertNotIn("MASTER", artifact)


class MasterRollbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = bytes(v1_image(b"\x27" * 32))
        cls.fixture += b"\x5a" * (EXPECTED_BYTES - len(cls.fixture))
        cls.digest = hashlib.sha256(cls.fixture).hexdigest()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.master = Path(self.temp.name) / "synthetic-master.bin"
        self.master.write_bytes(self.fixture)

    def test_valid_local_master_does_not_grant_restore_authority(self):
        self.assertFalse(inspect_master(self.master, self.digest)["authorization_to_restore"])

    def test_each_missing_restore_prerequisite_closes_gate(self):
        valid = dict(confirmed_chip="esp8266", confirmed_flash_bytes=EXPECTED_BYTES, owner_authorized=True)
        for key, bad in (("confirmed_chip", None), ("confirmed_chip", "esp32"),
                         ("confirmed_flash_bytes", None), ("confirmed_flash_bytes", 0x200000),
                         ("owner_authorized", False)):
            args = {**valid, key: bad}
            with self.subTest(key=key, bad=bad), self.assertRaises(MasterPreflightError):
                restore_gate(self.master, self.digest, **args)
        report = restore_gate(self.master, self.digest, **valid)
        self.assertEqual(report["post_restore_full_readback_bytes_required"], EXPECTED_BYTES)
        self.assertFalse(report["factory_recovery_successful"])

    def test_wrong_length_hash_header_and_uniform_fail(self):
        for data in (self.fixture[:-1], b"\xff" * EXPECTED_BYTES,
                     bytes([0]) + self.fixture[1:]):
            self.master.write_bytes(data)
            with self.assertRaises(MasterPreflightError):
                inspect_master(self.master, hashlib.sha256(data).hexdigest())
        self.master.write_bytes(self.fixture)
        for digest in ("", "z" * 64, "0" * 64):
            with self.assertRaises(MasterPreflightError):
                inspect_master(self.master, digest)

    def test_full_independent_byte_and_hash_readback_required(self):
        readback = self.master.parent / "synthetic-readback.bin"
        readback.write_bytes(self.fixture)
        report = verify_readback(self.master, readback, self.digest)
        self.assertTrue(report["byte_exact"])
        self.assertFalse(report["factory_runtime_recovery_proven"])
        with self.assertRaises(MasterPreflightError):
            verify_readback(self.master, self.master, self.digest)
        readback.write_bytes(self.fixture[:-1] + b"\xff")
        with self.assertRaises(MasterPreflightError):
            verify_readback(self.master, readback, self.digest)


if __name__ == "__main__":
    unittest.main()
