#!/usr/bin/env python3
"""Phase L runner with Phase M bounded acquisition hotfix; audit by default.

No device operation is authorized by Phase L qualification. The transaction is
owned exclusively by the unchanged Phase K SingleAttempt/PinnedStubTransport.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import sys
import time

# -I removes the script directory. Use only this file's trusted sibling directory,
# never cwd, PYTHONPATH or an operator-supplied import directory.
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import m9_single_attempt_app_write as app
from m9_executor_preflight import check_hashes
from m9_stage1_readback_verify import regular_file
from m9_rtc_neutralization import LOCAL_PYTHON, LOCAL_PYTHON_SHA

ROOT = TOOLS.parent
PINS = TOOLS / 'm9_phase_l_sources.json'
STUB_AUDIT_ROOT = ROOT / 'research-local/m9-phase-c'
UNKNOWN = 'STOP — PHYSICAL FLASH STATE MAY BE UNKNOWN'
MAX_SYNC_ATTEMPTS = 5
SYNC_RETRY_DELAY = 0.05


class BoundedSyncReads:
    """Bound continuous noise as well as empty reads; never write/reset/reconnect."""
    def __init__(self, port):
        self.port = port
        self.deadline = time.monotonic() + 5
        self.remaining = 16384
        self.calls = 0

    def check(self, delay=0):
        left = self.deadline - time.monotonic()
        app.require(left > delay and self.remaining > 0 and self.calls < 256,
                    'Global ROM sync budget exhausted')
        return left

    def inWaiting(self):
        return min(self.port.inWaiting(), self.remaining)

    def read(self, size):
        left = self.check()
        self.port.timeout = min(0.1, left)
        self.calls += 1
        data = self.port.read(min(size, self.remaining))
        self.remaining -= len(data)
        return data


def fresh_sync(rom, port) -> None:
    from esptool.loader import slip_reader
    from esptool.util import FatalError
    # One budget shared by ALL attempts, including incomplete frames and delays.
    budget = BoundedSyncReads(port)
    normal_write_timeout = port.write_timeout
    for attempt in range(MAX_SYNC_ATTEMPTS):
        budget.check()
        # Win32 PurgeComm buffer operations, not GPIO/reset/control-line changes.
        port.reset_input_buffer()
        port.reset_output_buffer()
        port.write_timeout = min(0.1, budget.check())
        packets = slip_reader(budget, rom.trace)
        replies = []
        def fresh_replies():
            for packet in packets:
                app.require(len(packet) in (10, 12), 'Exact ROM sync reply required')
                response, op, size, value = struct.unpack('<BBHI', packet[:8])
                app.require(response == 1 and op == rom.ESP_CMDS['SYNC'] and size in (2, 4)
                            and len(packet) == 8 + size and packet[8:] == bytes(size),
                            'Unexpected ROM sync reply')
                # Collect the COMPLETE sequence. Pinned sync() applies all-zero
                # AND semantics; never reject an individual zero value here.
                replies.append(packet)
                yield packet
        rom._slip_reader = fresh_replies()
        try:
            rom.sync()  # Exactly one request + seven response-only commands.
        except FatalError:
            # Reviewed pre-stub sync retry only. SerialException, interruption,
            # malformed envelope, classification or exhausted budget is terminal.
            if attempt + 1 == MAX_SYNC_ATTEMPTS:
                raise
            budget.check(SYNC_RETRY_DELAY)
            time.sleep(SYNC_RETRY_DELAY)
            continue
        app.require(time.monotonic() < budget.deadline and len(replies) == 8,
                    'Complete SYNC sequence within global deadline required')
        values = [struct.unpack('<I', packet[4:8])[0] for packet in replies]
        app.require(rom.sync_stub_detected == all(value == 0 for value in values),
                    'Pinned stub classification disagrees with complete sequence')
        app.require(not rom.sync_stub_detected, 'Known pre-existing stub refused')
        # ROM/stub responses are documented as eight identical replies. Pinned
        # any-nonzero semantics alone is insufficient for a mixed sequence.
        app.require(all(packet == replies[0] for packet in replies), 'Mixed inconsistent SYNC replies')
        port.timeout = 1
        port.write_timeout = normal_write_timeout
        rom._slip_reader = slip_reader(port, rom.trace)
        return


def port_literal(value: str) -> str:
    app.require(re.fullmatch(r'COM[1-9][0-9]*', value, flags=re.ASCII) is not None,
                'Explicit strict COM-number literal required')
    return value


def interpreter_gate() -> None:
    app.require(sys.platform == 'win32' and sys.version_info[:2] == (3, 12),
                'Approved Windows Python 3.12.x required')
    exe = regular_file(Path(sys.executable))
    app.require(exe.resolve() == Path(LOCAL_PYTHON).resolve()
                and hashlib.sha256(exe.read_bytes()).hexdigest() == LOCAL_PYTHON_SHA,
                'Approved local interpreter path and binary identity required')


def serial_source_gate() -> dict:
    pins = json.loads(PINS.read_text(encoding='utf-8'))
    check_hashes(TOOLS, pins['executor_helpers_sha256_lf'])
    spec = importlib.util.find_spec('serial')
    app.require(spec is not None and spec.origin is not None, 'Pinned pyserial missing')
    root = Path(spec.origin).parent
    expected = pins['pyserial_files_sha256_lf']
    app.require({p.relative_to(root).as_posix() for p in root.rglob('*.py')} == set(expected),
                'Pyserial source inventory changed')
    check_hashes(root, expected)
    module = importlib.import_module('serial')  # Import only; no serial object created.
    app.require(module.VERSION == '3.5' and Path(module.__file__).resolve().parent == root.resolve(),
                'Loaded pyserial differs from checked package')
    return {'pyserial_version': '3.5', 'source_files_checked': len(expected),
            'dtr_rts_api_disabled_before_open': True, 'electrical_glitch_proof': False}


def preflight(args) -> dict:
    port_literal(args.port)
    app.require(args.owner_go is None or args.owner_go == app.GO_TEXT, 'Exact owner GO required')
    if args.execute:
        app.require(args.owner_go == app.GO_TEXT, 'All execution latches required')
    interpreter_gate()
    _, identity = app.candidate(args.candidate, args.expected_sha256)
    app.load_pinned_esptool(args.stub_audit_root)  # Includes K package/config/stub source pins.
    serial_source_gate()
    return {'status': 'AUDIT_PRINT_ONLY_NO_PORT_OPEN', 'candidate_sha256': app.FROZEN_SHA256,
            'candidate_bytes': app.FROZEN_BYTES, 'target': 0, 'rounded_end': app.ROUNDED_END,
            'candidate_identity_gate': identity['PHASE_K_FROZEN_CANDIDATE_IDENTITY_GATE'],
            'physical_authorization': False, 'serial_io': 0}


class Session:
    """One invocation, one port open attempt, one K executor, no re-entry."""
    def __init__(self):
        self.consumed = False
        self.open_attempted = False
        self.port = None

    def acquire(self, args):
        from serial.serialwin32 import Serial
        from esptool.targets.esp8266 import ESP8266ROM
        # port=None is essential: SerialBase initializes stored states true,
        # but cannot apply them until open. Set false while still closed.
        self.port = Serial(port=None, baudrate=115200, timeout=1, write_timeout=1,
                           xonxoff=False, rtscts=False, dsrdtr=False, exclusive=True)
        self.port.dtr = False
        self.port.rts = False
        self.port.port = args.port
        app.require(not self.port.is_open and self.port.dtr is False and self.port.rts is False,
                    'Disabled control states required before open')
        self.open_attempted = True  # Even an uncertain open failure is a conservative STOP.
        self.port.open()
        app.require(self.port.is_open and self.port.dtr is False and self.port.rts is False,
                    'Disabled control states required before traffic')
        rom = ESP8266ROM(self.port, baud=115200, trace_enabled=False)
        # Never connect()/detect_chip(): those paths include reset strategies.
        # At most five SYNC requests, one global budget, before any stub upload.
        fresh_sync(rom, self.port)
        app.require(type(rom) is ESP8266ROM and not rom.IS_STUB and not rom.sync_stub_detected,
                    'Fresh manually established ESP8266 ROM required')
        # K rechecks exact chip magic/4 MiB capacity before pinned v2 upload and Begin.
        return app.PinnedStubTransport(rom, args.stub_audit_root)

    def run(self, args) -> tuple[int, dict]:
        if self.consumed:
            return 1, {'status': 'STOP_SESSION_ALREADY_CONSUMED'}
        self.consumed = True
        result = None
        failed = False
        # Suppress upstream progress/error details, including port identifiers or
        # raw protocol/internal dumps. Emit only our allowlisted receipt afterward.
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = preflight(args)
                if args.execute:
                    result = app.SingleAttempt().write(
                        args.candidate, args.expected_sha256, lambda: self.acquire(args), args.owner_go)
                    result['reconnects_after_transaction_start'] = 0
                    result.update(target=0, rounded_extent='0x000000..0x061FFF')
        except (Exception, KeyboardInterrupt):
            failed = True
        finally:
            # Close only the host handle. Pinned Windows close restores timeouts,
            # cancels I/O and closes handles; no DTR/RTS call/reset/Finish cleanup.
            if self.port is not None:
                try:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        self.port.close()
                except (Exception, KeyboardInterrupt):
                    failed = True
        if failed:
            return 1, {'status': UNKNOWN if self.open_attempted else 'STOP_PREFLIGHT_NO_PORT_OPEN'}
        return 0, result


class Once(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        seen = getattr(namespace, '_seen', set())
        if self.dest in seen:
            parser.error('Repeated argument forbidden: ' + option_string)
        seen.add(self.dest)
        namespace._seen = seen
        setattr(namespace, self.dest, values)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    p.add_argument('--candidate', type=Path, required=True, action=Once)
    p.add_argument('--expected-sha256', required=True, action=Once)
    p.add_argument('--port', required=True, action=Once)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--owner-go', action=Once)
    p.add_argument('--stub-audit-root', type=Path, default=STUB_AUDIT_ROOT, action=Once)
    return p


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    code, report = Session().run(args)
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
