"""Phase D synthetic parser/sequence/command tests; zero device access."""
import ast
import copy
import hashlib
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from m9_first_migration import arduino_crc
from m9_executor_preflight import ExecutorError, FROZEN_BYTES, FROZEN_SHA, MANIFEST
from m9_rtc_neutralization import (
    COMMAND_BYTES, CRC_ADDRESS, MAGIC_ADDRESS, REQUIRED_CONDITIONS,
    NeutralizationError, audit_sources, command_state, neutralize_model,
    render_packet, required_events, reset_retention_matrix, verify_sequence,
)

ROOT = Path(__file__).resolve().parents[1]


def copy_fixture(magic=0xEB001000):
    block = bytearray(bytes(range(128)))
    struct.pack_into("<II", block, 0, magic, 1)
    struct.pack_into("<III", block, 8, 0x80000, 0, 399168)
    struct.pack_into("<I", block, 124, arduino_crc(block[:124]))
    return bytes(block)


class RTCTests(unittest.TestCase):
    def test_retained_valid_copy_detected(self):
        state = command_state(copy_fixture())
        self.assertTrue(state["valid_command"])
        self.assertTrue(state["pending_copy"])
        self.assertFalse(state["default_load_app_zero"])

    def test_masked_magic_low_bits_accepted_with_matching_crc(self):
        self.assertTrue(command_state(copy_fixture(0xEB001FFF))["pending_copy"])

    def test_valid_magic_requires_crc(self):
        data = bytearray(copy_fixture())
        data[-1] ^= 1
        self.assertFalse(command_state(bytes(data))["pending_copy"])

    def test_zero_magic_rejects_independent_remaining_words_and_valid_crc(self):
        for fill in (0, 255, 0x6D):
            block = bytearray([fill] * COMMAND_BYTES)
            struct.pack_into("<II", block, 0, 0, 1)
            struct.pack_into("<I", block, 124, arduino_crc(block[:124]))
            state = command_state(bytes(block))
            self.assertFalse(state["pending_copy"])
            self.assertTrue(state["default_load_app_zero"])

    def test_exact_official_clear_leaves_other_120_bytes_unchanged(self):
        original = copy_fixture()
        cleared = neutralize_model(original)
        self.assertEqual(cleared[:4], b"\0" * 4)
        self.assertEqual(cleared[124:], b"\0" * 4)
        self.assertEqual(cleared[4:124], original[4:124])
        state = command_state(cleared)
        self.assertTrue(state["neutral_words"])
        self.assertFalse(state["pending_copy"])
        self.assertTrue(state["default_load_app_zero"])
        self.assertFalse(state["other_rtc_words_known_zero"])

    def test_corruption_is_never_deliberately_verified_neutral(self):
        for block in (b"\0" * 128, neutralize_model(copy_fixture()), b"\xff" * 128):
            self.assertFalse(command_state(block)["deliberately_verified_neutral"])
            self.assertFalse(command_state(block)["physical_observation"])

    def test_wrong_rtc_lengths_rejected(self):
        for size in (0, 124, 127, 129, 512):
            with self.assertRaises(ExecutorError):
                neutralize_model(b"\0" * size)

    def test_exact_32bit_aligned_addresses_and_geometry(self):
        self.assertEqual(MAGIC_ADDRESS, 0x60001200)
        self.assertEqual(CRC_ADDRESS, 0x6000127C)
        self.assertEqual(CRC_ADDRESS - MAGIC_ADDRESS, 124)
        self.assertEqual(COMMAND_BYTES, 128)
        self.assertEqual(MAGIC_ADDRESS % 4, 0)
        self.assertEqual(CRC_ADDRESS % 4, 0)


class SequenceTests(unittest.TestCase):
    def setUp(self):
        self.events = required_events()
        self.conditions = dict.fromkeys(REQUIRED_CONDITIONS, True)

    def test_powered_ext_rst_path_passes_only_synthetic_model(self):
        state = verify_sequence(self.events, self.conditions)
        self.assertTrue(state["model_neutralization_verified"])
        self.assertFalse(state["pending_copy"])
        self.assertTrue(state["default_load_app_zero"])
        self.assertFalse(state["physical_observation"])
        self.assertFalse(state["physical_authorization"])
        self.assertEqual(state["physical_write"], "HOLD")

    def test_power_on_en_run_software_watchdog_paths_rejected(self):
        for reset in ("power_on", "CHIP_EN", "esptool_run", "esptool_soft_reset", "system_restart", "watchdog", "unknown"):
            with self.assertRaises(NeutralizationError):
                verify_sequence(self.events, self.conditions, reset)

    def test_reset_matrix_cites_documented_retention(self):
        matrix = reset_retention_matrix()
        for reset in ("EXT_RST", "system_restart", "watchdog"):
            self.assertEqual(matrix[reset]["rtc"], "retained")
        self.assertIn("espressif.com", matrix["EXT_RST"]["retention_source"])
        for reset in ("power_on", "CHIP_EN"):
            self.assertEqual(matrix[reset]["rtc"], "random")

    def test_missing_or_unknown_conditions_hold(self):
        for key in REQUIRED_CONDITIONS:
            for value in (False, None, "unknown", 1):
                conditions = dict(self.conditions, **{key: value})
                with self.assertRaises(NeutralizationError):
                    verify_sequence(self.events, conditions)
            conditions = self.conditions.copy()
            del conditions[key]
            with self.assertRaises(NeutralizationError):
                verify_sequence(self.events, conditions)

    def test_wrong_or_failed_readback_holds(self):
        for index in range(4):
            for key, value in (("address", 0x60001204), ("value", 1), ("success", False), ("value", False)):
                events = copy.deepcopy(self.events)
                events[index][key] = value
                with self.assertRaises(NeutralizationError):
                    verify_sequence(events, self.conditions)

    def test_no_reordered_removed_or_added_transition(self):
        for index in range(len(self.events)):
            events = copy.deepcopy(self.events)
            del events[index]
            with self.assertRaises(NeutralizationError):
                verify_sequence(events, self.conditions)
        events = copy.deepcopy(self.events)
        events[2], events[4] = events[4], events[2]
        with self.assertRaises(NeutralizationError):
            verify_sequence(events, self.conditions)

    def test_intervening_reset_or_power_loss_invalidates_receipt(self):
        for reset in ("power_on", "CHIP_EN", "EXT_RST", "reconnect", "application"):
            events = copy.deepcopy(self.events)
            events.insert(4, {"step": reset, "success": True})
            with self.assertRaises(NeutralizationError):
                verify_sequence(events, self.conditions)


class SourcePacketTests(unittest.TestCase):
    def test_exact_print_only_four_command_packet(self):
        packet = render_packet()
        self.assertEqual(packet["mode"], "PRINT_ONLY")
        self.assertEqual(packet["esptool_version"], "5.4.0")
        self.assertEqual(len(packet["steps"]), 4)
        suffixes = ("write-mem 0x60001200 0x00000000 0xFFFFFFFF",
                    "write-mem 0x6000127C 0x00000000 0xFFFFFFFF",
                    "read-mem 0x60001200", "read-mem 0x6000127C")
        for step, suffix in zip(packet["steps"], suffixes):
            self.assertTrue(step["command"].endswith(suffix))
            self.assertIn('"<PORT>"', step["command"])
            self.assertIn("--after no-reset-stub", step["command"])
            self.assertIn("--before no-reset", step["command"])
            self.assertIn("--stub-version 2", step["command"])
            self.assertIn("--connect-attempts 1", step["command"])
            self.assertIn("NOT AUTHORIZED BY PHASE D", step["label"])

    def test_packet_has_no_flash_stage2_reset_or_executor(self):
        text = json.dumps(render_packet()).lower()
        for forbidden in ("write-flash", "erase-", "load-ram", "littlefs", "stage2", "hard-reset", "soft-reset", "--mask"):
            self.assertNotIn(forbidden, text)
        self.assertFalse(render_packet()["physical_authorization"])

    def test_tool_imports_and_calls_have_no_executor(self):
        tree = ast.parse((ROOT / "tools/m9_rtc_neutralization.py").read_text(encoding="utf-8"))
        allowed = {"__future__", "argparse", "importlib.metadata", "json", "os", "struct", "pathlib", "m9_executor_preflight"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertTrue(all(a.name in allowed for a in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            if isinstance(node, ast.Call):
                self.assertNotIn(ast.unparse(node.func), ("os.system", "os.popen", "exec", "eval", "__import__"))

    def test_source_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src/command_handler.c").write_text("changed source", encoding="utf-8")
            with patch("m9_rtc_neutralization.installed_identity", return_value={}):
                with self.assertRaisesRegex(ExecutorError, "Pinned source changed"):
                    audit_sources(root, root, root)

    def test_port_open_override_rejected_before_source_gate(self):
        with patch("m9_rtc_neutralization.installed_identity", return_value={}), patch.dict(os.environ, {"ESPTOOL_OPEN_PORT_ATTEMPTS": "2"}):
            with self.assertRaisesRegex(ExecutorError, "OPEN_PORT_ATTEMPTS"):
                audit_sources(ROOT, ROOT, ROOT)

    def test_phase_c_cold_gate_and_frozen_identity_not_promoted(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["eboot_cold_start_gate"], "HOLD")
        self.assertEqual(FROZEN_BYTES, 399168)
        self.assertEqual(FROZEN_SHA, "cd99139121fa47fedd6286a185fb16e8fb9e120280ecd75f1c6b41b905e31011")
        self.assertEqual(len(manifest["esptool_files"]), 53)
        self.assertIn("include/esp-stub-lib/soc_utils.h", manifest["rtc_neutralization_sources"]["library_files"])

    def test_frozen_local_candidate_rehashed_or_absent_from_ci(self):
        candidate = ROOT / "research-local/m9-phase-b/candidate-4m2m.bin"
        if candidate.exists():  # Authorized retained LOCAL candidate only; no MASTER/PRE/POST.
            self.assertFalse(candidate.is_symlink())
            data = candidate.read_bytes()
            self.assertEqual(len(data), FROZEN_BYTES)
            self.assertEqual(hashlib.sha256(data).hexdigest(), FROZEN_SHA)
        else:  # CI intentionally has no owner-local artifact input.
            workflow = (ROOT / ".github/workflows/m9-flash-layout.yml").read_text(encoding="utf-8")
            self.assertNotIn("candidate-4m2m.bin", workflow.split("name: Fetch pinned public", 1)[0])
            self.assertNotIn("research-local", workflow)

    def test_ci_retains_reviewed_json_only_no_private_inputs(self):
        workflow = (ROOT / ".github/workflows/m9-flash-layout.yml").read_text(encoding="utf-8")
        artifact = workflow.split("name: Upload safe numeric evidence only", 1)[1].split("if-no-files-found", 1)[0]
        retained = {line.strip() for line in artifact.splitlines()
                    if line.strip().startswith("${{ runner.temp }}/m9-")}
        self.assertEqual(retained, {
            "${{ runner.temp }}/m9-" + name + ".json" for name in
            ("layout", "fs", "build", "fsless", "first-migration",
             "stage2-source", "stage2-package")})
        self.assertNotIn("research-local", workflow)
        self.assertNotIn("PRIVATE_MASTER_BIN", workflow)
        self.assertIn("python tools/m9_rtc_neutralization.py", workflow)


if __name__ == "__main__":
    unittest.main()
