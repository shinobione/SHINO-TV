"""Mission 9 Phase R: offline by default; one future owner-only status GET."""
from __future__ import annotations

import json
from http.client import HTTPException
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPPasswordMgrWithDefaultRealm, ProxyHandler, Request, build_opener,
    parse_http_list, parse_keqv_list,
)

from push_fsless_metrics import NoRedirect, TelemetryDigestAuthHandler, validate_host

STATUS_PATH = "/api/v1/m9/normal/status"
REALM = "SHINO-StageA"
TIMEOUT = 3.0
MAX_STATUS_BYTES, MAX_ERROR_BYTES = 4096, 256
FLOORS = dict(heap_floor=20480, block_floor=16384,
              fragmentation_ceiling=25, continuation_floor=2048)
TRUE_FLAGS = ("normal_qualification", "digest_auth_required", "api_identity_ram_only",
              "autoformat_disabled")
FALSE_FLAGS = (
    "secure_storage_enabled", "eeprom_enabled", "rtc_writes_enabled",
    "sdk_wifi_persistence_enabled", "sta_enabled", "filesystem_writes_enabled",
    "static_fs_reads_enabled", "native_ota_writer_enabled", "media_ingress_enabled",
    "legacy_mutation_routes_enabled", "physical_authorization",
)
BOOL_FIELDS = ("config_loaded_readonly", "private_ap_ready", "mount_attempted",
               "mounted", "inventory_exact", "config_seed_exact",
               "resource_measurements_valid", "design_floors_observed")
INT_FIELDS = (
    "checked_file_count", "checked_payload_bytes", "blocked_write_attempts",
    "setup_cont_stack_min", "fs_config_cont_stack_min", "runtime_cont_stack_min",
    "lowest_heap", "lowest_block", "highest_fragmentation_percent",
    "resource_sample_count", "rejected_sample_count",
)
FAILURES = frozenset(("HTTP_401", "HTTP_403", "HTTP_OTHER", "REDIRECT_BLOCKED",
                     "UNEXPECTED_REALM", "MALFORMED_RESPONSE", "OVERSIZED_RESPONSE",
                     "TIMEOUT", "NETWORK_ERROR", "CONFIG_INVALID", "CLIENT_ERROR"))


class ProbeFailure(ValueError):
    def __init__(self, code):
        self.code = code if code in FAILURES else "CLIENT_ERROR"
        super().__init__(self.code)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProbeFailure("MALFORMED_RESPONSE")
        result[key] = value
    return result


def _reject_constant(_):
    raise ProbeFailure("MALFORMED_RESPONSE")


class OneGetDigest(TelemetryDigestAuthHandler):
    """Existing Digest proof machinery, closed realm and at most one auth retry."""
    def __init__(self, store, url):
        super().__init__(store, url)
        self.challenges = 0

    def http_error_401(self, req, fp, code, msg, headers):
        try:
            if (req.full_url != self.url or req.get_method() != "GET" or
                    self.challenges != 0):
                raise ProbeFailure("HTTP_401")
            values = headers.get_all("www-authenticate", [])
            if len(values) != 1 or len(values[0]) > 1024:
                raise ProbeFailure("HTTP_401")
            value = values[0]
            if not value.lower().startswith("digest "):
                raise ProbeFailure("HTTP_401")
            parts = parse_http_list(value[7:])
            keys = [p.partition("=")[0].strip().lower() for p in parts]
            if len(keys) != len(set(keys)):
                raise ProbeFailure("HTTP_401")
            challenge = parse_keqv_list(parts)
            if challenge.get("realm") != REALM:
                raise ProbeFailure("UNEXPECTED_REALM")
            if (not challenge.get("nonce") or challenge.get("qop") != "auth" or
                    challenge.get("algorithm", "MD5") != "MD5"):
                raise ProbeFailure("HTTP_401")
            self.challenges += 1
            return super().http_error_401(req, fp, code, msg, headers)
        finally:
            fp.close()


def make_opener(host, username, password):
    url = "http://" + validate_host(host) + STATUS_PATH
    store = HTTPPasswordMgrWithDefaultRealm()
    store.add_password(REALM, url, username, password)
    return build_opener(ProxyHandler({}), NoRedirect(), OneGetDigest(store, url))


def _bounded_body(response, limit):
    """Never read beyond the byte cap, including malformed/error responses."""
    lengths = response.headers.get_all("Content-Length", [])
    length = None
    if lengths:
        if (len(lengths) != 1 or not lengths[0].isascii() or
                not lengths[0].isdecimal() or len(lengths[0]) > 10):
            raise ProbeFailure("MALFORMED_RESPONSE")
        length = int(lengths[0])
        if length > limit:
            raise ProbeFailure("OVERSIZED_RESPONSE")
    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
        raise ProbeFailure("MALFORMED_RESPONSE")
    transfers = response.headers.get_all("Transfer-Encoding", [])
    if transfers and (length is not None or transfers != ["chunked"]):
        raise ProbeFailure("MALFORMED_RESPONSE")
    raw = response.read(limit if length is None else length)
    if (len(raw) > limit or (length is not None and len(raw) != length)):
        raise ProbeFailure("MALFORMED_RESPONSE")
    # Without declared length, reaching the cap is ambiguous: fail closed,
    # rather than read a cap+1 sentinel or accept a possibly truncated document.
    if length is None and len(raw) == limit:
        raise ProbeFailure("OVERSIZED_RESPONSE")
    return raw


def _document(response, limit):
    raw = _bounded_body(response, limit)
    if response.headers.get_content_type() != "application/json":
        raise ProbeFailure("MALFORMED_RESPONSE")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                              parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ProbeFailure("MALFORMED_RESPONSE") from None
    if type(document) is not dict:
        raise ProbeFailure("MALFORMED_RESPONSE")
    return document


def validate_status(document):
    if (document.get("mode") != "M9_NORMAL_STAGE_A" or
            type(document.get("boot_profile")) is not int or document["boot_profile"] != 1 or
            document.get("telemetry_storage") != "RAM_ONLY" or
            type(document.get("telemetry_ttl_ms")) is not int or document["telemetry_ttl_ms"] != 6000 or
            any(document.get(k) is not True for k in TRUE_FLAGS) or
            any(document.get(k) is not False for k in FALSE_FLAGS) or
            any(type(document.get(k)) is not int or document[k] != v for k, v in FLOORS.items()) or
            any(type(document.get(k)) is not bool for k in BOOL_FIELDS) or
            any(type(document.get(k)) is not int or not 0 <= document[k] <= 0xFFFFFFFF
                for k in INT_FIELDS)):
        raise ProbeFailure("MALFORMED_RESPONSE")
    d = document
    for key in ("setup_cont_stack_min", "fs_config_cont_stack_min", "runtime_cont_stack_min"):
        if d[key] > 4096 or d[key] % 4:
            raise ProbeFailure("MALFORMED_RESPONSE")
    if not (d["lowest_block"] <= d["lowest_heap"] <= 81920 and
            d["highest_fragmentation_percent"] <= 100 and
            d["checked_file_count"] <= 24 and d["checked_payload_bytes"] <= 181402):
        raise ProbeFailure("MALFORMED_RESPONSE")
    if ((d["inventory_exact"] and
         (d["checked_file_count"] != 24 or d["checked_payload_bytes"] != 181402)) or
            (d["config_seed_exact"] and not d["inventory_exact"]) or
            (d["resource_measurements_valid"] and
             (d["lowest_block"] == 0 or d["rejected_sample_count"] != 0))):
        raise ProbeFailure("MALFORMED_RESPONSE")
    numerical_pass = (d["resource_measurements_valid"] and d["resource_sample_count"] > 0 and
                      d["rejected_sample_count"] == 0 and d["lowest_heap"] >= 20480 and
                      d["lowest_block"] >= 16384 and d["highest_fragmentation_percent"] <= 25 and
                      all(d[k] >= 2048 for k in
                          ("setup_cont_stack_min", "fs_config_cont_stack_min", "runtime_cont_stack_min")))
    if d["design_floors_observed"] != bool(numerical_pass):
        raise ProbeFailure("MALFORMED_RESPONSE")
    # Strings/unknown keys never enter output, even if they contain hostile text.
    fields = {k: d[k] for k in (*BOOL_FIELDS, *INT_FIELDS)}
    return fields, "PASS" if numerical_pass else "HOLD"


def probe(host, opener):
    url = "http://" + validate_host(host) + STATUS_PATH
    request = Request(url, method="GET", headers={
        "Accept": "application/json", "Cache-Control": "no-store", "Connection": "close",
    })
    try:
        response = opener.open(request, timeout=TIMEOUT)
    except HTTPError as error:
        response = error
    with response:
        code = response.getcode()
        if code == 200:
            if not request.has_header("Authorization"):
                raise ProbeFailure("HTTP_401")
            return validate_status(_document(response, MAX_STATUS_BYTES))
        if code == 404:
            attribution = "404_UNATTRIBUTED"
            try:
                d = _document(response, MAX_ERROR_BYTES)
                if set(d) == {"error"} and d["error"] in ("STAGE_A_PREBODY", "STAGE_A_ROUTE_CLOSED"):
                    attribution = d["error"]
            except (ProbeFailure, TypeError):
                pass
            return attribution
        # Other error bodies are unnecessary for classification; never drain them.
        raise ProbeFailure({401: "HTTP_401", 403: "HTTP_403"}.get(
            code, "REDIRECT_BLOCKED" if 300 <= code < 400 else "HTTP_OTHER"))


def _private_probe():
    # Only the explicit future live branch calls these private loaders.
    from shino_link import load_config
    from push_fsless_metrics import read_credentials
    try:
        local = os.environ.get("LOCALAPPDATA", "")
        root = Path(local)
        if not local or not root.is_absolute() or ".." in root.parts:
            raise ValueError()
        config = load_config(root / "SHINO-TV" / "link.json")
        user, password = read_credentials(Path(config["credentials_file"]))
    except Exception:
        raise ProbeFailure("CONFIG_INVALID") from None
    return probe(config["host"], make_opener(config["host"], user, password))


def report_once(operation):
    """Fixed output only. No exception, HTTP header/body or private path output."""
    try:
        result = operation()
        if isinstance(result, str):
            code = result if result in ("STAGE_A_PREBODY", "STAGE_A_ROUTE_CLOSED") else "404_UNATTRIBUTED"
            print("STAGEA_STATUS_GET=HTTP_404 ERROR_CODE=" + code)
            return 1
        fields, floors = result
        print("STAGEA_STATUS_GET=HTTP_200 mode=M9_NORMAL_STAGE_A boot_profile=1")
        print(" ".join(k + "=" + (str(fields[k]).lower()) for k in (*BOOL_FIELDS, *INT_FIELDS)))
        print("RESOURCE_FLOORS=" + floors)
        print("NORMAL_PROFILE_RUNTIME_GATE=HOLD/PARTIAL")
        return 0
    except Exception as error:
        if isinstance(error, ProbeFailure):
            code = error.code
        elif isinstance(error, TimeoutError) or (isinstance(error, URLError) and isinstance(error.reason, TimeoutError)):
            code = "TIMEOUT"
        elif isinstance(error, (OSError, URLError)):
            code = "NETWORK_ERROR"
        elif isinstance(error, HTTPException):
            code = "MALFORMED_RESPONSE"
        else:
            code = "CLIENT_ERROR"
        print("STAGEA_STATUS_GET=" + code)
        return 1


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args in ([], ["--audit"]):
        print("OFFLINE_ONLY: no config/credentials, network or device access.")
        print("Future owner-only read: py -3 companion\\m9_stagea_status_probe.py --live")
        print("One GET cannot resolve the prior intermittent404; runtime HOLD/PARTIAL.")
        return 0
    if args == ["--live"]:
        return report_once(_private_probe)
    print("STAGEA_STATUS_GET=INVALID_ARGUMENTS")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
