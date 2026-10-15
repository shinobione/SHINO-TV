"""B5.3 private builder safety tests, no credentials/PlatformIO/device."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shino_b53_lean_owner_candidate as target

class OwnerGate(unittest.TestCase):
    def test_wrong_branch_stops_before_private_read(self):
        with patch.object(target.subprocess,"check_output",return_value="main\n"), \
             patch.object(target,"private_source_gate",side_effect=AssertionError("NO")):
            with self.assertRaisesRegex(ValueError,"not on B5.3"):
                target.preflight()

    def test_divergent_remote_stops_before_secret_lookup(self):
        with patch.object(target.subprocess,"check_output",side_effect=[
                target.BRANCH+"\n","b"*40+"\n"]), \
             patch.object(target,"private_source_gate",return_value="a"*40), \
             patch.object(target,"owner_credentials",side_effect=AssertionError("NO")):
            with self.assertRaisesRegex(ValueError,"diverged"):
                target.preflight()

    def test_missing_credentials_fail_closed(self):
        with patch.object(target.subprocess,"check_output",side_effect=[
                target.BRANCH+"\n","a"*40+"\n"]), \
             patch.object(target,"private_source_gate",return_value="a"*40), \
             patch.object(target,"owner_credentials",side_effect=ValueError("missing")):
            with self.assertRaisesRegex(ValueError,"missing"):
                target.preflight()

    def test_no_pinned_deps_cannot_start_owner_build(self):
        with patch.object(target,"preflight",return_value="a"*40), \
             patch.object(target,"available_libraries",return_value=iter(())), \
             patch.object(target,"build_public_b51",side_effect=AssertionError("NO")), \
             patch.object(target,"build_lean",side_effect=AssertionError("NO")):
            with self.assertRaisesRegex(ValueError,"pinned libraries"):
                target.run()

    def test_only_matching_existing_private_graph_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            owner=root/"research-local"/"m9-owner"
            owner.mkdir(parents=True)
            libraries=root/"deps"
            libraries.mkdir()
            # fake build generates no real secret or firmware
            blob=b"dummy binary for mocked builder"
            release={"bytes":len(blob),"sha256":target.hashlib.sha256(blob).hexdigest(),
                     "layout":"4m2m"}
            def fake_build(output,libs,private):
                assert private and libs==libraries
                p=output/".pio"/"build"/target.ENV
                p.mkdir(parents=True)
                (p/"firmware.bin").write_bytes(blob)
                (output/"release.json").write_text(json.dumps(release))
                source=output/"src"/"boot"
                source.mkdir(parents=True)
                (source/"M9NormalStageA.cpp").write_text(
                    "B53Sntp::begin(); B52Clock::step(now);")
                return {"bytes":len(blob),"sha256":release["sha256"],
                        "source_commit":"a"*40,"source_dirty":False,
                        "layout":"4m2m","private":True,"private_build":True,
                        "clock_authority":True,"lean_variant":True,
                        "weather_network_source":False,"weather_configured":False,
                        "noinit":56,"physical":"NOT_RUN","ota_posts":0,
                        "device_contacts":0,"static_ram":46000}
            with patch.object(target,"OWNER",owner), \
                 patch.object(target,"preflight",return_value="a"*40), \
                 patch.object(target,"pinned_libraries",return_value=True), \
                 patch.object(target,"owner_credentials",return_value=root/"existing.json"), \
                 patch.object(target,"build_lean",side_effect=fake_build), \
                 patch.object(target.owner_identity,"SECRETS",root/"no.json"):
                result=target.run(libraries=libraries)
                self.assertEqual(result["verdict"],"B53_LEAN_PRIVATE_OFFLINE_ONLY_PHYSICAL_HOLD")
                self.assertEqual(result["sha256"],release["sha256"])
                self.assertTrue(list(owner.glob("*/b53-lean-safe-receipt.json")))

if __name__=="__main__":
    unittest.main()
