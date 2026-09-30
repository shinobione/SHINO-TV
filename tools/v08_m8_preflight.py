"""Mission 8 bounded GET-only preflight; no upload, reboot, or media request.

Offline hashes by default. --contact explicitly enables the known private AP.
Reports omit credentials, HTTP auth/cookie headers, AP secrets, and raw HTML.
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import (HTTPDigestAuthHandler, HTTPCookieProcessor,
                            HTTPPasswordMgrWithDefaultRealm, ProxyHandler,
                            Request, build_opener)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
from push_fsless_metrics import NoRedirect, read_credentials
from read_fsless_heap import validate_status
from verify_factory_ota import verify_archive

PARENT = "84129daa7359c73e738272b1c01131b3292dc315"
V21 = "8cef03012ae4a4864d69cbe20e02f141a36e2d54"
BASE = "http://192.168.4.1"
PATHS = ("/", "/api/v1/bridge/status", "/api/v1/bridge/metrics",
         "/api/v1/bridge/factory-return", "/api/v1/bridge/ota/capabilities")
PUBLIC_FIELDS = {
    "/api/v1/bridge/status": (
        "mode", "application_littlefs_begin_called", "application_autoformat_enabled",
        "application_eeprom_begin_called", "application_eeprom_commit_called",
        "sdk_wifi_persistence_enabled", "filesystem_provisioning_route",
        "browser_ui_source", "pc_metrics_storage", "filesystem_migration_writes_compiled",
        "physical_flash_bytes_observed_at_runtime", "running_application_bytes",
        "linker_declared_free_sketch_bytes_NOT_stock_OTA_capacity", "available_heap_bytes",
        "heap_observation", "factory_app_return_compiled", "native_ota_manager",
        "native_ota_writer_compiled", "physical_flash_installation_authorized",
        "physical_flash_or_application_OTA_writes_performed_by_diagnostics"),
    "/api/v1/bridge/metrics": (
        "mode", "received", "stale", "ttl_seconds", "cpu_usage", "gpu_usage",
        "memory_used_gb", "memory_total_gb", "memory_total_available", "schema_version",
        "gpu_vram_mb", "gpu_temp_c", "gpu_power", "gpu_available",
        "filesystem_or_eeprom_write_performed"),
    "/api/v1/bridge/factory-return": (
        "firmware", "application_bytes", "manufacturer_sha256", "full_flash_backup",
        "filesystem_layout_verified", "write_enabled"),
    "/api/v1/bridge/ota/capabilities": (
        "mode", "model", "physical_flash_bytes_observed_at_runtime",
        "running_application_bytes", "reported_free_sketch_bytes_NOT_INSTALL_APPROVAL",
        "linked_application_ceiling", "filesystem_write_or_migration_enabled",
        "native_ota_writer_compiled", "native_ota_upload_route_registered",
        "signature_verification_implemented", "physical_installation_authorized",
        "manufacturer_application_return_separate"),
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def get(opener, path):
    if path not in PATHS:
        raise ValueError("Unreviewed GET target")
    start = time.monotonic()
    request = Request(BASE + path, method="GET", headers={
        "Connection": "close", "Cache-Control": "no-store",
        "User-Agent": "SHINO-Mission8-GET-Preflight/1"})
    with opener.open(request, timeout=4) as response:
        raw = response.read(16385)
        if response.status != 200 or len(raw) > 16384:
            raise ValueError("Unexpected status or excessive response")
        info = {"utc": stamp(), "http_status": response.status,
                "response_bytes": len(raw),
                "round_trip_ms": round((time.monotonic() - start) * 1000, 3)}
        if path == "/":
            info["dashboard_html_present"] = b"SHINO" in raw
            return info, None
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise ValueError("Expected diagnostic object")
        info["data"] = {key: document[key] for key in PUBLIC_FIELDS[path] if key in document}
        if path.endswith("/status"):
            # Validate the complete known schema before exposing its nested data.
            validate_status(raw)
        return info, raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--manufacturer-zip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--contact", action="store_true")
    args = parser.parse_args()
    result = {"mission7_parent": PARENT, "started_utc": stamp(),
              "device_requests": [], "device_writes": 0, "media_requests": 0}
    try:
        manifest = json.loads((args.kit / "REVIEW-ONLY-MANIFEST.json").read_text())
        if manifest["source_commit"] != V21:
            raise ValueError("Kit is not frozen V2.1 review-003")
        result["known_good_source"] = V21
        result["artifacts"] = []
        for name, expected in manifest["files"].items():
            if not name.endswith(".bin"):
                continue
            path = args.kit / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Rollback file missing or symlink")
            data = path.read_bytes()
            actual = {"path": str(path), "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest()}
            if actual["bytes"] != expected["bytes"] or actual["sha256"] != expected["sha256"]:
                raise ValueError("Retained rollback does not match manifest")
            result["artifacts"].append(actual)
        if len(result["artifacts"]) != 2:
            raise ValueError("Both retained application images required")
        result["manufacturer_zip"] = verify_archive(args.manufacturer_zip,
            Path(__file__).resolve().parents[1] / "recovery/factory_ota_v9_0_44.json")
        result["offline_artifact_gate"] = "PASS"
        if args.contact:
            user, password = read_credentials(args.kit / "credentials.txt")
            passwords = HTTPPasswordMgrWithDefaultRealm()
            passwords.add_password("SHINO-FirstBoot", BASE + "/", user, password)
            opener = build_opener(ProxyHandler({}), NoRedirect(),
                HTTPDigestAuthHandler(passwords), HTTPCookieProcessor(CookieJar()))
            for path in PATHS:
                info, raw = get(opener, path)
                info["path"] = path
                result["device_requests"].append(info)
                if path.endswith("/status"):
                    validate_status(raw)
                    if info["data"]["running_application_bytes"] != 405712:
                        raise ValueError("Installed size differs from review-003: STOP")
                if path.endswith("/factory-return"):
                    doc = info["data"]
                    if (doc.get("write_enabled") is not True or
                        doc.get("application_bytes") != 494144 or
                        doc.get("manufacturer_sha256") !=
                        "a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718"):
                        raise ValueError("OEM recovery identity/capability mismatch: STOP")
            time.sleep(5)
            info, _ = get(opener, "/api/v1/bridge/metrics")
            info["path"] = "/api/v1/bridge/metrics"
            result["device_requests"].append(info)
            result["device_read_gate"] = "READS_COMPLETE__REVIEW_REQUIRED"
    except Exception as error:
        # Do not print exceptions that can contain URLs, credentials or bodies.
        result["failure_type"] = type(error).__name__
        result["gate"] = "STOP__PREFLIGHT_INCOMPLETE_OR_MISMATCH"
    result["ended_utc"] = stamp()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if "failure_type" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
