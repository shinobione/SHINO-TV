"""B3 → B4 owner packet: offline source/identity gates and no device I/O."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shino_b4_owner_packet as b4


class TestB4OwnerPacket(unittest.TestCase):
    def test_b3_requires_exact_frozen_identity(self):
        old = dict(bytes=b4.B3_BYTES, sha256=b4.B3_SHA256,
                   build_id=b4.B3_BUILD_ID, device="1" * 16)
        with self.assertRaisesRegex(b4.B4Hold, "packet mismatch"):
            b4.check_b3(old, b"wrong", old["device"])
        old["build_id"] = "b" * 64
        with self.assertRaises(b4.B4Hold):
            b4.check_b3(old, b"wrong", old["device"])

    def test_b4_distinct_identity_and_exact_layout(self):
        old = dict(device="1" * 16)
        raw = b"new-b4"
        m = dict(device=old["device"], sha256="f" * 64,
                 build_id="e" * 64)
        report = dict(private=True, source_dirty=False, source_commit="a" * 40,
                      layout_symbols=dict(_FS_start=0x40400000, _FS_end=0x405FA000,
                                          _EEPROM_start=0x405FB000),
                      json_arena_bytes=768, json_document_heap_fallback=False,
                      physical="NOT_RUN", native_heap_peak_measured=False)
        with self.assertRaisesRegex(b4.B4Hold, "B4 staging"):
            b4.check_b4(m, b"x" * 0xFF000, report, old, "a" * 40)
        b4.check_b4(m, raw * 10000, report, old, "a" * 40)
        for override in ({"private": False}, {"source_dirty": True},
                         {"source_commit": "b" * 40},
                         {"native_heap_peak_measured": True}):
            with self.subTest(override=override), self.assertRaises(b4.B4Hold):
                b4.check_b4(m, raw * 10000, dict(report, **override), old, "a" * 40)
        with self.assertRaises(b4.B4Hold):
            b4.check_b4(dict(m, sha256=b4.B3_SHA256),
                        raw * 10000, report, old, "a" * 40)

    def test_source_gate_rejects_modified_firmware(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in b4.FROZEN_SOURCES:
                f = root / name
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(b"frozen\n")

            def git(args, **kwargs):
                if args[1:3] == ["branch", "--show-current"]:
                    return b4.BRANCH.encode()
                if args[1:3] == ["status", "--porcelain"]:
                    return b""
                if args[1:3] == ["rev-parse", "HEAD"]:
                    return b"a" * 40
                if args[1] == "show":
                    return b"frozen\n"
                raise AssertionError("unexpected git operation")

            with patch.object(subprocess, "check_output", side_effect=git):
                self.assertEqual(b4.verify_checkout(root), "a" * 40)
                (root / b4.FROZEN_SOURCES[0]).write_bytes(b"changed\n")
                with self.assertRaisesRegex(b4.B4Hold, "source changed"):
                    b4.verify_checkout(root)

    def test_missing_private_or_reused_output_never_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            owner = root / "research-local" / "m9-owner"
            owner.mkdir(parents=True)
            build_calls = []
            params = dict(inspect=lambda *a: (_ for _ in ()).throw(
                              AssertionError("private read before source gate")),
                          load=lambda: (_ for _ in ()).throw(
                              AssertionError("private load before source gate")),
                          build=lambda *a: build_calls.append(a),
                          checker=lambda _: (_ for _ in ()).throw(
                              b4.B4Hold("Unsafe checkout")))
            with self.assertRaises(b4.B4Hold):
                b4.prepare(root, owner, owner / "NEW", **params)
            self.assertFalse((owner / "NEW").exists())
            (owner / "REUSED").mkdir()
            with self.assertRaisesRegex(b4.B4Hold, "Fresh direct"):
                b4.prepare(root, owner, owner / "REUSED", **params)
            with self.assertRaises(b4.B4Hold):
                b4.prepare(root, owner, root / "outside", **params)
            self.assertEqual(build_calls, [])

    def test_new_packet_created_only_from_verified_offline_mocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            owner = root / "research-local" / "m9-owner"
            owner.mkdir(parents=True)
            out = owner / "b4-qa-fresh"
            secret = dict(device="1" * 16, maintenance_password="testsecret",
                          ap_psk="p" * 32, api_token="t" * 32,
                          digest_password="d" * 32)
            digest = hashlib.sha256(secret["maintenance_password"].encode()).digest()
            raw = b"image" * 15000 + digest + b"|".join(
                secret[k].encode() for k in ("ap_psk", "api_token", "digest_password"))
            b4manifest = dict(sha256="f" * 64, build_id="b" * 64, bytes=len(raw),
                              device=secret["device"])
            calls = []
            def inspect(binary, manifest):
                calls.append("inspect")
                if "b3-owner" in str(binary):
                    return dict(device=secret["device"]), b"old"
                return b4manifest, raw
            def fake_build(target, private):
                calls.append("build")
                self.assertTrue(private)
                self.assertFalse(target.exists())
                target.mkdir()
                return {"private": True}
            with patch.object(b4, "check_b3") as guard_b3, \\
                 patch.object(b4, "check_b4") as guard_b4, \\
                 patch("socket.socket", side_effect=AssertionError("NETWORK")) as network:
                result = b4.prepare(root, owner, out,
                                    inspect=inspect, load=lambda: secret,
                                    build=fake_build, checker=lambda _: "a" * 40)
                network.assert_not_called()
                guard_b3.assert_called_once()
                guard_b4.assert_called_once()
            self.assertEqual(calls, ["inspect", "build", "inspect"])
            self.assertEqual(result["ota_offline_gate"], "HOLD")
            self.assertFalse(result["physical_install_authorized"])
            self.assertEqual(result["device_contacts"], 0)
            self.assertEqual(result["ota_posts"], 0)
            self.assertTrue((out / "B4-OFFLINE-REVIEW.json").is_file())
            self.assertTrue((out / "NEXT-OWNER-DECISION.md").is_file())
            self.assertNotIn(secret["maintenance_password"],
                             (out / "NEXT-OWNER-DECISION.md").read_text())
            self.assertEqual(json.loads((out / "B4-OFFLINE-REVIEW.json").read_text())["status"],
                             "B4_OWNER_PRIVATE_CANDIDATE_OFFLINE_ONLY")


if __name__ == "__main__":
    unittest.main()
