"""Preview a scene JSON or explicitly send it to a *custom SHINO-TV firmware*.

No network request unless BOTH --send and --confirm-custom-firmware are given.
This does not work with the owner's original GeekMagic Ultra-V9.0.44 firmware.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

FIELDS = {
    "metrics": {},
    "music": {"artist": 32, "track": 48, "progress": (0, 100)},
    "agent": {"status": 18, "task": 56, "progress": (0, 100)},
    "release": {"artist": 32, "track": 48, "days": (0, 9999)},
}


def validate_scene(value: object) -> dict:
    if not isinstance(value, dict) or type(value.get("kind")) is not str:
        raise ValueError("Scene must be an object with a string kind")
    kind = value["kind"]
    if kind not in FIELDS:
        raise ValueError("Unsupported kind")
    fields = FIELDS[kind]
    if set(value) != {"kind", *fields}:
        raise ValueError("Scene contains missing or unsupported fields for kind " + kind)
    for field, bounds in fields.items():
        candidate = value[field]
        if isinstance(bounds, int):
            if type(candidate) is not str or not 0 < len(candidate) <= bounds:
                raise ValueError(f"{field}: expected 1-{bounds} characters")
            if any(ord(char) < 32 or ord(char) > 126 for char in candidate):
                raise ValueError(f"{field}: printable ASCII only (font limitation)")
        else:
            lower, upper = bounds
            if type(candidate) is not int or not lower <= candidate <= upper:
                raise ValueError(f"{field}: integer must be in {lower}..{upper}")
    body = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(body) > 512:
        raise ValueError("Scene JSON exceeds 512-byte limit")
    return value


def device_endpoint(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if (parsed.scheme != "http" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Provide an HTTP base URL only, without credentials/path/query")
    try:
        addr = ipaddress.IPv4Address(parsed.hostname)
    except ipaddress.AddressValueError as exc:
        raise ValueError("Use a literal private LAN/loopback IPv4 address") from exc
    if not addr.is_private or addr.is_multicast or addr.is_unspecified:
        raise ValueError("No public, multicast or unspecified address is allowed")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid port")
    return base_url.rstrip("/") + "/api/v1/shino/scene"


def send_scene(base_url: str, token: str, scene: dict, opener=urllib.request.urlopen) -> dict:
    endpoint = device_endpoint(base_url)
    if not token or "\r" in token or "\n" in token:
        raise ValueError("Set a valid SHINO_TV_TOKEN environment variable")
    validate_scene(scene)
    body = json.dumps(scene, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    request = urllib.request.Request(
        endpoint, data=body, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with opener(request, timeout=3) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene_file", type=Path, help="Local JSON file for preview or optional send")
    parser.add_argument("--url", help="Actual custom firmware base URL, e.g. http://192.168.1.70")
    parser.add_argument("--send", action="store_true", help="Enable an actual HTTP POST")
    parser.add_argument("--confirm-custom-firmware", action="store_true",
                        help="Confirm factory Ultra firmware has already been replaced with SHINO-TV")
    args = parser.parse_args()
    scene = validate_scene(json.loads(args.scene_file.read_text(encoding="utf-8")))
    if not args.send:
        print(json.dumps(scene, indent=2))
        print("PREVIEW ONLY — no network request made")
        return
    if not args.confirm_custom_firmware:
        parser.error("Refusing network send without --confirm-custom-firmware")
    if not args.url:
        parser.error("--url is required for --send")
    result = send_scene(args.url, os.environ.get("SHINO_TV_TOKEN", ""), scene)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
