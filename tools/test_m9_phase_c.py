"""Phase C deterministic synthetic files/models; zero device access."""
import ast
import hashlib
import json
import os
import shutil
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from m9_executor_preflight import (
    ExecutorError, MANIFEST, FROZEN_BYTES, check_configuration, inspect_sources,
    installed_identity, preflight, render_packet, retry_extent_model, rtc_command_model,
)
from m9_first_migration import arduino_crc, application_extent
from m9_stage1_readback_verify import ReadbackError, verify_stage1
from m9_master_restore_preflight import inspect_master, verify_readback, MasterPreflightError
from test_m9_first_migration import candidate_fixture

ROOT = Path(__file__).resolve().parents[1]


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate, self.pre, self.post = [self.root / name for name in ("candidate", "pre", "post")]
        self.data = candidate_fixture()
        self.candidate.write_bytes(self.data)
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.before = bytes(range(256)) * 16384
        self.pre.write_bytes(self.before)
        self.after = bytearray(self.before)
        self.after[:len(self.data)] = self.data
        self.post.write_bytes(self.after)

    def verify(self):
        return verify_stage1(self.candidate, self.pre, self.post, self.digest)

    def test_exact_payload_and_protected_region_pass_without_device_claims(self):
        report = self.verify()
        self.assertEqual(report["protected_range_inclusive"], "0x002000..0x3FFFFF")
        self.assertEqual(report["protected_bytes_compared"], 0x400000 - 0x2000)
        for name in ("device_claims", "physical_authorization", "serial_io_performed",
                     "physical_capture_freshness_proven", "slack_equality_required"):
            self.assertIs(report[name], False)
        self.assertEqual(report["physical_runtime_gate"], "NOT_RUN")

    def test_payload_corruption_fails(self):
        self.after[33] ^= 1
        self.post.write_bytes(self.after)
        with self.assertRaisesRegex(ReadbackError, "payload"):
            self.verify()

    def test_protected_mutations_at_start_historical_fs_future_fs_and_tail_fail(self):
        for offset in (0x2000, 0x100000, 0x200000, 0x3FA000, 0x3FFFFF):
            with self.subTest(offset=offset):
                data = bytearray(self.after)
                data[offset] ^= 1
                self.post.write_bytes(data)
                with self.assertRaisesRegex(ReadbackError, "Protected"):
                    self.verify()

    def test_touched_slack_mutation_allowed(self):
        rounded = application_extent(len(self.data))
        self.after[len(self.data):rounded] = b"\xff" * (rounded - len(self.data))
        self.post.write_bytes(self.after)
        self.assertTrue(self.verify()["protected_byte_exact"])

    def test_readback_wrong_sizes_fail(self):
        for path in (self.pre, self.post):
            for size in (0, 0x3FFFFF, 0x400001):
                with self.subTest(path=path.name, size=size):
                    path.write_bytes(b"\0" * size)
                    with self.assertRaises(ReadbackError):
                        self.verify()
            path.write_bytes(self.before if path == self.pre else self.after)

    def test_wrong_and_malformed_external_hash_fail(self):
        for digest in ("0" * 64, "bad", "g" * 64, "", self.digest + "0"):
            with self.assertRaises(ReadbackError):
                verify_stage1(self.candidate, self.pre, self.post, digest)

    def test_same_file_and_resolved_alias_fail(self):
        with self.assertRaisesRegex(ReadbackError, "independent"):
            verify_stage1(self.candidate, self.pre, self.pre, self.digest)
        with self.assertRaises(ReadbackError):
            verify_stage1(self.candidate, self.pre, self.root / "." / "pre", self.digest)

    def test_hardlink_alias_fails(self):
        alias = self.root / "hardlink"
        os.link(self.pre, alias)
        with self.assertRaisesRegex(ReadbackError, "independent"):
            verify_stage1(self.candidate, self.pre, alias, self.digest)

    def test_candidate_alias_with_readback_fails(self):
        with self.assertRaisesRegex(ReadbackError, "independent"):
            verify_stage1(self.candidate, self.candidate, self.post, self.digest)

    def test_directory_or_missing_file_fails(self):
        for path in (self.root, self.root / "missing"):
            with self.assertRaises((ReadbackError, OSError)):
                verify_stage1(path, self.pre, self.post, self.digest)

    def test_malformed_candidate_even_with_matching_hash_fails(self):
        self.data[0] = 0
        self.candidate.write_bytes(self.data)
        with self.assertRaises(ValueError):
            verify_stage1(self.candidate, self.pre, self.post, hashlib.sha256(self.data).hexdigest())


class ExecutorTests(unittest.TestCase):
    def test_installed_package_source_gate_and_inventory(self):
        report = installed_identity()
        self.assertEqual(report["esptool_version"], "5.4.0")
        self.assertEqual(report["source_files_checked"], 53)
        self.assertEqual(report["stub_version"], "2")
        self.assertEqual(report["eboot_cold_start_gate"], "HOLD")
        self.assertFalse(report["physical_authorization"])

    def test_source_mutation_fails_closed(self):
        import importlib.metadata
        source = Path(importlib.metadata.distribution("esptool").locate_file("esptool"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "esptool"
            shutil.copytree(source, root, ignore=shutil.ignore_patterns("__pycache__"))
            path = root / "cmds.py"
            path.write_bytes(path.read_bytes() + b"\n# changed\n")
            with self.assertRaisesRegex(ExecutorError, "Pinned source changed"):
                inspect_sources(root)

    def test_unexpected_source_inventory_fails_closed(self):
        import importlib.metadata
        source = Path(importlib.metadata.distribution("esptool").locate_file("esptool"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "esptool"
            shutil.copytree(source, root, ignore=shutil.ignore_patterns("__pycache__"))
            (root / "unreviewed.py").write_text("# changed")
            with self.assertRaisesRegex(ExecutorError, "inventory"):
                inspect_sources(root)

    def test_core_source_mutation_fails_closed(self):
        manifest = json.loads(MANIFEST.read_text())
        import importlib.metadata
        esp = Path(importlib.metadata.distribution("esptool").locate_file("esptool"))
        with tempfile.TemporaryDirectory() as temporary:
            core = Path(temporary)
            # Mismatch one reviewed source; never invent a successful Core hash.
            name = next(iter(manifest["arduino_files"]))
            path = core / name
            path.parent.mkdir(parents=True)
            path.write_text("# unreviewed eboot")
            with self.assertRaisesRegex(ExecutorError, "Pinned source changed"):
                inspect_sources(esp, core)

    def test_environment_overrides_fail_closed(self):
        for name in ("ESPTOOL_CFGFILE", "ESPTOOL_STUB_VERSION"):
            with patch.dict(os.environ, {name: "unreviewed"}):
                with self.assertRaises(ExecutorError):
                    check_configuration()

    def test_custom_config_section_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "esptool.cfg").write_text("[esptool]\nwrite_block_attempts=99\n")
            with patch("m9_executor_preflight.Path.cwd", return_value=root):
                with self.assertRaisesRegex(ExecutorError, "Custom esptool"):
                    check_configuration()

    def test_wrong_external_python_identity_fails_before_candidate_access(self):
        identity = {"python_executable_sha256": "1" * 64, "python_version": "3.12.10",
                    "esptool_module_path": str(ROOT)}
        with patch("m9_executor_preflight.installed_identity", return_value=identity):
            with self.assertRaisesRegex(ExecutorError, "interpreter/module"):
                preflight(ROOT / "absent", "0" * 64, "2" * 64, "3.12.10", ROOT, ROOT)

    def test_retry_model_same_bounded_range_both_attempts(self):
        for size in (FROZEN_BYTES, 399152, 0xFEFF0):
            report = retry_extent_model(size, [0x4000] * 100)
            attempts = report["attempts"]
            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[0], attempts[1])
            self.assertEqual(report["destructive_end_exclusive"], application_extent(size))
            for attempt in attempts:
                for left, right in attempt["writes"]:
                    self.assertTrue(0 <= left < right <= size)
                for left, right in attempt["possible_erase_ranges"]:
                    self.assertTrue(0 <= left < right <= application_extent(size))
                self.assertEqual(attempt["possible_erase_ranges"][-1][1], application_extent(size))
            self.assertFalse(report["payload_correctness_proven"])

    def test_retry_model_partial_and_duplicate_delivery_bound(self):
        report = retry_extent_model(FROZEN_BYTES, [0x4000] * 3)
        self.assertEqual(report["attempts"][0]["writes"][-1][1], 0xC000)
        with self.assertRaises(ValueError):
            retry_extent_model(0x100000, [0x4000])
        with self.assertRaises(ValueError):
            retry_extent_model(FROZEN_BYTES, [0x4001])

    def test_packet_A_to_K_placeholders_and_no_stage2(self):
        packet = render_packet()
        self.assertEqual([s["step"] for s in packet["steps"]], list("ABCDEFGHIJK"))
        text = json.dumps(packet)
        for placeholder in ("<PORT>", "<CANDIDATE_BIN>", "<PREWRITE_4MB_BIN>",
                            "<POSTWRITE_4MB_BIN>", "<PRIVATE_MASTER_BIN>", "<ROLLBACK_READBACK_BIN>"):
            self.assertIn(placeholder, text)
        for step in packet["steps"]:
            template = step["template"]
            if "-m esptool" in template:
                self.assertIn("-I -m esptool", template)
                self.assertIn("--stub-version 2", template)
                self.assertIn("--before no-reset --after no-reset-stub --connect-attempts 1", template)
                self.assertEqual(step["authorization"], "NOT AUTHORIZED BY PHASE C")
            self.assertNotIn("erase-flash", template)
            self.assertNotIn("--erase-all", template)
            self.assertNotIn("--no-stub", template)
            self.assertNotIn("0x200000", template)
        self.assertEqual(packet["steps"][4]["template"], packet["steps"][0]["template"])
        for key in ("F", "J"):
            command = next(s["template"] for s in packet["steps"] if s["step"] == key)
            self.assertIn("--flash-mode keep --flash-freq keep --flash-size keep --no-compress 0x000000", command)
        self.assertFalse(packet["physical_authorization"])

    def test_phase_c_tool_imports_cannot_execute_serial_or_subprocess(self):
        allowed = {"__future__", "argparse", "configparser", "hashlib", "importlib.metadata", "json",
                   "os", "platform", "struct", "sys", "pathlib", "re", "stat",
                   "m9_first_migration", "m9_stage1_readback_verify", "m9_flash_layout"}
        for name in ("m9_executor_preflight.py", "m9_stage1_readback_verify.py"):
            tree = ast.parse((ROOT / "tools" / name).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(alias.name in allowed for alias in node.names))
                if isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, allowed)
                if isinstance(node, ast.Call):
                    self.assertNotIn(ast.unparse(node.func), ("os.system", "os.popen", "exec", "eval", "__import__"))

    def test_rtc_valid_copy_survives_parser_without_reset_reason_gate(self):
        data = bytearray(128)
        struct.pack_into("<IIIII", data, 0, 0xEB001000, 1, 0x19E000, 0, FROZEN_BYTES)
        struct.pack_into("<I", data, 124, arduino_crc(data[:124]))
        report = rtc_command_model(data)
        self.assertTrue(report["pending_copy"])
        self.assertFalse(report["reset_reason_checked"])
        self.assertFalse(report["power_on_guarantees_invalid_command"])
        self.assertEqual(report["eboot_cold_start_gate"], "HOLD")

    def test_invalid_rtc_defaults_to_load_but_cold_power_does_not_prove_invalid(self):
        report = rtc_command_model(bytes(128))
        self.assertTrue(report["default_load_app_zero"])
        self.assertFalse(report["pending_copy"])
        self.assertEqual(report["eboot_cold_start_gate"], "HOLD")
        with self.assertRaises(ValueError):
            rtc_command_model(bytes(127))

    def test_source_gate_cannot_claim_cold_invalid_without_review(self):
        manifest = json.loads(MANIFEST.read_text())
        self.assertEqual(manifest["eboot_cold_start_gate"], "HOLD")
        self.assertIn("random", manifest["esp8266_power_on_rtc_contents"])
        self.assertEqual(manifest["stub_revision"], "23959b780454adf885916d42f2274ec648e96a94")
        self.assertEqual(manifest["arduino_core_version"], "3.1.2")

    def test_safe_ci_artifact_allowlist_does_not_include_phase_c_private_receipts(self):
        workflow = (ROOT / ".github/workflows/m9-flash-layout.yml").read_text()
        upload = workflow.split("- name: Upload safe numeric evidence only")[1].split("- name:")[0]
        self.assertNotIn("research-local", upload)
        self.assertNotIn("m9-phase-c", upload)
        self.assertNotIn(".bin", upload)
        self.assertNotIn(".elf", upload)
        self.assertNotIn("readback", upload)


class RollbackTests(unittest.TestCase):
    def test_synthetic_full_master_external_digest_readback_and_no_runtime_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            master, readback = (Path(temporary) / name for name in ("synthetic-master", "synthetic-readback"))
            data = bytearray(bytes(range(256)) * 16384)
            data[:4] = bytes([0xE9, 1, 2, 0x40])
            master.write_bytes(data)
            readback.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(inspect_master(master, digest)["bytes"], 0x400000)
            report = verify_readback(master, readback, digest)
            self.assertTrue(report["byte_exact"])
            self.assertFalse(report["factory_runtime_recovery_proven"])
            with self.assertRaises(MasterPreflightError):
                inspect_master(master, "0" * 64)
            data[-1] ^= 1
            readback.write_bytes(data)
            with self.assertRaises(MasterPreflightError):
                verify_readback(master, readback, digest)
            readback.write_bytes(data[:-1])
            with self.assertRaises(MasterPreflightError):
                inspect_master(readback, digest)


if __name__ == "__main__":
    unittest.main()
