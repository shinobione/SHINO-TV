"""Source-grounded HOST-ONLY general JSON decoding fixture for PC telemetry.

Unlike the two-literal localhost C++ fixture, accepts arbitrary valid UTF-8
JSON bytes with Python's standard JSON parser. This is NOT ArduinoJson on the
ESP8266, a real Digest authenticator, native dashboard/LCD, owner secrets,
a live device server, a firmware writer or install permission. An independent
real ArduinoJson-on-host crosscheck remains necessary before port-80 cutover.
"""
from dataclasses import dataclass, replace
import json
import math
import struct

RANGES = {
    "cpu_usage": (0.0, 100.0),
    "gpu_usage": (0.0, 100.0),
    "memory_used_gb": (0.0, 256.0),
    "gpu_vram_mb": (0.0, 65536.0),
    "gpu_temp_c": (-40.0, 130.0),
    "gpu_power": (0.0, 1200.0),
}
INVALID_LENGTH = '{"error":"Invalid bounded telemetry payload length"}'
INVALID_JSON = '{"error":"Invalid JSON telemetry"}'
INVALID_VALUES = '{"error":"Invalid, missing or out-of-range telemetry fields"}'
ACCEPTED = '{"status":"RAM_SAMPLE_ACCEPTED","persisted":false}'


@dataclass(frozen=True)
class HostRamSample:
    received: bool = False
    cpu_usage: float = 0.0
    gpu_usage: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    gpu_vram_mb: float = 0.0
    gpu_temp_c: float = 0.0
    gpu_power: float = 0.0
    gpu_available: bool = False
    last_received_ms: int = 0


@dataclass(frozen=True)
class HostResponsePreview:
    status: int
    body: str
    device_write_performed: bool = False
    actual_digest_checked: bool = False
    actual_lcd_repainted: bool = False


def _float32_numeric(source, low, high):
    # Mirror FslessMetrics::bounded: ArduinoJson requires a numeric variant,
    # then source takes value.as<float>() BEFORE finite/range checks. Python
    # bool subclasses int and must be excluded explicitly.
    if type(source) not in (int, float):
        raise ValueError("not a JSON number")
    try:
        converted = struct.unpack("<f", struct.pack("<f", source))[0]
    except (OverflowError, struct.error):
        raise ValueError("outside float32")
    if not math.isfinite(converted) or not low <= converted <= high:
        raise ValueError("outside numeric bounds")
    return converted


def _reject_non_json_constant(value):
    raise ValueError("non-JSON token: "+value)


class HostTelemetryJsonOracle:
    """Independent host RAM fixture; deliberately not connected to server."""
    def __init__(self):
        self._sample = HostRamSample()

    @property
    def sample(self):
        return self._sample

    def stale(self, now_ms):
        return (not self._sample.received or
                ((now_ms - self._sample.last_received_ms) & 0xFFFFFFFF) > 6000)

    def preview_authenticated_post(self, raw, now_ms):
        # Called ONLY after a separate simulated Digest fixture has passed;
        # this method does not inspect or trust Authorization/Cookie headers.
        if not isinstance(raw, bytes) or not 16 <= len(raw) <= 384:
            return HostResponsePreview(413, INVALID_LENGTH)
        try:
            parsed = json.loads(
                raw.decode("utf-8", errors="strict"),
                parse_constant=_reject_non_json_constant)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return HostResponsePreview(422, INVALID_JSON)
        if (type(parsed) is not dict or
            type(parsed.get("ok")) is not bool or not parsed["ok"] or
            type(parsed.get("gpu_available")) is not bool):
            return HostResponsePreview(422, INVALID_VALUES)
        try:
            values = {
                name: _float32_numeric(parsed.get(name), *bounds)
                for name, bounds in RANGES.items()
            }
            total = parsed.get("memory_total_gb")
            total_gb = 0.0 if total is None else _float32_numeric(total, 0.01, 256.0)
            if total is not None and values["memory_used_gb"] > total_gb:
                raise ValueError("RAM used exceeds installed total")
        except ValueError:
            return HostResponsePreview(422, INVALID_VALUES)
        # All-or-nothing replacement of host fixture RAM, never physical RAM.
        self._sample = HostRamSample(
            received=True, memory_total_gb=total_gb,
            gpu_available=parsed["gpu_available"],
            last_received_ms=now_ms & 0xFFFFFFFF, **values)
        return HostResponsePreview(200, ACCEPTED)
