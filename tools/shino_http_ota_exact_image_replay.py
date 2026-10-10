"""Offline replay of exact owner BIN through real ShinoHttpOta Transfer/Core.

Simulated 4 MiB flash + RTC, ephemeral fake maintenance credential, NO device
contact, UART, Wi-Fi, owner secrets, or network. This is NOT native memory
qualification and cannot authorize a hardware installation.
"""
import argparse
import hashlib
import json
import secrets
import tempfile
import sys
from pathlib import Path

from shino_wifi_runner import build, IO, ROOT

sys.path.insert(0, str(ROOT / "companion"))
from shino_update import inspect, signature


def replay(binary: Path, manifest: Path, expected_sha256: str):
    # Offline image and exact 4m2m segment/tag validation occurs before any
    # host lab is started. The actual BIN is never copied into the repository.
    m, raw = inspect(binary, manifest)
    if not isinstance(expected_sha256, str) or m["sha256"] != expected_sha256:
        raise ValueError("Exact expected release SHA-256 does not match")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Input BIN changed after inspection")

    # This key is synthetic and discarded immediately after the simulation.
    secret = secrets.token_hex(32)
    identity = {"device": m["device"], "maintenance_password": secret}
    nonce = "1" * 32
    with tempfile.TemporaryDirectory(prefix="shino-exact-core-replay-") as td:
        directory = Path(td)
        exe, env = build(directory, ROOT / "tools/shino_http_ota_lab.cpp")
        io = IO(exe, dict(env, SHINO_TEST_DEVICE=m["device"]), secret)
        try:
            if io.command("ALIGN_PROBE") != "ALIGN_OK":
                raise ValueError("Host flash model accepted a forbidden unaligned word read")
            tag = signature(identity, nonce, m)
            begin = f'BEGIN {len(raw)} {m["sha256"]} {m["build_id"]} {tag}'
            if io.command(begin) != "READY":
                raise ValueError("Core staging admission failed in offline replay")
            for at in range(0, len(raw), 512):
                block = raw[at:at + 512]
                io.write(block)
                if io.read() != f"ACK {at + len(block)}":
                    raise ValueError("Exact image rejected during simulated flash staging")
            if io.command("FINISH") != "STAGED":
                raise ValueError("Exact staged release did not pass CRC/segments/flash validation")
            report = io.report()
            if report["commit"] != 1 or not report["fs_preserved"] or report["received"] != len(raw):
                raise ValueError("Simulated eboot/FS/result acceptance failed")
        finally:
            io.close()
    return {
        "status": "EXACT_IMAGE_CORE_REPLAY_PASS_OFFLINE_ONLY",
        "sha256": expected_sha256,
        "bytes": len(raw),
        "flash_model": "4MiB_RAM_STRICT_4_BYTE_READ_ALIGNMENT",
        "core_flash_staged": True,
        "crc_segments_identity": "PASS",
        "simulated_eboot_command": True,
        "simulated_fs_preserved": True,
        "device_contact": 0,
        "physical_ota": "NOT_RUN",
        "native_stack_proven": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bin", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    args = p.parse_args()
    try:
        print(json.dumps(replay(args.bin, args.manifest, args.expected_sha256), indent=2))
        return 0
    except (ValueError, OSError, RuntimeError) as e:
        print("EXACT_IMAGE_CORE_REPLAY_HOLD: " + type(e).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
