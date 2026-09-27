"""Fail-closed checks for shared ESP8266 Updater signature vs pinned OEM app.

Core 3.1.2's Updater.end() executes _verify instead of _target_md5 when a
signing verifier is installed, and Updater._reset() does not wipe _verify.
Therefore an unsigned OEM MD5 pin must NOT coexist with global signing.
This is SOURCE safety review, NOT a physical install/recovery test.
"""
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "tools/generate_shino_device_policy.py"
BRIDGE = ROOT / "firmware/src/boot/FirstBootBridge.cpp"
OEM = ROOT / "firmware/src/recovery/FactoryRollback.cpp"

class UpdaterSigningIsolationTests(unittest.TestCase):
    def test_private_build_generator_declares_native_writer_explicitly_disabled(self):
        src = GENERATOR.read_text(encoding="utf-8")
        self.assertIn("'#define SHINO_ENABLE_NATIVE_SIGNED_OTA 0\\n'", src)
        self.assertNotIn("enable-native-ota", src)
        self.assertNotIn("--enable-native-ota", src)

    def test_bridge_refuses_any_enabled_native_writer_pre_release(self):
        src = BRIDGE.read_text(encoding="utf-8")
        self.assertIn('#ifndef SHINO_ENABLE_NATIVE_SIGNED_OTA', src)
        self.assertRegex(src, r'static_assert\(SHINO_ENABLE_NATIVE_SIGNED_OTA\s*==\s*0,')
        self.assertIn('doc["native_ota_writer_compiled"] = false;', src)
        self.assertIn('doc["native_ota_upload_route_registered"] = false;', src)
        for method in ("/api/v1/bridge/ota/arm", "/api/v1/bridge/ota/upload",
                       "/api/v1/bridge/ota/install"):
            self.assertNotIn('server.on("' + method + '"', src)

    def test_oem_return_is_compile_blocked_under_global_native_signing(self):
        src = OEM.read_text(encoding="utf-8")
        self.assertIn('#include <Updater_Signing.h>', src)
        self.assertIn('#ifndef SHINO_ENABLE_NATIVE_SIGNED_OTA', src)
        self.assertRegex(src, r'#if SHINO_ENABLE_NATIVE_SIGNED_OTA\s*!=\s*0\n#error ')
        self.assertRegex(src, r'#if SHINO_ENABLE_FACTORY_RESTORE\s*&&\s*ARDUINO_SIGNING\n#error ')
        self.assertIn("Update.setMD5(SHINO_FACTORY_MD5)", src)
        self.assertNotIn("Update.installSignature(", src)
        self.assertNotIn("Update.end(true)", src)

    def test_no_public_writer_implementation_in_research_modules(self):
        for path in ("firmware/include/boot/NativeOtaIntentGate.h",
                     "firmware/include/boot/NativeOtaRequestPolicy.h"):
            source = (ROOT / path).read_text(encoding="utf-8")
            source = "\n".join(line for line in source.splitlines()
                               if not line.lstrip().startswith("//"))
            for forbidden in ("Update.begin(", "Update.write(", "Update.end(",
                              "installSignature(", "U_FS", "U_FLASH",
                              "ESP8266WebServer", "#include <Updater"):
                self.assertNotIn(forbidden, source)

    def test_experimental_writer_never_signing_bypass_exception(self):
        src = OEM.read_text(encoding="utf-8")
        self.assertNotIn("installSignature(nullptr", src)
        self.assertNotIn("installSignature(NULL", src)
        self.assertIn("SHINO_FACTORY_MD5", src)
        self.assertIn("SHINO_FACTORY_SHA256", src)

if __name__ == "__main__":
    unittest.main()
