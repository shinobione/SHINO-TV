"""Fake application transport and real pinned esptool command paths; no hardware."""
import ast
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch
import m9_single_attempt_app_write as app

FIXTURE = bytes((i % 251 for i in range(app.FROZEN_BYTES)))  # Not an ESP image or physical candidate.


class FakeTransport:
    identity=('ESP8266',2,0x400000)
    def __init__(self, fail=None, error=TimeoutError):
        self.fail=fail; self.error=error; self.calls=[]
        self.flash=bytearray(b'\xff'*app.ROUNDED_END);self.offset=0;self.remaining=app.FROZEN_BYTES
    def event(self,event):
        self.calls.append(event)
        if event==self.fail:raise self.error('synthetic uncertain fault')
    def begin(self):self.event('begin')
    def data(self,block,sequence):
        if len(block)!=4096:raise ValueError('block size')
        expected=FIXTURE[sequence*4096:(sequence+1)*4096]
        if block!=expected+b'\xff'*(4096-len(expected)):raise ValueError('payload/padding changed')
        # Pinned v2 clamps to remaining bytes. Simulate uncertain ACK after programming:
        # a failure cannot be treated as proof that nothing was written.
        size=min(len(block),self.remaining)
        self.flash[self.offset:self.offset+size]=block[:size]
        self.offset+=size;self.remaining-=size
        self.event(('data',sequence))
    def finish(self):
        if self.remaining:raise ValueError('incomplete synthetic write')
        self.event('finish')
    def md5(self):self.event('md5');return hashlib.md5(self.flash[:app.FROZEN_BYTES]).hexdigest()


class ExecutorTests(unittest.TestCase):
    def run_fixture(self,t,session=None):
        session=session or app.SingleAttempt()
        with patch.object(app,'candidate',return_value=(FIXTURE,{'sha256':app.FROZEN_SHA256})):
            return session.write(Path('SYNTHETIC_ONLY'),app.FROZEN_SHA256,lambda:t,app.GO_TEXT)

    def test_success_one_begin_101_unique_blocks_one_finish(self):
        t=FakeTransport();r=self.run_fixture(t)
        self.assertEqual(t.calls,['begin']+[('data',i) for i in range(101)]+['finish','md5'])
        self.assertEqual(r['automatic_retries'],0)
        self.assertFalse(r['full_post_verified'])
        self.assertEqual(t.offset,411136);self.assertEqual(t.flash[:411136],FIXTURE)
        self.assertEqual(t.flash[411136:],b'\xff'*(413696-411136))

    def test_fail_before_begin_has_no_data_and_no_second_attempt(self):
        session=app.SingleAttempt();calls=[]
        def fail():calls.append('factory');raise OSError('synthetic disconnect before begin')
        with patch.object(app,'candidate',return_value=(FIXTURE,{})),self.assertRaises(OSError):
            session.write(Path('synthetic'),app.FROZEN_SHA256,fail,app.GO_TEXT)
        with self.assertRaises(app.WriteError):session.write(Path('synthetic'),app.FROZEN_SHA256,fail,app.GO_TEXT)
        self.assertEqual(calls,['factory'])

    def test_failure_matrix_no_repeated_begin_block_finish_or_reconnect(self):
        # Every block boundary plus Begin/Finish/MD5: exceptions include disconnect and timeout.
        for error in (TimeoutError,OSError,ValueError,KeyboardInterrupt):
            for event in ['begin']+[('data',i) for i in range(101)]+['finish','md5']:
                t=FakeTransport(event,error);session=app.SingleAttempt()
                with self.subTest(error=error.__name__,event=event),self.assertRaises(error):self.run_fixture(t,session)
                self.assertEqual(t.calls.count('begin'),1)
                self.assertEqual(t.calls.count(event),1)
                if event!='md5':self.assertNotIn('md5',t.calls)
                if event not in ('finish','md5'):self.assertNotIn('finish',t.calls)
                with self.assertRaises(app.WriteError):self.run_fixture(t,session)

    def test_hash_and_size_fail_before_factory_contact(self):
        contacts=[]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'synthetic.bin';p.write_bytes(FIXTURE)
            for expected in ('0'*64,app.FROZEN_SHA256):
                with self.subTest(expected=expected),self.assertRaises(ValueError):
                    app.SingleAttempt().write(p,expected,lambda:contacts.append(1),app.GO_TEXT)
            p.write_bytes(b'wrong size')
            with self.assertRaises(ValueError):app.SingleAttempt().write(p,app.FROZEN_SHA256,lambda:contacts.append(1),app.GO_TEXT)
        self.assertEqual(contacts,[])

    def test_identity_and_external_go_fail_before_write(self):
        for ident in [('ESP32',2,0x400000),('ESP8266',1,0x400000),('ESP8266',2,0x200000)]:
            t=FakeTransport();t.identity=ident
            with self.subTest(identity=ident),self.assertRaises(app.WriteError):self.run_fixture(t)
            self.assertEqual(t.calls,[])
        contacts=[]
        with self.assertRaises(app.WriteError):app.SingleAttempt().write(Path('missing'),app.FROZEN_SHA256,lambda:contacts.append(1),'GO')
        self.assertEqual(contacts,[])

    def test_md5_mismatch_stop_no_second_transaction(self):
        t=FakeTransport();t.md5=lambda:'0'*32
        with self.assertRaises(app.WriteError):self.run_fixture(t)
        self.assertEqual(t.calls.count('begin'),1);self.assertEqual(t.calls.count('finish'),1)

    def test_exact_size_check_independent_of_digest(self):
        with patch.object(app,'candidate_bytes',return_value=(b'x',{'sector_rounded_write_extent':app.ROUNDED_END})):
            with self.assertRaises(app.WriteError):app.candidate(Path('synthetic'),app.FROZEN_SHA256)

    def test_regular_file_and_external_hash_fail_before_contact(self):
        from m9_stage1_readback_verify import ReadbackError
        contacts=[]
        with patch.object(app,'candidate_bytes',side_effect=ReadbackError('non-regular/hash mismatch')):
            with self.assertRaises(ReadbackError):app.SingleAttempt().write(Path('synthetic'),app.FROZEN_SHA256,lambda:contacts.append(1),app.GO_TEXT)
        self.assertEqual(contacts,[])

    def test_wrong_versions_before_import_or_contact(self):
        expected={'esptool':'5.4.0','esp-pylib':'1.1.5','pyserial':'3.5'}
        for name in expected:
            observed={**expected,name:'UNQUALIFIED'}
            with self.subTest(package=name),patch.object(app.importlib.metadata,'version',side_effect=observed.get),patch.object(app.importlib,'import_module') as imp:
                with self.assertRaises(app.WriteError):app.load_pinned_esptool(Path('synthetic'))
                imp.assert_not_called()

    def test_source_pin_and_configuration_fault_before_import(self):
        for name in ('check_configuration','inspect_sources','check_hashes'):
            with self.subTest(gate=name),patch.object(app,name,side_effect=ValueError('mutated source/config')),patch.object(app.importlib,'import_module') as imp:
                with self.assertRaises(ValueError):app.load_pinned_esptool(Path('synthetic'))
                imp.assert_not_called()

    def test_no_port_cli_and_no_retry_wrappers(self):
        tree=ast.parse(Path(app.__file__).read_text())
        attrs={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        self.assertFalse(attrs & {'write_flash','flash_block','flash_defl_block','connect','open','close','hard_reset','soft_reset','erase_flash'})
        text=Path(app.__file__).read_text()
        self.assertNotIn("add_argument('--port'",text)
        self.assertNotIn('import serial',text)
        self.assertIn("STUB_SUBDIRS = ['2']",text)

    def test_future_packet_requires_both_gates_and_no_authority(self):
        for a,b in [('HOLD','PASS/OFFLINE'),('PASS/OFFLINE','HOLD')]:
            with self.assertRaises(app.WriteError):app.future_packet(a,b)
        r=app.future_packet('PASS/OFFLINE','PASS/OFFLINE')
        self.assertFalse(r['physical_authorization']);self.assertEqual(r['rounded_end'],0x65000)


class PinnedCommandTests(unittest.TestCase):
    def setUp(self):
        # Real pinned Python package + command/check_command/SLIP write. Fake serial object only.
        import importlib.metadata
        self.assertEqual(importlib.metadata.version('esptool'),'5.4.0')
        from esptool.targets.esp8266 import ESP8266StubLoader
        self.loader=ESP8266StubLoader.__new__(ESP8266StubLoader)
        class Port:
            timeout=3
            def __init__(self):self.writes=[]
            def write(self,data):self.writes.append(data)
        self.port=Port();self.loader._port=self.port;self.loader._trace_enabled=False
        self.transport=app.PinnedStubTransport.__new__(app.PinnedStubTransport)
        self.transport.loader=self.loader

    def responses(self,op,failure=None):
        from esptool.util import FatalError
        def packets():
            if failure:raise failure('synthetic wire fault after request')
            yield struct.pack('<BBHI',1,op,2,0)+b'\x00\x00'
            raise FatalError('unexpected second read')
        self.loader._slip_reader=packets()

    def test_actual_adapter_one_packet_per_command(self):
        for op,invoke in [(2,self.transport.begin),(3,lambda:self.transport.data(b'x'*4096,0)),(4,self.transport.finish)]:
            self.responses(op);before=len(self.port.writes);invoke()
            self.assertEqual(len(self.port.writes),before+1)
        # Decode SLIP payload to assert no-compression Begin and no-reboot Finish.
        decode=lambda p:p[1:-1].replace(b'\xdb\xdc',b'\xc0').replace(b'\xdb\xdd',b'\xdb')
        begin=decode(self.port.writes[0]);finish=decode(self.port.writes[-1])
        self.assertEqual(struct.unpack('<IIIII',begin[8:]),(411136,101,4096,0,0))
        self.assertEqual(struct.unpack('<I',finish[8:]),(1,))

    def test_actual_api_fatal_serial_timeout_never_resends(self):
        from esptool.util import FatalError
        from serial import SerialException
        for error in (FatalError,SerialException,TimeoutError):
            for op,invoke in [(2,self.transport.begin),(3,lambda:self.transport.data(b'x'*4096,5)),(4,self.transport.finish)]:
                self.responses(op,error);before=len(self.port.writes)
                with self.subTest(error=error.__name__,op=op),self.assertRaises(error):invoke()
                self.assertEqual(len(self.port.writes),before+1)

    def test_bad_status_and_extra_response_reads_do_not_resend(self):
        from esptool.util import FatalError
        self.loader._slip_reader=iter([struct.pack('<BBHI',1,2,2,0)+b'\x01\x01'])
        with self.assertRaises(FatalError):self.transport.begin()
        self.assertEqual(len(self.port.writes),1)
        wrong=struct.pack('<BBHI',1,8,2,0)+b'\x00\x00'
        good=struct.pack('<BBHI',1,3,2,0)+b'\x00\x00'
        self.loader._slip_reader=iter([wrong]*3+[good])
        self.transport.data(b'x'*4096,6)
        self.assertEqual(len(self.port.writes),2)

    def test_fresh_rom_adapter_chip_capacity_and_stub_version_guards(self):
        from esptool.targets.esp8266 import ESP8266ROM,ESP8266StubLoader
        import esptool
        rom=ESP8266ROM.__new__(ESP8266ROM);rom.sync_stub_detected=False
        rom.read_reg=lambda address:rom.MAGIC_VALUE
        rom.flash_id=Mock(side_effect=AssertionError('Raw ROM capacity must not be queried'))
        stub=ESP8266StubLoader.__new__(ESP8266StubLoader)
        stub.flash_id=lambda cache=False:0x1640ef
        configured=[];stub.flash_set_parameters=lambda size:configured.append(size)
        uploads=[]
        def upload(spec):
            uploads.append(spec)
            self.assertEqual(spec.STUB_SUBDIRS,['2'])
            self.assertEqual(spec.plugin_segments,[])
            return stub
        rom.run_stub=upload
        with patch.object(app,'load_pinned_esptool',return_value=(esptool,{})):
            t=app.PinnedStubTransport(rom,Path('synthetic pins mocked separately'))
            self.assertEqual(t.identity,('ESP8266',2,0x400000));self.assertEqual(configured,[0x400000])
            self.assertEqual(len(uploads),1)
            rom.flash_id.assert_not_called()
            for change in ('unknown_stub','wrong_magic'):
                rom.sync_stub_detected=change=='unknown_stub'
                rom.read_reg=lambda address:0 if change=='wrong_magic' else rom.MAGIC_VALUE
                with self.subTest(change=change),self.assertRaises(app.WriteError):app.PinnedStubTransport(rom,Path('synthetic'))
                self.assertEqual(len(uploads),1)

    def test_post_stub_capacity_is_measured_once_before_begin(self):
        from esptool.targets.esp8266 import ESP8266ROM,ESP8266StubLoader
        from serial import SerialException
        import esptool
        for outcome in (0x1640ef,0x0040ef,0x1540ef,SerialException('synthetic ID failure'),TimeoutError('synthetic timeout')):
            with self.subTest(outcome=type(outcome).__name__):
                events=[]
                rom=ESP8266ROM.__new__(ESP8266ROM);rom.sync_stub_detected=False
                rom.read_reg=lambda address:events.append('magic') or rom.MAGIC_VALUE
                rom.flash_id=Mock(side_effect=AssertionError('Raw ROM capacity must not be queried'))
                stub=ESP8266StubLoader.__new__(ESP8266StubLoader)
                stub.flash_set_parameters=lambda size:events.append(('geometry',size))
                def measure(cache=False):
                    self.assertIs(cache,False);events.append('stub_id')
                    if isinstance(outcome,Exception):raise outcome
                    return outcome
                stub.flash_id=Mock(side_effect=measure)
                def upload(spec):
                    self.assertEqual(spec.STUB_SUBDIRS,['2'])
                    self.assertTrue(spec.STUB_VERSION_EXPLICIT)
                    self.assertEqual(spec.plugin_segments,[])
                    events.append('upload');return stub
                rom.run_stub=Mock(side_effect=upload)
                stub.check_command=Mock(side_effect=lambda label,op,*args:events.append(op))
                stub.flash_md5sum=Mock(return_value=hashlib.md5(FIXTURE).hexdigest())
                session=app.SingleAttempt()
                with patch.object(app,'load_pinned_esptool',return_value=(esptool,{})),patch.object(app,'candidate',return_value=(FIXTURE,{'sha256':app.FROZEN_SHA256})):
                    factory=lambda:app.PinnedStubTransport(rom,Path('synthetic'))
                    if outcome==0x1640ef:
                        result=session.write(Path('synthetic'),app.FROZEN_SHA256,factory,app.GO_TEXT)
                        self.assertEqual(result['begin_count'],1)
                        self.assertEqual(events[4:],[2]+[3]*101+[4])
                        stub.flash_md5sum.assert_called_once_with(0,app.FROZEN_BYTES)
                    else:
                        error=type(outcome) if isinstance(outcome,Exception) else app.WriteError
                        with self.assertRaises(error):session.write(Path('synthetic'),app.FROZEN_SHA256,factory,app.GO_TEXT)
                        stub.check_command.assert_not_called();stub.flash_md5sum.assert_not_called()
                    with self.assertRaises(app.WriteError):session.write(Path('synthetic'),app.FROZEN_SHA256,factory,app.GO_TEXT)
                self.assertEqual(events[:4],['magic','upload',('geometry',0x400000),'stub_id'])
                rom.flash_id.assert_not_called();rom.run_stub.assert_called_once()
                stub.flash_id.assert_called_once_with(cache=False)

    def test_only_capacity_query_in_adapter_is_post_stub(self):
        tree=ast.parse(Path(app.__file__).read_text(encoding='utf-8'))
        adapter=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='PinnedStubTransport')
        constructor=next(node for node in adapter.body if isinstance(node,ast.FunctionDef) and node.name=='__init__')
        queries=[node for node in ast.walk(constructor) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='flash_id']
        self.assertEqual(len(queries),1)
        self.assertEqual(ast.unparse(queries[0].func.value),'self.loader')


if __name__=='__main__':unittest.main()
