"""Compare compiled public B2 normal HTTP handler frames. No device contact.

This gate validates a narrower .su frame. It never asserts that native
continuation high-water, SDK/ROM stack or a physical OTA passed.
"""
import argparse
import json
from pathlib import Path

PINNED_SOURCE = "bd20e294427a381a5833da52763b76b8e193a0bfd3625c917e2bf753430d83fd"
PINNED_TELEMETRY = 224
MAX_STATIC_GROWTH = 256  # explicit candidate budget, NOT physical heap proof
BASELINE = Path(__file__).parent / "fixtures" / "shino_b2_public_stack_baseline.json"


class Hold(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Hold(reason)


def measured(report, name):
    entry = report.get("handler_frames", {}).get(name)
    require(isinstance(entry, dict) and entry.get("state") == "MEASURED_STATIC", "Unverified frame: " + name)
    value = entry.get("frame_bytes")
    require(type(value) is int and 0 <= value <= 4096, "Invalid frame: " + name)
    return value


def compare(baseline, stack, build):
    require(baseline.get("source_sha256") == PINNED_SOURCE and
            baseline.get("baseline_telemetry_frame_bytes") == PINNED_TELEMETRY,
            "Pinned B2 baseline mismatch")
    require(stack.get("status") == "COMPILED_NORMAL_HANDLER_FRAMES_NOT_NATIVE_STACK_BOUND" and
            stack.get("stack_free_floor") == 2048 and
            stack.get("stack_budget_total") == 4096 and
            stack.get("native_highwater_is_historical") is True and
            stack.get("reset_during_poll") is False and
            stack.get("complete_normal_native_upper_bound") is False and
            stack.get("physical") == "NOT_RUN" and
            stack.get("device_contacts") == 0 and stack.get("ota_posts") == 0 and
            stack.get("serial_writes") == 0,
            "Stack semantics, scope or safety boundary changed")
    for key in ("identity_get", "normal_status_get", "metrics_get", "pre_body_gate", "response_send"):
        require(measured(stack, key) <= baseline["handler_frames"][key], key + " frame regressed")
    new_frame = measured(stack, "telemetry_post")
    require(new_frame < PINNED_TELEMETRY, "No compiled telemetry frame reduction")
    require(build.get("physical") == "NOT_RUN" and
            build.get("device_contacts") == 0 and
            build.get("layout") == "4m2m" and
            build.get("noinit") == 56 and
            build.get("core_buffer") == 4096 and
            build.get("layout_symbols") == baseline["layout_symbols"],
            "Compiled layout / device isolation changed")
    ram = build.get("static_ram")
    require(type(ram) is int and ram <= baseline["static_ram"] + MAX_STATIC_GROWTH,
            "Static RAM candidate cap exceeded")
    length = build.get("bytes")
    require(type(length) is int and 64000 <= length <= 0xFEFF0, "Candidate size invalid")
    for key, limit in baseline["retained_frame_caps"].items():
        value = build.get("stack_frames", {}).get(key)
        require(type(value) is int and value <= limit, "Protected compiler frame regressed: " + key)
    return dict(status="COMPILED_FRAME_REDUCTION_NOT_PHYSICAL_PASS",
                baseline_frame_bytes=PINNED_TELEMETRY,
                candidate_frame_bytes=new_frame,
                compiled_frame_reduction_bytes=PINNED_TELEMETRY-new_frame,
                static_ram_growth_bytes=ram-baseline["static_ram"],
                static_ram_growth_limit_bytes=MAX_STATIC_GROWTH,
                native_highwater_proven=False, physical_qualification="HOLD",
                ota_authorized=False, device_contacts=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--stack-report", type=Path, required=True)
    parser.add_argument("--build-report", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = compare(json.loads(args.baseline.read_text()),
                         json.loads(args.stack_report.read_text()),
                         json.loads(args.build_report.read_text()))
    except (Hold, ValueError, KeyError, OSError) as exc:
        print(json.dumps(dict(status="CANDIDATE_HOLD", reason=str(exc),
                              device_contacts=0, ota_authorized=False)))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
