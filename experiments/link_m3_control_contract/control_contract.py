"""M3-A: OFFLINE-ONLY proposed SHINO // LINK display control contract.

No socket, urllib, file, scheduler, secret or firmware import. This is not a
running firmware endpoint or an active Windows sender. Authentication here is
a *simulated upstream admission flag*, NOT a proof of ESP8266 Digest security.
Real deployment requires separate native pre-body authentication, heap/stack,
identity, nonce, scheduler and on-device scene qualifications.
"""

from dataclasses import dataclass
from enum import Enum
import ipaddress
import json
import re

PROTOCOL = "shino-display-control-1"  # PROPOSED; not B5.3 or B5.4 route
CAPABILITIES_GET = "/api/v1/display/capabilities"
STATUS_GET = "/api/v1/display/status"
MODE_POST = "/api/v1/display/mode"
COMMAND_MAX = 240
CAPABILITIES_MAX = 384
ACK_MAX = 256
STATUS_MAX = 384
MAX_REVISION = (1 << 32) - 1
_HEX16 = re.compile(r"[0-9a-f]{16}\Z")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")


class Mode(str, Enum):
    AUTO = "AUTO"
    CLOCK_WEATHER = "CLOCK_WEATHER"
    MONITORING = "MONITORING"
    MUSIC = "MUSIC"


class Scene(str, Enum):
    HYBRID = "HYBRID"
    CLOCK_WEATHER = "CLOCK_WEATHER"
    MONITORING = "MONITORING"
    MUSIC = "MUSIC"
    MONITORING_UNAVAILABLE = "MONITORING_UNAVAILABLE"
    NO_MEDIA = "NO_MEDIA"
    OFFLINE = "OFFLINE"


class State(str, Enum):
    CONFIRMED = "CONFIRMED"
    HOLD = "HOLD"
    REJECTED = "REJECTED"


class ContractError(ValueError):
    pass


class AdmissionDenied(ContractError):
    """Simulated authoritative refusal *before* command mutation."""


class LinkFailure(OSError):
    """Simulated transport failure, possibly after commit; outcome UNKNOWN."""


def _hex(value, pattern, name):
    if type(value) is not str or pattern.fullmatch(value) is None or not any(c != "0" for c in value):
        raise ContractError("INVALID_" + name)
    return value


def _rev(value, name):
    if type(value) is not int or not 0 <= value <= MAX_REVISION:
        raise ContractError("INVALID_" + name)
    return value


def _mode(value):
    if type(value) is not str:
        raise ContractError("INVALID_MODE")
    try:
        return Mode(value)
    except ValueError as exc:
        raise ContractError("INVALID_MODE") from exc


def _scene(value):
    if type(value) is not str:
        raise ContractError("INVALID_SCENE")
    try:
        return Scene(value)
    except ValueError as exc:
        raise ContractError("INVALID_SCENE") from exc


def _exact(obj, fields):
    if type(obj) is not dict or set(obj) != set(fields):
        raise ContractError("INVALID_FIELDS")
    return obj


def _pair_no_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ContractError("DUPLICATE_FIELD")
        obj[key] = value
    return obj


def _no_float(value):
    raise ContractError("INVALID_NUMBER")


def _decode(raw, maximum):
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise ContractError("INVALID_SIZE")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_pair_no_duplicates,
                         parse_float=_no_float, parse_constant=_no_float)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError("INVALID_JSON") from exc
    if type(obj) is not dict:
        raise ContractError("INVALID_FIELDS")
    return obj


def _encode(obj, maximum):
    _exact(obj, obj.keys())
    try:
        raw = json.dumps(obj, ensure_ascii=True, separators=(",", ":"),
                         sort_keys=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ContractError("INVALID_JSON") from exc
    if len(raw) > maximum:
        raise ContractError("INVALID_SIZE")
    return raw


@dataclass(frozen=True)
class Binding:
    """An externally VERIFIED owner target/boot binding; never auto-discovered."""

    host: str
    device: str
    boot: str

    def __post_init__(self):
        try:
            addr = ipaddress.IPv4Address(self.host)
        except (ipaddress.AddressValueError, ValueError, TypeError) as exc:
            raise ContractError("INVALID_HOST") from exc
        if (self.host != str(addr)
                or not any(addr in block for block in (
                    ipaddress.ip_network("10.0.0.0/8"),
                    ipaddress.ip_network("172.16.0.0/12"),
                    ipaddress.ip_network("192.168.0.0/16"))):
            raise ContractError("INVALID_HOST")
        _hex(self.device, _HEX16, "DEVICE")
        _hex(self.boot, _HEX32, "BOOT")


@dataclass(frozen=True)
class Outcome:
    state: State
    reason: str
    post_attempted: bool
    mode: Mode
    confirmed_scene: Scene | None = None

    # CONFIRMED means a valid ACK *AND* independent matching status readback.
    # Even CONFIRMED is SIMULATED in this module; not a physical LCD receipt.


def capabilities(raw):
    obj = _exact(_decode(raw, CAPABILITIES_MAX),
                 ("protocol", "device", "boot", "control", "modes", "max_command"))
    if obj["protocol"] != PROTOCOL or type(obj["control"]) is not bool:
        raise ContractError("INCOMPATIBLE_CAPABILITY")
    _hex(obj["device"], _HEX16, "DEVICE")
    _hex(obj["boot"], _HEX32, "BOOT")
    if (type(obj["modes"]) is not list
            or obj["modes"] != [mode.value for mode in Mode]
            or type(obj["max_command"]) is not int
            or obj["max_command"] != COMMAND_MAX):
        raise ContractError("INCOMPATIBLE_CAPABILITY")
    return obj


def status(raw):
    obj = _exact(_decode(raw, STATUS_MAX),
                 ("protocol", "device", "boot", "revision", "mode", "scene", "last_tx"))
    if obj["protocol"] != PROTOCOL:
        raise ContractError("INCOMPATIBLE_STATUS")
    _hex(obj["device"], _HEX16, "DEVICE")
    _hex(obj["boot"], _HEX32, "BOOT")
    _rev(obj["revision"], "REVISION")
    _mode(obj["mode"])
    _scene(obj["scene"])
    if obj["last_tx"] is not None:
        _hex(obj["last_tx"], _HEX32, "TRANSACTION")
    return obj


def command(mode, binding, revision, transaction):
    if type(mode) is not Mode or type(binding) is not Binding:
        raise ContractError("INVALID_COMMAND")
    _rev(revision, "REVISION")
    _hex(transaction, _HEX32, "TRANSACTION")
    obj = dict(protocol=PROTOCOL, device=binding.device, boot=binding.boot,
               revision=revision, mode=mode.value, tx=transaction)
    encoded = _encode(obj, COMMAND_MAX)
    parse_command(encoded)  # Same strict grammar for host and native lab.
    return encoded


def parse_command(raw):
    obj = _exact(_decode(raw, COMMAND_MAX),
                 ("protocol", "device", "boot", "revision", "mode", "tx"))
    if obj["protocol"] != PROTOCOL:
        raise ContractError("INCOMPATIBLE_COMMAND")
    _hex(obj["device"], _HEX16, "DEVICE")
    _hex(obj["boot"], _HEX32, "BOOT")
    _rev(obj["revision"], "REVISION")
    _mode(obj["mode"])
    _hex(obj["tx"], _HEX32, "TRANSACTION")
    return obj


def ack(raw):
    obj = _exact(_decode(raw, ACK_MAX),
                 ("protocol", "device", "boot", "revision", "mode", "tx", "accepted"))
    if obj["protocol"] != PROTOCOL or obj["accepted"] is not True:
        raise ContractError("INVALID_ACK")
    _hex(obj["device"], _HEX16, "DEVICE")
    _hex(obj["boot"], _HEX32, "BOOT")
    _rev(obj["revision"], "REVISION")
    _mode(obj["mode"])
    _hex(obj["tx"], _HEX32, "TRANSACTION")
    return obj


@dataclass(frozen=True)
class SimulatedAuth:
    """Not cryptography: only models a separately proven upstream native gate."""
    digest_verified: bool
    prebody_admitted: bool

    def __post_init__(self):
        if type(self.digest_verified) is not bool or type(self.prebody_admitted) is not bool:
            raise ContractError("INVALID_AUTH")


class FakeDevice:
    """Pure memory fake, not a firmware emulator or actual network endpoint."""

    def __init__(self, binding: Binding, *, auth: SimulatedAuth | None = None):
        if type(binding) is not Binding:
            raise ContractError("INVALID_BINDING")
        self.binding = binding
        self.auth = auth if auth is not None else SimulatedAuth(True, True)
        self.revision = 0
        self.mode = Mode.AUTO
        self.scene = Scene.OFFLINE
        self.last_tx = None
        self.last_request = None
        self.last_ack = None
        self.body_reads = 0
        self.commits = 0
        self.gets = 0

    def _authenticated(self):
        if not (type(self.auth) is SimulatedAuth
                and self.auth.digest_verified and self.auth.prebody_admitted):
            raise AdmissionDenied("SIMULATED_PREBODY_AUTH_REJECTED")

    def get_capabilities(self):
        self._authenticated()
        self.gets += 1
        return _encode(dict(protocol=PROTOCOL, device=self.binding.device,
                            boot=self.binding.boot, control=True,
                            modes=[m.value for m in Mode],
                            max_command=COMMAND_MAX), CAPABILITIES_MAX)

    def get_status(self):
        self._authenticated()
        self.gets += 1
        return _encode(dict(protocol=PROTOCOL, device=self.binding.device,
                            boot=self.binding.boot, revision=self.revision,
                            mode=self.mode.value, scene=self.scene.value,
                            last_tx=self.last_tx), STATUS_MAX)

    def post(self, raw):
        # Simulates the mandatory native order: authenticate BEFORE reading
        # any POST body. The real ESP8266 server's order is NOT yet proven.
        self._authenticated()
        self.body_reads += 1
        req = parse_command(raw)
        if req["device"] != self.binding.device or req["boot"] != self.binding.boot:
            raise AdmissionDenied("WRONG_DEVICE_OR_BOOT")
        if self.last_tx == req["tx"]:
            if raw != self.last_request:
                raise AdmissionDenied("CONFLICTING_TRANSACTION")
            return self.last_ack  # idempotent native response, no second commit
        if req["revision"] != self.revision:
            raise AdmissionDenied("STALE_REVISION")
        if self.revision == MAX_REVISION:
            raise AdmissionDenied("REVISION_EXHAUSTED")
        self.revision += 1
        self.mode = _mode(req["mode"])
        # A mode preference ACK is NOT a renderer-proof scene. The lab
        # deliberately sets an offline scene to force distinct status fields.
        self.scene = Scene.OFFLINE
        self.last_tx = req["tx"]
        self.last_request = raw
        self.commits += 1
        self.last_ack = _encode(dict(protocol=PROTOCOL, device=self.binding.device,
                                     boot=self.binding.boot, revision=self.revision,
                                     mode=self.mode.value, tx=req["tx"],
                                     accepted=True), ACK_MAX)
        return self.last_ack

    def reboot(self, fresh_boot):
        _hex(fresh_boot, _HEX32, "BOOT")
        if fresh_boot == self.binding.boot:
            raise ContractError("BOOT_MUST_CHANGE")
        self.binding = Binding(self.binding.host, self.binding.device, fresh_boot)
        self.revision = 0
        self.mode = Mode.AUTO
        self.scene = Scene.OFFLINE
        self.last_tx = self.last_request = self.last_ack = None


class LabTransport:
    """Hard offline restriction. No HTTP implementation or device discovery."""

    def __init__(self, device: FakeDevice):
        if type(device) is not FakeDevice:
            raise ContractError("LAB_DEVICE_REQUIRED")
        self.device = device
        self.host = device.binding.host
        self.posts = 0

    def get_capabilities(self):
        return self.device.get_capabilities()

    def get_status(self):
        return self.device.get_status()

    def post_mode(self, raw):
        self.posts += 1
        return self.device.post(raw)


class Session:
    """One explicit user intent; no automatic retry after any POST uncertainty."""

    def __init__(self, binding: Binding, transport: LabTransport):
        if type(binding) is not Binding or not isinstance(transport, LabTransport):
            raise ContractError("OFFLINE_SESSION_ONLY")
        if transport.host != binding.host:
            raise ContractError("HOST_MISMATCH")
        self.binding = binding
        self.transport = transport
        self.used = False
        self.last_outcome = None

    def _target(self, packet):
        return packet["device"] == self.binding.device and packet["boot"] == self.binding.boot

    def execute(self, mode: Mode, transaction: str):
        if self.used:
            raise ContractError("ONE_INTENT_PER_SESSION")
        if type(mode) is not Mode:
            raise ContractError("INVALID_MODE")
        _hex(transaction, _HEX32, "TRANSACTION")
        self.used = True
        posted = False

        def result(state, reason, scene=None):
            value = Outcome(state, reason, posted, mode, scene)
            self.last_outcome = value
            return value

        try:
            caps = capabilities(self.transport.get_capabilities())
            if not caps["control"] or not self._target(caps):
                return result(State.HOLD, "CAPABILITY_OR_BINDING")
            before = status(self.transport.get_status())
            if not self._target(before):
                return result(State.HOLD, "PRE_STATUS_BOOT_OR_DEVICE")
            if before["revision"] == MAX_REVISION:
                return result(State.REJECTED, "REVISION_EXHAUSTED")
            frame = command(mode, self.binding, before["revision"], transaction)
        except (ContractError, OSError, TimeoutError, RuntimeError):
            return result(State.HOLD, "PREFLIGHT_UNKNOWN")

        posted = True  # Set before invoking transport; even immediate failure is UNKNOWN.
        try:
            response = ack(self.transport.post_mode(frame))
            if (not self._target(response)
                    or response["mode"] != mode.value
                    or response["tx"] != transaction
                    or response["revision"] != before["revision"] + 1):
                return result(State.HOLD, "ACK_MISMATCH_OR_UNKNOWN")
            after = status(self.transport.get_status())
            if (not self._target(after)
                    or after["revision"] != response["revision"]
                    or after["mode"] != mode.value
                    or after["last_tx"] != transaction):
                return result(State.HOLD, "READBACK_MISMATCH_OR_UNKNOWN")
            return result(State.CONFIRMED, "ACK_AND_READBACK_SIMULATED",
                          _scene(after["scene"]))
        except AdmissionDenied:
            # A local lab model can guarantee pre-commit refusal. Real HTTP
            # 401/403 are NOT covered by this exception and remain uncertain.
            return result(State.REJECTED, "LAB_PRECOMMIT_REFUSAL")
        except (ContractError, OSError, TimeoutError, RuntimeError):
            return result(State.HOLD, "POST_OR_READBACK_UNKNOWN")

    def read_only_reconcile(self):
        """Post-fault observation never resends nor clears the one-intent latch."""
        if not self.used:
            raise ContractError("NO_PRIOR_INTENT")
        try:
            caps = capabilities(self.transport.get_capabilities())
            snapshot = status(self.transport.get_status())
        except (ContractError, OSError, TimeoutError, RuntimeError):
            return None
        return snapshot if caps["control"] and self._target(caps) and self._target(snapshot) else None
