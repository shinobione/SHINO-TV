"""Issue #83: manual, read-only SmallTV firmware identity in SHINO LINK tray.

Reuses the B5 reviewed two-GET Digest transport and OS process lock; deliberately
does NOT call its release-specific/resource/OTA-admission validator. No POST, OTA,
scan, device mutation, silent poll, or automatic repeat. A receipt label is
displayed only for a *local, byte-verified* BIN+manifest pair.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import threading

from push_fsless_metrics import read_credentials, validate_host
from shino_b5_get_diagnostic import B5GetDiagnostic, DiagnosticStop, PATHS
from shino_update import inspect as inspect_release

ENDPOINT = "/api/v1/update/status"
assert ENDPOINT == PATHS[0]
LABEL = "Vérifier le firmware du SmallTV…"
HEX16 = re.compile(r"[0-9a-f]{16}\Z")
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SAFE_NAME = re.compile(r"[A-Za-z0-9À-ÿ _.+()/\-]{1,48}\Z")
SAFE_STATE = re.compile(r"[A-Z0-9_]{1,64}\Z")
REQUIRED = frozenset((
    "protocol", "descriptor", "device", "build_id", "sha256", "bytes",
    "boot_id", "nonce", "ota_enabled", "fs_ok", "last_update",
    "metrics_fresh", "heap", "block", "stack", "frag", "fs_files", "fs_bytes",
    "ota_heap_min", "ota_block_min", "ota_stack_min", "ota_frag_max",
))


def validate_identity(data):
    """Validate the exact known P0 status vocabulary; never use OTA floors."""
    if type(data) is not dict or set(data) != REQUIRED:
        raise DiagnosticStop("INVALID_SCHEMA")
    if data["protocol"] != "shino-http-ota-1":
        raise DiagnosticStop("INVALID_SCHEMA")
    for key, pattern in (("device", HEX16), ("build_id", HEX64),
                         ("sha256", HEX64), ("boot_id", HEX32), ("nonce", HEX32)):
        if type(data[key]) is not str or not pattern.fullmatch(data[key]):
            raise DiagnosticStop("INVALID_SCHEMA")
    expected = ("SHINO-HTTP-OTA-1|" + data["device"] + "|" +
                data["build_id"] + "|4m2m|APP_ONLY")
    if data["descriptor"] != expected:
        raise DiagnosticStop("INVALID_SCHEMA")
    for key in ("ota_enabled", "fs_ok", "metrics_fresh"):
        if type(data[key]) is not bool:
            raise DiagnosticStop("INVALID_SCHEMA")
    for key in ("bytes", "heap", "block", "stack", "frag", "fs_files",
                "fs_bytes", "ota_heap_min", "ota_block_min",
                "ota_stack_min", "ota_frag_max"):
        if type(data[key]) is not int or data[key] < 0:
            raise DiagnosticStop("INVALID_SCHEMA")
    if not 64000 <= data["bytes"] <= 0xFEFF0:
        raise DiagnosticStop("INVALID_SCHEMA")
    if data["block"] > data["heap"] or data["heap"] > 81920 or data["frag"] > 100 or data["stack"] > 8192:
        raise DiagnosticStop("INVALID_SCHEMA")
    if type(data["last_update"]) is not str or not SAFE_STATE.fullmatch(data["last_update"]):
        raise DiagnosticStop("INVALID_SCHEMA")
    # Deliberately no conclusion about OTA success from last_update or ota_enabled.
    return {key: data[key] for key in (
        "device", "build_id", "sha256", "bytes", "descriptor",
        "boot_id", "last_update", "ota_enabled", "fs_ok",
    )}


class IdentityOnlyReader(B5GetDiagnostic):
    """Shares strict reviewed HTTP/Digest, but has no release identity to assume.

    The private internal placeholders are ONLY constructor compatibility for
    B5GetDiagnostic; they are never compared to response identity and never
    used as a release receipt. Actual response fields are validated separately.
    """

    def __init__(self, host, password, **transport_options):
        placeholder = "UNBOUND_READ_ONLY_IDENTITY"
        super().__init__(
            {"device": placeholder, "digest_password": password},
            {"device": placeholder}, host=validate_host(host),
            **transport_options,
        )

    def validate(self, path, data):
        if path != ENDPOINT:
            raise DiagnosticStop("ENDPOINT_NOT_ALLOWED")
        return validate_identity(data)

    def identity(self):
        # The inherited GET is locked through response body/close, uses at
        # most anonymous 401 + ONE authenticated GET, and has 6s total budget.
        return self.get(ENDPOINT)


def local_ota_hold(directory):
    """Known local one-shot markers veto a new GET. Never remove any markers."""
    root = Path(directory)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        return True
    try:
        # Only the configured private LINK folder; another OTA executor may
        # store markers elsewhere. That limitation is documented, not hidden.
        return root.is_dir() and any(root.glob("*.attempt"))
    except OSError:
        return True


def matching_receipt(identity, path):
    """Trust no label unless its local exact BIN and manifest pass inspect()."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        return None
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"),
                             object_pairs_hook=_unique)
        if type(catalog) is not dict or set(catalog) != {"schema", "receipts"} or catalog["schema"] != 1:
            return None
        items = catalog["receipts"]
        if type(items) is not list or len(items) > 10:
            return None
        matches = []
        for item in items:
            if type(item) is not dict or set(item) != {"name", "bin", "manifest"}:
                return None
            label = item["name"]
            if type(label) is not str or not SAFE_NAME.fullmatch(label):
                return None
            for key in ("bin", "manifest"):
                if type(item[key]) is not str or not Path(item[key]).is_absolute():
                    return None
            release, _ = inspect_release(Path(item["bin"]), Path(item["manifest"]))
            if (all(identity[k] == release[k] for k in ("device", "build_id", "sha256", "bytes"))
                    and identity["descriptor"] == "SHINO-HTTP-OTA-1|" + release["device"] + "|" + release["build_id"] + "|4m2m|APP_ONLY"):
                matches.append(label)
        return matches[0] if len(matches) == 1 else None
    except (ValueError, TypeError, OSError, KeyError, UnicodeError):
        return None


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate local receipt field")
        out[key] = value
    return out


def read_firmware_identity(host, credentials, directory, *, reader_factory=IdentityOnlyReader,
                           now=None, local_guard=local_ota_hold):
    """One manual diagnostic only. No secret retained in returned UI model."""
    host = validate_host(host)
    directory = Path(directory)
    if local_guard(directory):
        return {"state": "HOLD", "message": "OTA locale en cours ou incertaine"}
    # Fresh private credentials at click time; engine sender is unaffected.
    _, password = read_credentials(Path(credentials))
    if local_guard(directory):
        return {"state": "HOLD", "message": "OTA locale en cours ou incertaine"}
    reader = reader_factory(host, password)
    identity = reader.identity()
    # Any local marker appearing during the exchange downgrades the result.
    if local_guard(directory):
        return {"state": "HOLD", "message": "OTA locale en cours ou incertaine"}
    label = matching_receipt(identity, directory/"firmware-receipts.json")
    clock = datetime.now().astimezone() if now is None else now
    if not isinstance(clock, datetime) or clock.tzinfo is None:
        raise ValueError("Local timestamp must have a timezone")
    return {
        "state": "READ",
        "version": label or "Version inconnue — identité lue",
        "build": identity["build_id"][:12],
        "sha": identity["sha256"][:12],
        "bytes": identity["bytes"],
        "checked": clock.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "ota": "activée (déclarée)" if identity["ota_enabled"] else "désactivée (déclarée)",
        "fs": "OK déclaré" if identity["fs_ok"] else "Non OK déclaré",
        "last_update": identity["last_update"],
        "receipt": label is not None,
    }


def safe_failure(exc):
    if isinstance(exc, DiagnosticStop):
        if exc.code in ("UNEXPECTED_HTTP_STATUS", "SECOND_401", "INVALID_DIGEST_CHALLENGE",
                        "UNAUTHENTICATED_200", "DIGEST_SEQUENCE_HOLD"):
            return "Authentification refusée / HTTP non accepté"
        if exc.code == "TIMEOUT":
            return "Délai de lecture dépassé"
        if exc.code in ("COORDINATOR_UNAVAILABLE", "CLIENT_BUSY"):
            return "HOLD : verrou Digest indisponible"
        if exc.code in ("CONNECTION_OR_HTTP_ERROR",):
            return "Appareil injoignable"
    return "Non disponible — diagnostic non confirmé"


class FirmwareMenuAction:
    """Exactly one manual worker; no polling or second telemetry sender."""
    def __init__(self, read_once):
        if not callable(read_once):
            raise TypeError("read_once must be callable")
        self._read_once = read_once
        self._lock = threading.Lock()
        self._closed = False
        self._busy = False
        self._result = {"state": "IDLE"}

    def snapshot(self):
        with self._lock:
            return dict(self._result)

    def close(self):
        with self._lock:
            self._closed = True

    def start(self, icon):
        with self._lock:
            if self._closed or self._busy:
                return False
            self._busy = True
            self._result = {"state": "READING"}
        self._refresh(icon)

        def task():
            try:
                outcome = self._read_once()
                if type(outcome) is not dict or outcome.get("state") not in ("READ", "HOLD"):
                    raise ValueError("Invalid read-only outcome")
            except Exception as error:
                outcome = {"state": "ERROR", "message": safe_failure(error)}
            with self._lock:
                self._busy = False
                if self._closed:
                    return
                self._result = outcome
            self._refresh(icon)
            if hasattr(icon, "notify"):
                try:
                    title = "Firmware SmallTV"
                    message = outcome.get("version", outcome.get("message", "Non disponible"))
                    icon.notify(message[:90], title)
                except (OSError, RuntimeError, AttributeError):
                    pass

        threading.Thread(target=task, name="SHINO-LINK-firmware-read",
                         daemon=True).start()
        return True

    @staticmethod
    def _refresh(icon):
        try:
            icon.update_menu()
        except (RuntimeError, AttributeError, OSError):
            pass

    def line(self, field):
        model = self.snapshot()
        state = model["state"]
        if state == "READING":
            return "Firmware : lecture en cours…"
        if state == "IDLE":
            return "Firmware : aucune lecture"
        if state != "READ":
            return "Firmware : " + model.get("message", "Non disponible")
        titles = {
            "version": "Firmware", "build": "Build ID", "sha": "SHA-256",
            "bytes": "Taille BIN", "checked": "Dernière lecture",
            "ota": "OTA", "fs": "LittleFS", "last_update": "Dernière OTA déclarée",
        }
        value = model.get(field)
        if field == "bytes":
            value = str(value) + " octets"
        return titles.get(field, field) + " : " + str(value)
