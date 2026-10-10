"""Read-only B3 resource transcript reviewer; NO networking, device IO or OTA.

Accepts already-captured private owner reports but never treats synthetic JSON
or compiler-only evidence as physical qualification. Do not commit owner files.
"""
import argparse
import json
from pathlib import Path

STACK_FLOOR = 2048
HEAP_FLOOR = 20480
BLOCK_FLOOR = 16384
FRAG_CEILING = 25
MIN_POLL_SPAN = 180


class EvidenceHold(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceHold(message)


def integer(record, key, minimum=0, maximum=4294967294):
    value = record.get(key)
    require(type(value) is int and minimum <= value <= maximum,
            "Invalid or unknown evidence field: " + key)
    return value


def review(transcript):
    require(type(transcript) is dict and transcript.get("schema") == 1,
            "Unrecognized or missing resource transcript")
    require(transcript.get("source") == "OWNER_CAPTURED_READONLY_STATUS",
            "Only owner-captured read-only status responses are eligible")
    manifest = transcript.get("expected_manifest")
    require(type(manifest) is dict and manifest.get("layout") == "4m2m"
            and manifest.get("protocol") == "shino-http-ota-1",
            "Missing reviewed owner 4m2m manifest")
    for key in ("device", "build_id", "sha256"):
        v = manifest.get(key)
        n = 16 if key == "device" else 64
        require(type(v) is str and len(v) == n and all(c in "0123456789abcdef" for c in v),
                "Unverifiable manifest identity: " + key)
    integer(manifest, "bytes", 64000, 0xFEFF0)
    records = transcript.get("observations")
    require(type(records) is list and len(records) >= 3,
            "Need at least three separate in-boot status checkpoints")
    prev = None
    first_count = last_count = 0
    min_stack = 4096
    min_heap = 81920
    min_block = 81920
    max_frag = 0
    for index, pair in enumerate(records):
        require(type(pair) is dict, "Invalid checkpoint")
        identity, status = pair.get("identity"), pair.get("status")
        require(type(identity) is dict and type(status) is dict,
                "Each checkpoint must include identity and status JSON")
        for field in ("device", "build_id", "sha256", "bytes"):
            require(identity.get(field) == manifest[field],
                    "Firmware manifest drift across checkpoints: " + field)
        require(identity.get("protocol") == manifest["protocol"]
                and identity.get("ota_enabled") is True
                and identity.get("fs_ok") is True,
                "Normal private runtime identity / filesystem not verified")
        boot = identity.get("boot_id")
        require(type(boot) is str and len(boot) == 32
                and all(c in "0123456789abcdef" for c in boot),
                "Missing unique boot identifier")
        if prev is not None:
            require(boot == prev["boot"], "Boot changed between checkpoints")
        for key in ("config_loaded_readonly", "private_ap_ready",
                    "mounted", "inventory_exact", "config_seed_exact",
                    "resource_measurements_valid", "design_floors_observed"):
            require(status.get(key) is True, "Unsafe status checkpoint: " + key)
        for key, value in (("heap_floor", HEAP_FLOOR),
                           ("block_floor", BLOCK_FLOOR),
                           ("fragmentation_ceiling", FRAG_CEILING),
                           ("continuation_floor", STACK_FLOOR)):
            require(integer(status, key) == value, "Resource floor changed: " + key)
        require(integer(status, "rejected_sample_count") == 0,
                "Rejected resource measurement in boot history")
        count = integer(status, "resource_sample_count", 1)
        stack = integer(status, "runtime_cont_stack_min", STACK_FLOOR, 4096)
        heap = integer(status, "lowest_heap", HEAP_FLOOR, 81920)
        block = integer(status, "lowest_block", BLOCK_FLOOR, 81920)
        frag = integer(status, "highest_fragmentation_percent", 0, FRAG_CEILING)
        require(block <= heap, "Largest free block cannot exceed free heap")
        for key in ("setup_cont_stack_start", "setup_cont_stack_min",
                    "fs_config_cont_stack_start", "fs_config_cont_stack_min",
                    "runtime_cont_stack_start"):
            value = integer(status, key, 0, 4096)
            require(value % 4 == 0 and value >= STACK_FLOOR,
                    "Invalid setup/FS/runtime stack window: " + key)
        require(stack % 4 == 0 and stack <= status["runtime_cont_stack_start"],
                "Invalid historical continuation watermark")
        require(status["setup_cont_stack_min"] <= status["setup_cont_stack_start"]
                and status["fs_config_cont_stack_min"] <= status["fs_config_cont_stack_start"],
                "Invalid setup/FS stack ordering")
        if prev is not None:
            require(count > prev["count"], "No fresh independent 1Hz observations")
            require(stack <= prev["stack"] and heap <= prev["heap"]
                    and block <= prev["block"] and frag >= prev["frag"],
                    "Historical watermarks were reset or repainted")
        else:
            first_count = count
        prev = dict(boot=boot, count=count, stack=stack, heap=heap,
                    block=block, frag=frag)
        last_count = count
        min_stack = min(stack, min_stack)
        min_heap = min(heap, min_heap)
        min_block = min(block, min_block)
        max_frag = max(frag, max_frag)
    require(last_count - first_count >= MIN_POLL_SPAN,
            "Insufficient 1Hz runtime window (<180 distinct poll intervals)")
    return dict(
        status="RESOURCE_TRANSCRIPT_REVIEWABLE_NOT_PHYSICAL_CERTIFICATION",
        observations=len(records),
        poll_span=last_count-first_count,
        min_free_cont_stack_bytes=min_stack,
        min_free_heap_bytes=min_heap,
        min_largest_free_block_bytes=min_block,
        max_fragmentation_percent=max_frag,
        compiled_frame_delta_is_not_native_proof=True,
        measurement_origin_not_cryptographically_attested=True,
        physical_qualification="HOLD",
        ota_authorized=False,
        device_contacts_by_this_tool=0,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = review(json.loads(args.input.read_text(encoding="utf-8")))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "RESOURCE_HOLD", "reason": str(exc),
                          "ota_authorized": False,
                          "device_contacts_by_this_tool": 0}))
        return 2
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
