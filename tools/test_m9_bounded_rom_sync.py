"""Phase M: deterministic shared-budget acquisition and real K integration; fake serial."""
from contextlib import ExitStack
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import m9_single_attempt_physical_runner as runner
import test_m9_single_attempt_physical_runner as phase_l
from esptool.targets.esp8266 import ESP8266ROM


class Clock:
    def __init__(self): self.now=0; self.delays=[]; self.oversleep=0
    def monotonic(self): return self.now
    def sleep(self, seconds):
        self.delays.append(seconds); self.now += seconds + self.oversleep


class RetrySerial(phase_l.SpySerial):
    success_at=1
    partial_bytes=3
    read_chunk=100000
    def __init__(self, **kwargs):
        super().__init__(**kwargs); self.sync_count=0; self.purges=[]
    def reset_input_buffer(self):
        self.purges.append(('input', self.sync_count)); super().reset_input_buffer()
    def reset_output_buffer(self): self.purges.append(('output', self.sync_count))
    def write(self, encoded):
        super().write(encoded)
        if self.calls[-1]=='sync':
            self.sync_count += 1
            if self.sync_count < self.success_at:
                # Incomplete SLIP state followed by an empty read, as pinned
                # slip_reader turns into FatalError. Must discard before retry.
                self.buffer=bytearray(b'\xc0'+b'\x01'*(self.partial_bytes-1))
    def read(self, size): return super().read(min(size,self.read_chunk))


class BoundedSyncTests(unittest.TestCase):
    def exercise(self, success_at=1, serial_class=None, clock=None, **changes):
        class Serial(RetrySerial): pass
        Serial.success_at=success_at
        budgets=[]; original=runner.BoundedSyncReads
        def shared(port):
            budget=original(port); budgets.append(budget); return budget
        clock=clock or Clock()
        with patch.object(runner.time,'monotonic',clock.monotonic),patch.object(runner.time,'sleep',clock.sleep),patch.object(runner,'BoundedSyncReads',side_effect=shared):
            result=phase_l.RunnerTests().exercise(serial_class=serial_class or Serial,**changes)
        code, report, ports, uploads=result
        self.assertEqual(len(budgets),1)
        self.assertIs(budgets[0].port,ports[0])
        self.assertLessEqual(budgets[0].calls,256); self.assertGreaterEqual(budgets[0].remaining,0)
        self.assertLessEqual(ports[0].calls.count('sync'),5)
        self.assertEqual(ports[0].opens,1); self.assertEqual(ports[0].closes,1)
        self.assertEqual(ports[0].controls,[('dtr',False,False),('rts',False,False)])
        self.assertTrue(all(delay==0.05 for delay in clock.delays))
        return result,budgets[0],clock

    def test_success_at_each_of_five_attempts_one_upload_one_transaction(self):
        for position in range(1,6):
            with self.subTest(success_at=position):
                (code,report,ports,uploads),budget,clock=self.exercise(position)
                self.assertEqual(code,0); self.assertEqual(len(uploads),1)
                p=ports[0]
                self.assertEqual(p.calls,['sync']*position+['begin']+[('data',i) for i in range(98)]+['finish','md5'])
                self.assertEqual(p.purges,[(name,i) for i in range(position) for name in ('input','output')])
                self.assertEqual(clock.delays,[0.05]*(position-1))
                self.assertEqual(budget.calls,2*(position-1)+1)
                self.assertFalse(report['full_post_verified']); self.assertEqual(report['automatic_retries'],0)

    def test_all_five_fail_no_sixth_sync_no_stub_no_flash(self):
        (code,report,ports,uploads),budget,clock=self.exercise(6)
        self.assertEqual((code,report),(1,{'status':runner.UNKNOWN}))
        self.assertEqual(uploads,[]); self.assertEqual(ports[0].calls,['sync']*5)
        self.assertEqual(clock.delays,[0.05]*4); self.assertEqual(budget.calls,10)

    def test_global_time_not_restarted_and_no_catchup_after_oversleep(self):
        clock=Clock();clock.oversleep=5
        (code,report,ports,uploads),budget,_=self.exercise(6,clock=clock)
        self.assertEqual(code,1);self.assertEqual(uploads,[])
        self.assertEqual(ports[0].calls,['sync']);self.assertEqual(clock.delays,[0.05])
        self.assertEqual(budget.deadline,5)

    def test_global_time_exhausted_during_read_prevents_retry_and_upload(self):
        clock=Clock()
        class Slow(RetrySerial):
            success_at=6
            def read(self,size):
                data=super().read(size);clock.now+=2.6;return data
        (code,_,ports,uploads),budget,_=self.exercise(serial_class=Slow,clock=clock)
        self.assertEqual(code,1);self.assertEqual(uploads,[]);self.assertEqual(ports[0].calls,['sync'])
        self.assertEqual(clock.delays,[]);self.assertEqual(budget.deadline,5)

    def test_global_bytes_exhaust_across_attempts_without_new_budget(self):
        class Large(RetrySerial): success_at=6; partial_bytes=4000
        (code,_,ports,uploads),budget,clock=self.exercise(serial_class=Large)
        self.assertEqual(code,1);self.assertEqual(uploads,[])
        self.assertEqual(ports[0].calls,['sync']*5);self.assertEqual(budget.remaining,0)
        self.assertEqual(clock.delays,[0.05]*4)

    def test_global_read_cap_exhaust_across_attempts_stops_before_fifth(self):
        class Bytewise(RetrySerial): success_at=6; partial_bytes=64; read_chunk=1
        (code,_,ports,uploads),budget,_=self.exercise(serial_class=Bytewise)
        self.assertEqual(code,1);self.assertEqual(uploads,[])
        self.assertEqual(budget.calls,256);self.assertEqual(ports[0].calls,['sync']*4)

    def test_malformed_envelope_is_terminal_before_stub(self):
        class Malformed(RetrySerial):
            def __init__(self,**kwargs): super().__init__(**kwargs);self.sync_body=b'\0'*3
        (code,_,ports,uploads),_,clock=self.exercise(serial_class=Malformed)
        self.assertEqual(code,1);self.assertEqual(uploads,[])
        self.assertEqual(ports[0].calls,['sync']);self.assertEqual(clock.delays,[])

    def test_complete_sequence_semantics_stub_and_mixed_fail_closed(self):
        original=ESP8266ROM.sync
        for pattern,expected_flag in [('all',True),(0,False),(7,False)]:
            completed=[]
            def sync(rom):
                original(rom);completed.append(rom.sync_stub_detected)
            with self.subTest(pattern=pattern),patch.object(ESP8266ROM,'sync',sync):
                (code,_,ports,uploads),_,clock=self.exercise(stub_value=pattern)
            self.assertEqual(completed,[expected_flag])  # Classification only after all eight.
            self.assertEqual(code,1);self.assertEqual(uploads,[])
            self.assertEqual(ports[0].calls,['sync']);self.assertEqual(clock.delays,[])

    def test_other_inconsistent_rom_values_rejected_after_complete_sequence(self):
        from test_m9_single_attempt_physical_runner import slip
        import struct
        class Mixed(RetrySerial):
            def write(self,encoded):
                super().write(encoded)
                if self.calls[-1]=='sync':
                    self.buffer=bytearray().join(slip(struct.pack('<BBHI',1,8,4,value)+b'\0'*4)
                        for value in [0x20120707]*7+[1])
        (code,_,ports,uploads),_,clock=self.exercise(serial_class=Mixed)
        self.assertEqual(code,1);self.assertEqual(uploads,[]);self.assertEqual(clock.delays,[])
        self.assertEqual(ports[0].calls,['sync'])

    def test_serial_disconnect_timeout_and_interrupt_never_sync_retry(self):
        from serial import SerialException
        for error in (SerialException,TimeoutError,KeyboardInterrupt):
            with self.subTest(error=error.__name__):
                (code,_,ports,uploads),_,clock=self.exercise(fail='sync',error=error)
                self.assertEqual(code,1);self.assertEqual(uploads,[])
                self.assertEqual(ports[0].calls,['sync']);self.assertEqual(clock.delays,[])

    def test_exact_source_spans_and_version_mutation_rejected(self):
        from m9_phase_m_qualification import source_gate
        report=source_gate()
        self.assertEqual(set(report['functions']),{'_connect_attempt','connect','sync','command','slip_reader'})
        self.assertEqual(report['reviewed_inner_sync_maximum'],5)
        with patch('importlib.metadata.version',return_value='UNPINNED'),self.assertRaises(ValueError):source_gate()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'loader.py').write_bytes(b'UNPINNED_SOURCE')
            with self.assertRaises(ValueError):source_gate(Path(tmp))


if __name__=='__main__':unittest.main()
