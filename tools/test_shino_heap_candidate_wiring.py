"""Exact source/CI locks for the opt-in, non-installing heap diagnostic build.

This test NEVER contacts private AP/device or opens a secret. Xtensa CI compiles
both default and instrumented profiles; the baseline must exclude the marker.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent.parent
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
CANDIDATE=ROOT/"firmware/include/boot/ShinoHeapDiagnosticCandidate.h"
PLATFORM=ROOT/"firmware/platformio.ini"
WORKFLOW=ROOT/".github/workflows/firmware-build.yml"


class ReadOnlyHeapCandidateWiringTests(unittest.TestCase):
    def test_observer_is_opt_in_and_default_build_has_no_heap_status_or_sampler(self):
        src=BRIDGE.read_text(encoding="utf-8")
        config=PLATFORM.read_text(encoding="utf-8")
        self.assertIn("#define SHINO_ENABLE_HEAP_DIAGNOSTICS 0",src)
        self.assertIn("#if SHINO_ENABLE_HEAP_DIAGNOSTICS\n#include \"boot/ShinoHeapDiagnosticCandidate.h\"\n#endif",src)
        self.assertIn("default_envs = esp12e",config)
        self.assertIn("[env:esp12e_heap_diagnostics]",config)
        self.assertIn("extends = env:esp12e",config)
        self.assertIn("-DSHINO_ENABLE_HEAP_DIAGNOSTICS=1",config)
        self.assertIn("board_build.ldscript = eagle.flash.4m3m.ld",config)

    def test_single_existing_digest_status_and_prospective_hook_position(self):
        src=BRIDGE.read_text(encoding="utf-8")
        self.assertEqual(src.count("ESP8266WebServer server(80)"),1)
        self.assertEqual(src.count('server.on("/api/v1/bridge/status", HTTP_GET, sendStatus);'),1)
        self.assertIn('void sendStatus() {\n    if (!requireAuth()) return;',src)
        self.assertEqual(src.count("heapDiagnostic.appendReadOnlyStatus(doc);"),1)
        self.assertEqual(src.count("heapDiagnostic.pollAfterExistingWork(millis());"),1)
        self.assertIn('doc["available_heap_bytes"] = ESP.getFreeHeap();\n#if SHINO_ENABLE_HEAP_DIAGNOSTICS',src)
        hook=src.index("if (networkReady) heapDiagnostic.pollAfterExistingWork(millis());")
        loop=src.index("void loop() {",src.index("namespace FirstBootBridge {"))
        for existing in ("server.handleClient();","paintNativeDashboard();","FactoryRollback::tick();"):
            self.assertLess(src.index(existing,loop),hook)
        self.assertLess(hook,src.index("ESP.wdtFeed();",hook))
        self.assertNotIn('server.on("/api/v1/bridge/heap',src)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',src)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"',src)

    def test_projection_is_observation_only_and_missing_sample_is_not_zero(self):
        src=CANDIDATE.read_text(encoding="utf-8")
        for marker in ("OBSERVED_HEAP_V1","sampling_interval_ms","sample_count",
                       "NO_SAMPLES","SATURATED","SAMPLING",
                       "lowest_observed_free_heap_bytes",
                       "lowest_observed_largest_free_block_bytes",
                       "highest_observed_fragmentation_percent",
                       "latest_fragmentation_percent"):
            self.assertIn(marker,src)
        self.assertIn("if(summary.samples==0u)return;",src)
        self.assertIn("if(cadence_.due(nowMs)) (void)review_.capture();",src)
        self.assertEqual(src.count("ESP.getHeapStats("),1)
        self.assertNotIn("ESP.getFreeHeap()",src)
        executable="\n".join(line for line in src.splitlines()
                            if not line.lstrip().startswith("//"))
        for forbidden in ("Update.begin(", "Update.write(", "Update.end(",
                          "LittleFS.", "EEPROM.", "WiFiServer(", "ESP8266WebServer(",
                          "server.send(", "ESP.restart(", "malloc(", "new "):
            self.assertNotIn(forbidden,executable)

    def test_ci_compiles_both_profiles_without_upload_or_secrets_in_image(self):
        ci=WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pio run -e esp12e\n",ci)
        self.assertIn("pio run -e esp12e_heap_diagnostics\n",ci)
        self.assertIn("generate_shino_device_policy.py --oem-zip",ci)
        self.assertIn("--enable-restore >/dev/null",ci)
        self.assertIn("Rebuild exact OEM-return plus HEAP candidate",ci)
        self.assertIn("b'Verified OEM application image',pinned_md5",ci)
        self.assertEqual(ci.count("pio run -e esp12e_heap_diagnostics"),2)
        self.assertIn("assert b'OBSERVED_HEAP_V1' not in blob",ci)
        self.assertIn("for marker in (b'FIRST_BOOT_BRIDGE', b'OBSERVED_HEAP_V1',",ci)
        self.assertNotIn("pio run -t upload",ci)
        self.assertNotIn("pio run -t uploadfs",ci)
        self.assertLess(ci.index("pio run -e esp12e_heap_diagnostics"),
                        ci.index("Delete proprietary manufacturer source"))


if __name__=="__main__":
    unittest.main()
