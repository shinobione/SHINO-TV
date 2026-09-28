"""Fail-closed checks for shared ESP8266 Updater signature vs pinned OEM app.

Core 3.1.2's Updater.end() executes _verify instead of _target_md5 when a
signing verifier is installed, and Updater._reset() does not wipe _verify.
Therefore an unsigned OEM MD5 pin must NOT coexist with global signing.
This is SOURCE safety review, NOT a physical install/recovery test.
"""
from pathlib import Path
import re
import shutil
import subprocess
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

    def test_actual_oem_preprocessor_guards_reject_unsafe_signing_matrix(self):
        """Execute the source's real #error block through a host C++ preprocessor."""
        compiler = shutil.which("g++")
        self.assertIsNotNone(compiler, "A C++ preprocessor is required by CI")
        source = OEM.read_text(encoding="utf-8")
        start = source.index("#ifndef SHINO_ENABLE_NATIVE_SIGNED_OTA")
        end = source.index("#ifndef SHINO_FACTORY_BYTES", start)
        actual_guards = source[start:end]

        def compile_guards(native: int | None, factory: int, core_signing: int):
            definitions = ["#define SHINO_ENABLE_FACTORY_RESTORE " + str(factory),
                           "#define ARDUINO_SIGNING " + str(core_signing)]
            if native is not None:
                definitions.append("#define SHINO_ENABLE_NATIVE_SIGNED_OTA " + str(native))
            snippet = "\n".join(definitions) + "\n" + actual_guards + "\nint main() { return 0; }\n"
            return subprocess.run([compiler, "-std=c++17", "-x", "c++", "-fsyntax-only", "-"],
                                  input=snippet, capture_output=True, text=True, timeout=10,
                                  check=False)

        for native, factory, core_signing in ((0,0,0), (0,1,0), (0,0,1)):
            with self.subTest(native=native, factory=factory, core_signing=core_signing):
                result=compile_guards(native,factory,core_signing)
                self.assertEqual(result.returncode,0,result.stderr)
        for native, factory, core_signing in ((None,0,0), (1,0,0), (1,1,0),
                                               (1,0,1), (0,1,1)):
            with self.subTest(native=native, factory=factory, core_signing=core_signing):
                result=compile_guards(native,factory,core_signing)
                self.assertNotEqual(result.returncode,0)
                self.assertIn("error:",result.stderr.lower())

    def test_both_ota_builds_pin_reviewed_core_version(self):
        for path in ("firmware/platformio.ini", "recovery_loader/platformio.ini"):
            with self.subTest(path=path):
                ini = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("platform = espressif8266@4.2.1", ini)
                self.assertIn(
                    "platformio/framework-arduinoespressif8266@3.30102.0", ini
                )
                self.assertNotIn("\\nplatform = espressif8266\\n", ini)

    def test_experimental_writer_never_signing_bypass_exception(self):
        src = OEM.read_text(encoding="utf-8")
        self.assertNotIn("installSignature(nullptr", src)
        self.assertNotIn("installSignature(NULL", src)
        self.assertIn("SHINO_FACTORY_MD5", src)
        self.assertIn("SHINO_FACTORY_SHA256", src)

if __name__ == "__main__":
    unittest.main()
