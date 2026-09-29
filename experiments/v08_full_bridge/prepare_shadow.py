"""Copy tracked firmware only; never read a generated private policy.

Both link variants have an inert startup guard. No upload command is provided.
The original production project and installed core are never written.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

Import("env")
project = Path(env["PROJECT_DIR"]).resolve()
repo = project.parents[1]
sys.path.insert(0, str(repo / "tools"))
from v08_native_overlay import materialize
from v07_pinned_core_probe import pinned_sources

pinned_sources()
shadow = project / ".pio/shadow"
tracked = subprocess.check_output(
    ["git", "ls-files", "firmware/src", "firmware/include", "firmware/lib"],
    cwd=repo, text=True).splitlines()
manifest = {}
for name in tracked:
    source = repo / name
    if not source.is_file():
        continue
    assert source.name not in ("shino_private_policy.h", "project_version.h")
    target = shadow / Path(name).relative_to("firmware")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    manifest[name] = hashlib.sha256(source.read_bytes()).hexdigest()

policy = '''// PUBLIC INERT LAB FIXTURES. Never a production policy.
#define SHINO_FACTORY_BYTES 494144
#define SHINO_FACTORY_MD5 "00000000000000000000000000000000"
#define SHINO_FACTORY_SHA256 "a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718"
#define SHINO_ENABLE_FACTORY_RESTORE 0
#define SHINO_ENABLE_NATIVE_SIGNED_OTA 0
#define SHINO_BOOT_PROFILE 0
#define SHINO_FS_IMAGE_PRESENT 0
#define SHINO_FS_BYTES 2072576
#define SHINO_FS_SHA256 ""
#define SHINO_FS_MD5 ""
#define SHINO_ENABLE_FS_MIGRATION 0
#define SHINO_SETUP_AP_PSK "PUBLIC-INERT-LAB-AP-FIXTURE"
#define SHINO_BOOTSTRAP_API_TOKEN "PUBLIC-INERT-LAB-API-TOKEN-FIXTURE"
#define SHINO_RESCUE_HTTP_USER "lab"
#define SHINO_RESCUE_HTTP_PASSWORD "PUBLIC-INERT-LAB-HTTP-FIXTURE"
'''
(shadow / "include/shino_private_policy.h").write_text(policy, encoding="utf-8")
(shadow / "include/project_version.h").write_text(
    '#pragma once\n#define PROJECT_VER_STR "V08-M3-LINK-ONLY"\n', encoding="utf-8")
original = shadow / "src/main.cpp"
(shadow / "src/original_main.inc").write_text(
    original.read_text(encoding="utf-8").replace("void setup() {", "void shinoResearchSetup() {")
    .replace("void loop() {", "void shinoResearchLoop() {"), encoding="utf-8")
original.write_text('''// Deliberately unstarted link graph, identical in both environments.
#include <Arduino.h>
#include "original_main.inc"
volatile unsigned char shinoResearchDisabled = 0;
void setup() { if (shinoResearchDisabled) shinoResearchSetup(); }
void loop() { if (shinoResearchDisabled) shinoResearchLoop(); else delay(1000); }
''', encoding="utf-8")
overlay_hashes = None
if env["PIOENV"] == "bridge_preparse":
    overlay = project / ".pio/pinned_overlay"
    overlay_hashes = materialize(overlay)
    env.Prepend(CPPPATH=[str(overlay)])
    env.BuildSources("$BUILD_DIR/v08_mime", str(overlay / "detail"),
                     src_filter=["+<mimetable.cpp>"])
    # Resolve every copied source/header include to the same overlay class ABI.
    # The stock template library remains installed but its guard prevents reuse.
    include = '#include "' + (overlay / "ESP8266WebServer.h").as_posix() + '"'
    for name in tracked:
        target = shadow / Path(name).relative_to("firmware")
        if target.suffix not in (".cpp", ".h") or not target.is_file():
            continue
        text = target.read_text(encoding="utf-8")
        if "#include <ESP8266WebServer.h>" in text:
            target.write_text(text.replace("#include <ESP8266WebServer.h>", include), encoding="utf-8")
manifest["overlay"] = overlay_hashes
(project / ".pio" / (env["PIOENV"] + "-provenance.json")).write_text(
    json.dumps(manifest, indent=2), encoding="utf-8")
