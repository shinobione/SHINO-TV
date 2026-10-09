"""Fail-closed regressions for local-only owner-private M9 preparation."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shino_owner_transition as owner


def fixture_credentials():
    return {
        "device": "fedcba9876543210",
        "build": "b" * 64,
        "ap_psk": "P" * 34,
        "api_token": "T" * 40,
        "digest_password": "D" * 42,
        "maintenance_password": "M" * 64,
    }


class OwnerTransition(unittest.TestCase):
    def setUp(self):
        owner.OWNER.mkdir(parents=True, exist_ok=True)

    def test_schema_and_public_fixture_rejected(self):
        credential = fixture_credentials()
        self.assertEqual(owner.validate_owner(credential), credential)
        with self.assertRaises(ValueError):
            owner.validate_owner(dict(credential, ap_psk="short"))
        with self.assertRaises(ValueError):
            owner.validate_owner(dict(credential, build="a" * 63))
        with self.assertRaises(ValueError):
            owner.validate_owner(dict(credential, api_token=credential["digest_password"]))
        with self.assertRaises(ValueError):
            owner.validate_owner(dict(credential, ap_psk=owner.PUBLIC["ap_psk"]))
        with self.assertRaises(ValueError):
            owner.validate_owner(dict(credential, extra="not allowed"))

    def test_private_graph_injected_and_public_fixture_absent(self):
        with tempfile.TemporaryDirectory(dir=owner.OWNER) as tmp:
            directory = Path(tmp) / "source"
            (directory / "src/boot").mkdir(parents=True)
            (directory / "include").mkdir(parents=True)
            (directory / "src/boot/M9NormalStageA.cpp").write_text(
                'static constexpr char ReviewDevice[]="0123456789abcdef";\n'
                'static constexpr char ReviewBuild[]=\n'
                '"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";\n'
                'static constexpr char ReviewMaintenanceKey[]=\n'
                '"1111111111111111111111111111111111111111111111111111111111111111";\n'
                'if(!armGate.consume(p) || !p.dryRun)return false;\n'
                'c={p.device,p.build,p.key,true,true};return true;\n'
                '    if(!dryRun){respond(403,"{\\\"error\\\":\\\"PUBLIC_REVIEW_DRY_RUN_ONLY\\\"}");return;}\n',
                encoding="utf-8")
            (directory / "include/shino_private_policy.h").write_text(
                '#define SHINO_SETUP_AP_PSK "PUBLIC-INERT-AP-FIXTURE"\n'
                '#define SHINO_BOOTSTRAP_API_TOKEN "PUBLIC-INERT-TOKEN-FIXTURE-00000000"\n'
                '#define SHINO_RESCUE_HTTP_PASSWORD "PUBLIC-INERT-LAB-HTTP-FIXTURE"\n',
                encoding="utf-8")
            (directory / "platformio.ini").write_text(
                'build_flags = -DSHINO_PUBLIC_INERT_REVIEW=1\n', encoding="utf-8")
            (directory / "public-inputs.json").write_text(json.dumps({
                "not_flashable_or_owner_qualified": True,
                "public_inert_hmac_credential_only": True,
                "public_install_denied": True
            }), encoding="utf-8")
            config = fixture_credentials()
            with patch.object(owner, "prepare_public", lambda path: path):
                path = owner.private_source(directory, config)
            cpp = (path / "src/boot/M9NormalStageA.cpp").read_text()
            policy = (path / "include/shino_private_policy.h").read_text()
            ini = (path / "platformio.ini").read_text()
            info = json.loads((path / "public-inputs.json").read_text())
            self.assertIn(config["device"], cpp)
            self.assertIn(config["build"], cpp)
            self.assertIn(hashlib.sha256(config["maintenance_password"].encode()).hexdigest(), cpp)
            self.assertNotIn(config["maintenance_password"], cpp)
            self.assertNotIn("PUBLIC_REVIEW_DRY_RUN_ONLY", cpp)
            self.assertIn("c={p.device,p.build,p.key,true,p.dryRun};return true;", cpp)
            self.assertNotIn("-DSHINO_PUBLIC_INERT_REVIEW=1", ini)
            self.assertIn("-DSHINO_OWNER_PRIVATE_TRANSITION=1", ini)
            self.assertIn(config["ap_psk"], policy)
            self.assertIn(config["digest_password"], policy)
            self.assertIn(config["api_token"], policy)
            self.assertNotIn(config["maintenance_password"], json.dumps(info))
            self.assertTrue(info["owner_private_identity"])
            self.assertTrue(info["not_flashable_or_owner_qualified"])

    def test_non_private_output_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AssertionError):
                owner.private_source(Path(tmp) / "bad", fixture_credentials())


if __name__ == "__main__":
    unittest.main()
