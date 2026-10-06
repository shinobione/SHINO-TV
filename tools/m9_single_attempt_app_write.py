#!/usr/bin/env python3
"""Phase K single-attempt executor core. CLI is LOCAL AUDIT/PRINT ONLY, no port option.

The adapter accepts an existing fresh ROM session ONLY under separate future
authorization. This module never opens/closes a port, connects, resets or retries.
Phase K executes only deterministic fake transports and local source audits.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import struct
from pathlib import Path
from m9_executor_preflight import check_configuration, check_hashes, inspect_sources, MANIFEST
from m9_stage1_readback_verify import candidate_bytes

FROZEN_BYTES = 411136
FROZEN_SHA256 = '2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835'
FLASH_BYTES = 0x400000
ROUNDED_END = 0x065000
BLOCK_BYTES = 4096
BLOCK_COUNT = 101
GO_TEXT = 'GO SINGLE ATTEMPT ' + FROZEN_SHA256


class WriteError(ValueError):
    """STOP; flash state may be uncertain. No recovery operation is implied."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WriteError(message)


def candidate(path: Path, expected_sha256: str) -> tuple[bytes, dict]:
    require(expected_sha256 == FROZEN_SHA256, 'External SHA must select the exact frozen J successor')
    data, report = candidate_bytes(path, expected_sha256)
    require(len(data) == FROZEN_BYTES and report['sector_rounded_write_extent'] == ROUNDED_END,
            'Exact frozen size/extent required')
    report.update(PHASE_K_FROZEN_CANDIDATE_IDENTITY_GATE='PASS/OFFLINE',
                  firmware_rebuilt=False, candidate_substituted=False)
    return data, report


def pinned_sources(stub_audit_root: Path) -> tuple[Path, dict]:
    # Reject versions/configuration before importing esptool; import itself opens no port.
    require(importlib.metadata.version('esptool') == '5.4.0', 'Only esptool 5.4.0 is qualified')
    require(importlib.metadata.version('esp-pylib') == '1.1.5', 'Only esp-pylib 1.1.5 is qualified')
    require(importlib.metadata.version('pyserial') == '3.5', 'Only pyserial 3.5 is qualified')
    check_configuration()
    spec = importlib.util.find_spec('esptool')
    require(spec is not None and spec.origin is not None, 'Pinned esptool missing')
    root = Path(spec.origin).parent
    report = inspect_sources(root)  # Existing exact 53-file package inventory/digests, includes v2 binary.
    pins = json.loads(MANIFEST.read_text(encoding='utf-8'))
    check_hashes(stub_audit_root, pins['upstream_stub_source_sha256'])
    report.update(stub_source_files_checked=7, block_payload_bytes=BLOCK_BYTES,
                  whole_write_attempts=1, flash_packet_attempts=1)
    return root, report


def load_pinned_esptool(stub_audit_root: Path):
    root, report = pinned_sources(stub_audit_root)
    module = importlib.import_module('esptool')
    require(module.__version__ == '5.4.0' and Path(module.__file__).resolve().parent == root.resolve(),
            'Loaded module differs from checked package')
    return module, report


class PinnedStubTransport:
    """Exact low-level API adapter: one check_command call per flash command.

    Does not call cmds.write_flash, flash_block, connect or any port lifecycle API.
    Unknown existing stub sessions are refused; v2 is freshly uploaded from pinned
    bytes to an already connected/qualified ESP8266 ROM, with no v1 fallback.
    """
    def __init__(self, rom, stub_audit_root: Path):
        module, self.source_report = load_pinned_esptool(stub_audit_root)
        from esptool.loader import StubFlasher
        from esptool.targets.esp8266 import ESP8266ROM, ESP8266StubLoader
        require(type(rom) is ESP8266ROM and rom.CHIP_NAME == 'ESP8266' and not rom.IS_STUB
                and not rom.sync_stub_detected, 'Fresh ESP8266 ROM session required; unknown stub refused')
        require(rom.read_reg(rom.CHIP_DETECT_MAGIC_REG_ADDR) == rom.MAGIC_VALUE,
                'Physical chip magic does not identify ESP8266')
        require((rom.flash_id(cache=False) >> 16) == 0x16, 'Exact 4 MiB JEDEC capacity required')
        # A private subclass prevents the package's [2,1] automatic fallback.
        class OnlyV2(StubFlasher):
            STUB_SUBDIRS = ['2']
            STUB_VERSION_EXPLICIT = True
        stub = OnlyV2(rom)
        require(not stub.plugin_segments, 'No stub plugins allowed')
        self.loader = rom.run_stub(stub)
        require(type(self.loader) is ESP8266StubLoader and self.loader.IS_STUB,
                'Exact freshly loaded ESP8266 v2 stub required')
        self.loader.flash_set_parameters(FLASH_BYTES)  # RAM SPI geometry, no header rewrite.
        require((self.loader.flash_id(cache=False) >> 16) == 0x16, 'Stub flash capacity changed')
        self.identity = ('ESP8266', 2, FLASH_BYTES)

    def begin(self) -> None:
        self.loader.check_command('single application begin', self.loader.ESP_CMDS['FLASH_BEGIN'],
                                  struct.pack('<IIIII', FROZEN_BYTES, BLOCK_COUNT, BLOCK_BYTES, 0, 0))

    def data(self, block: bytes, sequence: int) -> None:
        self.loader.check_command('single application data', self.loader.ESP_CMDS['FLASH_DATA'],
                                  struct.pack('<IIII', len(block), sequence, 0, 0) + block,
                                  self.loader.checksum(block))

    def finish(self) -> None:
        # Same no-reboot parameter as pinned flash_finish(reboot=False).
        self.loader.check_command('single application finish', self.loader.ESP_CMDS['FLASH_END'],
                                  struct.pack('<I', 1))

    def md5(self) -> str:
        return self.loader.flash_md5sum(0, FROZEN_BYTES)


class SingleAttempt:
    """One-shot session, including exceptions/interruption; no implicit recovery."""
    def __init__(self):
        self.consumed = False

    def write(self, path: Path, expected_sha256: str, transport_factory, owner_go: str) -> dict:
        require(not self.consumed, 'Session consumed: STOP; a second attempt is forbidden')
        self.consumed = True  # Latch even preflight failure; no hidden re-entry/recovery.
        require(owner_go == GO_TEXT, 'Separate exact-operation owner GO required')
        data, report = candidate(path, expected_sha256)  # All bytes retained before any contact.
        transport = transport_factory()  # Production adapter has no port-open/connect path.
        require(transport.identity == ('ESP8266', 2, FLASH_BYTES), 'Wrong chip/stub/flash: STOP before Begin')
        # Exceptions propagate without Finish, reconnect, repeated block or second Begin.
        transport.begin()
        for sequence in range(BLOCK_COUNT):
            block = data[sequence * BLOCK_BYTES:(sequence + 1) * BLOCK_BYTES]
            block += b'\xff' * (BLOCK_BYTES - len(block))
            transport.data(block, sequence)
        transport.finish()
        require(transport.md5() == hashlib.md5(data).hexdigest(), 'Post-write MD5 mismatch: STOP, no retry')
        return {'status': 'APPLICATION_TRANSACTION_ACKNOWLEDGED_FULL_POST_STILL_REQUIRED',
                'candidate_sha256': report['sha256'], 'candidate_bytes': len(data),
                'begin_count': 1, 'data_blocks': BLOCK_COUNT, 'finish_count': 1,
                'automatic_retries': 0, 'reconnects': 0, 'automatic_reboots': 0,
                'full_post_verified': False, 'physical_gate_closed_by_this_receipt': False}


def future_packet(resource_policy_gate: str, executor_gate: str) -> dict:
    require(resource_policy_gate == executor_gate == 'PASS/OFFLINE', 'Both offline prerequisites required')
    return {'scope': 'PRINT ONLY / NOT AUTHORIZED BY PHASE K', 'candidate_bytes': FROZEN_BYTES,
            'candidate_sha256': FROZEN_SHA256, 'target': 0, 'rounded_end': ROUNDED_END,
            'protected_interval': '0x065000..0x3FFFFF', 'physical_authorization': False,
            'steps': [
                'Fresh same-unit ESP8266 ROM/chip/4 MiB qualification; continuous power, GPIO0 LOW, isolated DTR/RTS',
                'Fresh private full 4 MiB PRE; PRE FS slice equals retained frozen Stage-2 bytes',
                'Rehash exact frozen J candidate; verify rollback captures/authority separately',
                'Explicit owner GO for exact image/hash/operation; not supplied by this Phase K packet',
                'SingleAttempt plus PinnedStubTransport only; same fresh ROM session, fresh pinned v2 stub; no stock write-flash CLI',
                'One uncompressed target-zero Begin / 101 data packets / Finish; keep GPIO0 LOW; no retry/reset/rollback',
                'Full independent 4 MiB POST before first app boot; exact candidate at zero',
                'POST[0x065000:0x400000] equals PRE continuously, including frozen FS and tail',
                'RTC 0/0 verified under continuous power; GPIO0 release and existing RST; normal application boot',
                'Digest status mount/inventory/config exact; zero blocked writes, enabled/valid advancing resource diagnostics',
                'Apply scoped thresholds to mount/post-probe/runtime fields, including old denser heap minimum',
                '180 s LINK, controlled stale/recovery, no reboot/display corruption; final status/monotone counters still pass',
                'No automatic retry/rollback; any exception, missing fact or ambiguity = STOP; full normal profile remains NOT_RUN'],
            'port_open_connect_reset_adapter': 'NOT IMPLEMENTED; any future integration separately reviewed/authorized'}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--stub-audit-root', type=Path, required=True)
    args = p.parse_args()
    try:
        _, image = candidate(args.candidate, args.expected_sha256)
        _, sources = load_pinned_esptool(args.stub_audit_root)
        from m9_resource_policy import policy
        report = {'PHASE_K_SINGLE_ATTEMPT_EXECUTOR_GATE': 'PASS/OFFLINE', 'image': image,
                  'sources': sources, 'future_packet': future_packet(policy()['PHASE_K_RESOURCE_POLICY_GATE'],
                      'PASS/OFFLINE'), 'physical_authorization': False,
                  'device_contacts': 0, 'serial_io': 0, 'flash_writes': 0, 'rtc_writes': 0,
                  'reboots': 0, 'device_filesystem_writes': 0}
        print(json.dumps(report, indent=2, sort_keys=True))
    except (ValueError, OSError, TypeError, ImportError) as exc:
        p.exit(1, 'EXECUTOR GATE CLOSED: ' + str(exc) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
