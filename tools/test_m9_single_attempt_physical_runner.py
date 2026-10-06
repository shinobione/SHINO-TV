"""Real pinned ROM sync/SLIP/K flash API with fake serial only; no hardware."""
import ast
from contextlib import ExitStack
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch
import m9_single_attempt_physical_runner as runner
from test_m9_single_attempt_app_write import FIXTURE
from esptool.loader import slip_reader
from esptool.targets.esp8266 import ESP8266ROM, ESP8266StubLoader
from serial import SerialException


def slip(data):
    return b'\xc0' + data.replace(b'\xdb', b'\xdb\xdd').replace(b'\xc0', b'\xdb\xdc') + b'\xc0'


class SpySerial:
    def __init__(self, *, port, **settings):
        assert port is None
        assert settings['rtscts'] is False and settings['dsrdtr'] is False
        assert settings['xonxoff'] is False and settings['exclusive'] is True
        self.settings = settings
        self.is_open = False
        self._dtr = self._rts = True  # pyserial initial stored values, never applied.
        self.controls = []
        self.opens = self.closes = 0
        self.calls = []
        self.buffer = bytearray()
        self.fail = None
        self.error = TimeoutError
        self.stub_value = None
        self.bad_md5 = False
        self.sync_body = b'\0'*4  # Espressif ESP8266 ROM trace, not stub status fixture.
        self.timeout = 1
    @property
    def dtr(self): return self._dtr
    @dtr.setter
    def dtr(self, value):
        assert not self.is_open and value is False
        self.controls.append(('dtr', value, self.is_open)); self._dtr = value
    @property
    def rts(self): return self._rts
    @rts.setter
    def rts(self, value):
        assert not self.is_open and value is False
        self.controls.append(('rts', value, self.is_open)); self._rts = value
    def open(self):
        self.opens += 1
        assert self.opens == 1 and self.dtr is self.rts is False
        if self.fail == 'open': raise self.error('PRIVATE SERIAL DETAIL')
        self.is_open = True
    def close(self):
        self.closes += 1; self.is_open = False
        if self.fail == 'close': raise self.error('PRIVATE SERIAL DETAIL')
    def inWaiting(self): return len(self.buffer)
    def reset_input_buffer(self): self.buffer.clear()
    def reset_output_buffer(self): pass
    def read(self, size):
        if self.calls and self.calls[-1] == self.fail:
            raise self.error('PRIVATE SERIAL DETAIL')
        data = bytes(self.buffer[:size]); del self.buffer[:size]; return data
    def write(self, encoded):
        assert self.is_open and self.dtr is self.rts is False
        packet = encoded[1:-1].replace(b'\xdb\xdc', b'\xc0').replace(b'\xdb\xdd', b'\xdb')
        _, op, size, checksum = struct.unpack('<BBHI', packet[:8])
        data = packet[8:]; assert size == len(data)
        event = {8: 'sync', 2: 'begin', 4: 'finish', 0x13: 'md5'}.get(op)
        if op == 3:
            length, seq, zero1, zero2 = struct.unpack('<IIII', data[:16])
            assert length == 4096 and zero1 == zero2 == 0
            expected = FIXTURE[seq*4096:(seq+1)*4096]
            assert data[16:] == expected + b'\xff' * (4096-len(expected))
            event = ('data', seq)
        assert event is not None, 'Forbidden protocol operation'
        self.calls.append(event)  # Failure during read may follow successful transmission.
        if event == 'sync':
            assert data == b'\x07\x07\x12\x20' + 32*b'\x55'
            for i in range(8):
                value = 0 if self.stub_value == 'all' or self.stub_value == i else 0x20120707
                self.buffer.extend(slip(struct.pack('<BBHI', 1, op, len(self.sync_body), value)+self.sync_body))
        else:
            if event == 'begin': assert struct.unpack('<IIIII', data) == (411136, 101, 4096, 0, 0)
            if event == 'finish': assert struct.unpack('<I', data) == (1,)
            payload = (b'\0'*16 if self.bad_md5 else hashlib.md5(FIXTURE).digest()) if event == 'md5' else b''
            self.buffer.extend(slip(struct.pack('<BBHI', 1, op, len(payload)+2, 0)+payload+b'\0\0'))


class RunnerTests(unittest.TestCase):
    def args(self, execute=True, **changes):
        values = dict(candidate=Path('SYNTHETIC_ONLY_NOT_FIRMWARE'), expected_sha256=runner.app.FROZEN_SHA256,
                      port='COM8', execute=execute, owner_go=runner.app.GO_TEXT if execute else None,
                      stub_audit_root=Path('SOURCE_PINS_MOCKED_SEPARATELY'))
        values.update(changes); return types.SimpleNamespace(**values)

    def exercise(self, args=None, fail=None, error=TimeoutError, chip=True, capacity=True, stub_value=None,
                 stub_fail=False, bad_md5=False, preflight_fault=None, serial_class=SpySerial):
        ports=[]; uploads=[]
        def serial_factory(**kwargs):
            p=serial_class(**kwargs); p.fail=fail; p.error=error; p.stub_value=stub_value; p.bad_md5=bad_md5
            ports.append(p); return p
        def upload(rom, specification):
            uploads.append(specification)
            self.assertEqual(specification.STUB_SUBDIRS, ['2'])
            self.assertEqual(specification.plugin_segments, [])
            if stub_fail: raise error('PRIVATE STUB DETAIL')
            stub=ESP8266StubLoader.__new__(ESP8266StubLoader)
            stub._port=rom._port; stub._trace_enabled=False
            stub._slip_reader=slip_reader(stub._port, stub.trace)
            return stub
        with ExitStack() as stack:
            # Never instantiate a real serial backend, even on a Windows host.
            stack.enter_context(patch.dict(sys.modules, {'serial.serialwin32':types.SimpleNamespace(Serial=serial_factory)}))
            stack.enter_context(patch.object(runner, 'interpreter_gate'))
            stack.enter_context(patch.object(runner, 'serial_source_gate'))
            import esptool
            stack.enter_context(patch.object(runner.app, 'load_pinned_esptool', return_value=(esptool, {})))
            stack.enter_context(patch.object(runner.app, 'candidate', return_value=(FIXTURE,
                {'sha256':runner.app.FROZEN_SHA256, 'PHASE_K_FROZEN_CANDIDATE_IDENTITY_GATE':'PASS/OFFLINE'})))
            if preflight_fault:
                stack.enter_context(patch.object(runner, preflight_fault, side_effect=ValueError('PRIVATE PREFLIGHT DETAIL')))
            stack.enter_context(patch.object(ESP8266ROM, 'read_reg', return_value=ESP8266ROM.MAGIC_VALUE if chip else 0))
            stack.enter_context(patch.object(ESP8266ROM, 'flash_id', return_value=0x1640ef if capacity else 0x1540ef))
            stack.enter_context(patch.object(ESP8266ROM, 'run_stub', upload))
            stack.enter_context(patch.object(ESP8266StubLoader, 'flash_set_parameters'))
            original=runner.app.SingleAttempt
            once=stack.enter_context(patch.object(runner.app, 'SingleAttempt', wraps=original))
            s=runner.Session(); code, report=s.run(args or self.args())
            self.assertLessEqual(once.call_count, 1)
            self.assertEqual(s.run(args or self.args()), (1, {'status':'STOP_SESSION_ALREADY_CONSUMED'}))
            self.assertLessEqual(once.call_count, 1)
        self.assertLessEqual(len(ports), 1)
        for p in ports:
            self.assertLessEqual(p.opens, 1)
            self.assertEqual(p.closes, 1)
            self.assertEqual(p.controls, [('dtr', False, False), ('rts', False, False)])
            flash_calls=[event for event in p.calls if event != 'sync']
            self.assertEqual(len(flash_calls), len(set(flash_calls)))
            self.assertLessEqual(p.calls.count('sync'), runner.MAX_SYNC_ATTEMPTS)
            self.assertLessEqual(p.calls.count('begin'), 1)
        return code, report, ports, uploads

    def test_success_actual_sync_and_k_adapter_slip_101_packets(self):
        code, report, ports, uploads=self.exercise()
        self.assertEqual(code, 0)
        self.assertEqual(ports[0].calls, ['sync','begin']+[('data', i) for i in range(101)]+['finish','md5'])
        self.assertEqual(len(uploads), 1)
        self.assertEqual(report['status'], 'APPLICATION_TRANSACTION_ACKNOWLEDGED_FULL_POST_STILL_REQUIRED')
        self.assertEqual(report['target'], 0); self.assertEqual(report['rounded_extent'], '0x000000..0x064FFF')
        self.assertFalse(report['full_post_verified']); self.assertFalse(report['physical_gate_closed_by_this_receipt'])
        self.assertEqual(report['automatic_retries'], 0); self.assertEqual(report['automatic_reboots'], 0)

    def test_416_packet_faults_serial_timeout_interrupt_value_no_resend(self):
        events=['begin']+[('data',i) for i in range(101)]+['finish','md5']
        for error in (SerialException, TimeoutError, KeyboardInterrupt, ValueError):
            for event in events:
                with self.subTest(error=error.__name__, event=event):
                    code, report, ports, uploads=self.exercise(fail=event, error=error)
                    self.assertEqual(code, 1); self.assertEqual(report, {'status':runner.UNKNOWN})
                    p=ports[0]; self.assertEqual(p.calls[-1], event)
                    if event not in ('finish','md5'): self.assertNotIn('finish',p.calls)
                    if event != 'md5': self.assertNotIn('md5',p.calls)

    def test_open_sync_stub_upload_and_close_faults(self):
        for error in (SerialException, TimeoutError, KeyboardInterrupt):
            for event in ('open','sync','stub','close'):
                with self.subTest(error=error.__name__, event=event):
                    code, report, ports, uploads=self.exercise(fail=event, error=error, stub_fail=event=='stub')
                    self.assertEqual((code,report),(1,{'status':runner.UNKNOWN}))
                    if event != 'close': self.assertNotIn('begin',ports[0].calls)

    def test_wrong_chip_capacity_unknown_stub_stop_before_begin(self):
        for changes in ({'chip':False},{'capacity':False},{'stub_value':'all'},{'stub_value':0},{'stub_value':7}):
            with self.subTest(changes=changes):
                code, report, ports, uploads=self.exercise(**changes)
                self.assertEqual((code,report),(1,{'status':runner.UNKNOWN}))
                self.assertNotIn('begin',ports[0].calls); self.assertEqual(uploads,[])

    def test_md5_mismatch_has_one_finish_no_recovery(self):
        code, report, ports, _=self.exercise(bad_md5=True)
        self.assertEqual((code,report),(1,{'status':runner.UNKNOWN}))
        self.assertEqual(ports[0].calls[-2:], ['finish','md5'])

    def test_audit_missing_execute_never_constructs_serial_or_executor(self):
        code, report, ports, uploads=self.exercise(self.args(execute=False))
        self.assertEqual(code, 0); self.assertEqual(report['status'],'AUDIT_PRINT_ONLY_NO_PORT_OPEN')
        self.assertEqual((ports,uploads),([],[]))

    def test_wrong_go_and_bad_port_never_open(self):
        for args in [self.args(owner_go=None),self.args(owner_go='GO'),self.args(port='COM8,COM9'),
                     self.args(port='loop://'),self.args(port=''),self.args(port='com8')]:
            with self.subTest(args=args):
                code, report, ports, _=self.exercise(args)
                self.assertEqual((code,report),(1,{'status':'STOP_PREFLIGHT_NO_PORT_OPEN'})); self.assertEqual(ports,[])

    def test_interpreter_serial_source_package_and_hash_faults_before_open(self):
        for name in ('interpreter_gate','serial_source_gate'):
            code, report, ports, _=self.exercise(preflight_fault=name)
            self.assertEqual(code,1); self.assertEqual(ports,[])
        # Real K candidate/version guards, no mock bypass of wrong external hash.
        for mode in ('hash','esptool','esp-pylib','pyserial'):
            with ExitStack() as stack:
                stack.enter_context(patch.object(runner,'interpreter_gate'))
                stack.enter_context(patch.object(runner.Session,'acquire'))
                if mode=='hash': args=self.args(expected_sha256='0'*64)
                else:
                    args=self.args()
                    stack.enter_context(patch.object(runner.app,'candidate',return_value=(FIXTURE,{'PHASE_K_FROZEN_CANDIDATE_IDENTITY_GATE':'PASS/OFFLINE'})))
                    versions={'esptool':'5.4.0','esp-pylib':'1.1.5','pyserial':'3.5',mode:'WRONG'}
                    stack.enter_context(patch.object(importlib.metadata,'version',side_effect=versions.get))
                code, report=runner.Session().run(args)
                self.assertEqual(code,1); runner.Session.acquire.assert_not_called()

    def test_port_syntax_and_duplicate_no_abbreviations(self):
        for text in ('COM0','COM08','COM8 COM9','COM*','socket://host:1','rfc2217://host','C:\\COM8','\\\\.\\COM8','COM8\n','COM８'):
            with self.subTest(port=text), self.assertRaises(ValueError): runner.port_literal(text)
        self.assertEqual(runner.port_literal('COM8'),'COM8')
        base=['--candidate','synthetic','--expected-sha256',runner.app.FROZEN_SHA256,'--port','COM8']
        for extra in (['--port','COM9'],['--exec']):
            with patch('sys.stderr',io.StringIO()), self.assertRaises(SystemExit): runner.parser().parse_args(base+extra)

    def test_sync_noise_and_clock_budgets(self):
        class Noise:
            timeout=1
            def inWaiting(self): return 100000
            def read(self,size): return b'\0'*size
        port=Noise(); reads=runner.BoundedSyncReads(port)
        self.assertEqual(len(reads.read(100000)),16384)
        with self.assertRaises(ValueError): reads.read(1)
        reads=runner.BoundedSyncReads(port); reads.calls=256
        with self.assertRaises(ValueError): reads.read(1)
        reads=runner.BoundedSyncReads(port); reads.deadline=0
        with self.assertRaises(ValueError): reads.read(1)

    def test_real_pyserial_35_serialbase_closed_setters_no_control_updates(self):
        from serial.serialutil import SerialBase
        class Closed(SerialBase):
            def open(self): raise AssertionError('Cannot open hardware')
            def _update_dtr_state(self): raise AssertionError('Cannot toggle')
            def _update_rts_state(self): raise AssertionError('Cannot toggle')
        p=Closed(port=None,dsrdtr=False,rtscts=False)
        self.assertFalse(p.is_open); p.dtr=False; p.rts=False
        self.assertIs(p.dtr,False); self.assertIs(p.rts,False)

    def test_actual_serial_source_inventory_pins_and_mutation_rejected(self):
        report=runner.serial_source_gate()
        self.assertEqual(report['source_files_checked'],28)
        self.assertFalse(report['electrical_glitch_proof'])
        with patch.object(runner,'check_hashes',side_effect=ValueError('mutated')):
            with self.assertRaises(ValueError): runner.serial_source_gate()

    def test_approved_interpreter_gate_rejects_version_path_hash(self):
        with patch.object(runner.sys,'version_info',(3,13)), self.assertRaises(ValueError): runner.interpreter_gate()
        with patch.object(runner.sys,'platform','win32'),patch.object(runner.sys,'version_info',(3,12)),patch.object(runner.sys,'executable','UNAPPROVED'),self.assertRaises((ValueError,OSError)):
            runner.interpreter_gate()

    def test_no_reset_enumeration_recovery_readback_wrappers(self):
        tree=ast.parse(Path(runner.__file__).read_text(encoding='utf-8'))
        attrs={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
        self.assertFalse(attrs & {'connect','detect_chip','hard_reset','soft_reset','setDTR','setRTS','comports',
                                  'write_flash','flash_block','flash_defl_block','erase_flash','read_flash'})
        self.assertEqual(Path(runner.__file__).read_text().count('app.SingleAttempt()'),1)

    def test_cli_safe_failure_receipt_never_leaks_internal_exception(self):
        argv=['--candidate','synthetic','--expected-sha256',runner.app.FROZEN_SHA256,'--port','COM8']
        output=io.StringIO()
        with patch.object(runner.Session,'run',return_value=(1,{'status':runner.UNKNOWN})),patch('sys.stdout',output):
            self.assertEqual(runner.main(argv),1)
        self.assertIn(runner.UNKNOWN,output.getvalue())
        self.assertEqual(json.loads(output.getvalue()),{'status':runner.UNKNOWN})

    def test_rom_sync_status_forms_and_malformed_reply_stop(self):
        for body in (b'\0'*2,b'\0'*4,b'\0'*3,b'\1\0',b'\0\0\1\0'):
            p=SpySerial(port=None,xonxoff=False,rtscts=False,dsrdtr=False,exclusive=True)
            p.dtr=False; p.rts=False; p.port='COM8'; p.open(); p.sync_body=body
            rom=ESP8266ROM(p,baud=115200,trace_enabled=False)
            if body in (b'\0'*2,b'\0'*4): runner.fresh_sync(rom,p)
            else:
                with self.assertRaises(ValueError): runner.fresh_sync(rom,p)
            self.assertEqual(p.calls,['sync']); self.assertEqual(p.opens,1)
            self.assertEqual(p.controls,[('dtr',False,False),('rts',False,False)])
            p.close()


if __name__=='__main__': unittest.main()
