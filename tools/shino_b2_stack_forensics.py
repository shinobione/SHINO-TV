"""B2 continuation stack forensic inventory from a PUBLIC compiled ELF.

The OTA stack graph is already bounded where modeled by
shino_http_ota_stack.audit(). This complement enumerates *normal runtime*
handlers, including Digest/metrics/status; it deliberately never promotes
a collection of individual frame sizes into a complete native stack bound.
Reads already-built public .su/ELF and tracked source only. No sockets,
device IO, reset, OTA, marker writes, or credential read.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from m9_stagea_build import ENV, ROOT
from shino_http_ota_stack import audit as ota_audit


TRACKED_NORMAL = ROOT / "ota/firmware/Normal.cpp"
TRACKED_RESOURCES = ROOT / "firmware/include/boot/M9NormalResources.h"
TARGETS = {
    "identity_get": "::identity()",
    "normal_status_get": "::status()",
    "telemetry_post": "::telemetry()",
    "metrics_get": "::metrics()",
    "digest_gate": "::auth()",
    "pre_body_gate": "::beforeBody()",
    "request_route": "::route()",
    "response_send": "::respond(",
}
# These are pre-existing, verified frame ceilings. NOT a whole path budget.
RETAINED_FRAME_CAPS = {
    "identity_get": 160,
    "normal_status_get": 256,
    "metrics_get": 112,
}


def rows_of_su(data: str):
    rows = []
    for line in data.splitlines():
        fields = line.rsplit("\t", 2)
        if len(fields) != 3:
            continue
        label, count, nature = fields
        if not count.isdecimal():
            continue
        # GCC/G++ stack usage label format:
        #    <source>:<line>:<column>:<demangled signature>
        match = re.match(r"^.*?:\d+:\d+:(.+)$", label)
        signature = match.group(1) if match else label
        rows.append(dict(signature=signature, frame_bytes=int(count),
                         kind=nature))
    return rows


def collect_frames(folder: Path):
    folder = Path(folder)
    build = folder / ".pio" / "build" / ENV
    if not build.is_dir() or not (build / "firmware.elf").is_file():
        raise ValueError("No compiled public ELF; build first")
    normal_su = build / "src" / "boot" / "M9NormalStageA.cpp.su"
    if not normal_su.is_file():
        raise ValueError("Missing native normal-HTTP .su")
    rows = rows_of_su(normal_su.read_text(errors="replace"))
    if not rows:
        raise ValueError("Missing native stack metadata")
    selected = {}
    for label, marker in TARGETS.items():
        match = [r for r in rows if marker in r["signature"]]
        if len(match) == 1:
            row = match[0]
            selected[label] = dict(state="MEASURED_STATIC" if row["kind"] == "static" else "DYNAMIC_UNKNOWN",
                                   frame_bytes=row["frame_bytes"] if row["kind"] == "static" else None,
                                   kind=row["kind"])
        else:
            # GCC can inline functions; absent .su does NOT mean a zero frame.
            selected[label] = dict(state="INLINED_OR_AMBIGUOUS" if not match else "AMBIGUOUS",
                                   frame_bytes=None, matches=len(match))
    for label, ceiling in RETAINED_FRAME_CAPS.items():
        row = selected[label]
        if row["state"] != "MEASURED_STATIC" or row["frame_bytes"] > ceiling:
            raise ValueError("Unverified or regressed original native frame: " + label)
    return selected, rows


def highwater_source_guard(normal: str, resources: str):
    # Track the actual code paths, not commentary or an assertion that it can
    # never be repainted during the whole boot. The observer resets in setup.
    assert "uint32_t stack(){return ESP.getFreeContStack();}" in normal
    assert "void resetStack(){ESP.resetFreeContStack();}" in normal
    assert "if(apReady)server.handleClient();" in normal
    assert "observer.poll();" in normal
    assert "server.requestAuthentication(DIGEST_AUTH," in normal
    # Either the pinned B2 locals or the B3 guarded, per-request placement
    # workspace must be present; never silently accept a missing parser.
    b2_local = "const String payload=server.arg(\"plain\");JsonDocument doc;" in normal
    b3_scratch = all(part in normal for part in (
        "TelemetryScratchLease scratch;",
        "ResponseLease responseLease_;",
        "scratch_->~TelemetryScratch();",
        'deserializeJson(scratch->doc,server.arg("plain"))',
        "FslessMetrics::apply(scratch->doc.as<JsonVariantConst>(),scratch->error)",
    ))
    assert b2_local or b3_scratch
    assert "void identity()" in normal and "void status()" in normal
    assert "void telemetry()" in normal and "void metrics()" in normal
    assert "void poll()" in resources
    section = resources.split("void poll()", 1)[1].split("const Observation& status()", 1)[0]
    if "reset()" in section or "resetStack()" in section:
        raise ValueError("Unexpected periodic continuation-stack repaint")
    return True


def audit(folder: Path):
    normal = TRACKED_NORMAL.read_text(encoding="utf-8")
    observer = TRACKED_RESOURCES.read_text(encoding="utf-8")
    if not highwater_source_guard(normal, observer):
        raise ValueError("Unexpected continuation stack semantics")
    handlers, rows = collect_frames(folder)
    ota = ota_audit(folder)  # Existing linked Xtensa/.su crosschecks remain mandatory.
    if ota["whole_native_upper_bound"]:
        raise ValueError("Never treat compiled subpaths as a whole native bound")
    normal_functions = sorted(
        (dict(name=r["signature"], frame_bytes=r["frame_bytes"], kind=r["kind"])
         for r in rows if "M9NormalStageA" in r["signature"]),
        key=lambda item: item["frame_bytes"], reverse=True)
    return dict(
        status="COMPILED_NORMAL_HANDLER_FRAMES_NOT_NATIVE_STACK_BOUND",
        stack_free_floor=2048,
        stack_budget_total=4096,
        native_highwater_is_historical=True,
        reset_during_setup=True,
        reset_during_poll=False,
        simultaneous_runtime_paths=["normal_status_GET", "identity_GET",
                                    "telemetry_POST", "digest_challenge_or_verify",
                                    "display_render_and_yield"],
        source_sha256=hashlib.sha256(normal.encode()).hexdigest(),
        candidate_source_changed=hashlib.sha256(normal.encode()).hexdigest() != "bd20e294427a381a5833da52763b76b8e193a0bfd3625c917e2bf753430d83fd",
        handler_frames=handlers,
        top_normal_frames=normal_functions[:16],
        compiled_ota_max_path_bytes=max(p["compiled_bytes"] for p in ota["paths"].values()),
        known_ota_native_upper_bound=False,
        complete_normal_native_upper_bound=False,
        unresolved_paths=["ESP8266WebServer request parser and Digest helper call chains",
                          "ArduinoJson deserialize and allocations",
                          "DisplayManager / SPI and rendering",
                          "lwIP, SDK, ROM, allocator and interrupt/callback paths",
                          "interleaved events and actual continuation high-water"],
        acceptance_floor_changed=False,
        physical="NOT_RUN",
        device_contacts=0,
        ota_posts=0,
        serial_writes=0,
        firmware_changed=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public_build", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.public_build), indent=2))
