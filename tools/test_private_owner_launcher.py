"""Source-only safeguards for Windows owner-private review launcher (never execute .cmd)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "start-private-owner-build.cmd"
BUILDER = ROOT / "tools/build_private_owner_packet.py"


class OwnerPrivateLauncherTests(unittest.TestCase):
    def test_explicit_optional_heap_profile_only(self):
        launcher = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn('if "%~3"=="" goto usage', launcher)
        self.assertIn('if not "%~5"=="" goto usage', launcher)
        self.assertIn('if not "%~4"=="" if /I not "%~4"=="--heap-diagnostics" goto usage', launcher)
        self.assertEqual(launcher.count('py -3 tools\\build_private_owner_packet.py --official-zip '), 2)
        self.assertIn('--expected-source-sha "%~3" --heap-diagnostics', launcher)
        self.assertIn('--expected-source-sha "%~3"\n)', launcher)
        self.assertIn('PRIVATE REVIEW KIT GENERATED. STILL NOT PERMISSION TO FLASH.', launcher)

    def test_builder_keeps_oem_receiver_and_separate_private_policy(self):
        source = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"--oem-zip", str(original), "--enable-restore"', source)
        self.assertIn('APP_HEAP = ROOT / "firmware/.pio/build/esp12e_heap_diagnostics/firmware.bin"', source)
        self.assertIn('"esp12e_heap_diagnostics" if heap_diagnostics else "esp12e"', source)
        self.assertIn('if diagnostic_present is not heap_diagnostics:', source)
        self.assertIn('if APP.exists() or APP_HEAP.exists():', source)
        self.assertIn('if POLICY.exists() or CREDENTIALS.exists():', source)
        self.assertIn('if report["permission_to_flash"] or report["files_uploaded"]:', source)
        self.assertIn('"physical_device_contacted": False', source)
        self.assertIn('private_app = temporary / candidate_name', source)

    def test_launcher_has_no_upload_or_restore_action(self):
        source = LAUNCHER.read_text(encoding="utf-8")
        invoked = [line.strip() for line in source.splitlines()
                   if line.strip().lower().startswith(("py ", "pio ", "curl ", "esptool "))]
        self.assertEqual(len(invoked), 2)
        for cmd in invoked:
            self.assertIn("build_private_owner_packet.py", cmd)
            for forbidden in (" --port ", " -t upload", "write-flash", "erase-flash",
                              " /update", "http://", " https://", " --measure"):
                self.assertNotIn(forbidden, cmd.lower())


if __name__ == "__main__":
    unittest.main()
