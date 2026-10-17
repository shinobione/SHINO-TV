"""Regression: nested C++ call chains pass; orphan symbols still fail closed."""
import unittest
from shino_xtensa_callgraph import require_paths

DISASM='''40200000 <M9NormalStageA::loop()>:
  40200000: 000000 call0 40200100 <ShinoInstall::Maintenance<T1,T2,T3>::tick()>
  40200003: 000000 call0 40200300 <shinoMaintenanceConsent(ShinoInstall::Consent&)>
40200100 <ShinoInstall::Maintenance<T1,T2,T3>::tick()>:
  40200100: 000000 call0 40200400 <ShinoInstall::Native::pump()>
  40200103: 000000 call0 40200500 <ShinoInstall::Native::begin()>
  40200106: 000000 call0 40200600 <ShinoInstall::ReclaimingHttp::quiesce()>
40200300 <shinoMaintenanceConsent(ShinoInstall::Consent&)>:
  40200300: 000000 ret.n
40200400 <ShinoInstall::Native::pump()>:
  40200400: 000000 ret.n
40200500 <ShinoInstall::Native::begin()>:
  40200500: 000000 ret.n
40200600 <ShinoInstall::ReclaimingHttp::quiesce()>:
  40200600: 000000 ret.n
'''
class CallGraphTests(unittest.TestCase):
    def test_nested_direct_calls_are_proven(self):
        paths=require_paths(DISASM)
        self.assertEqual(len(paths['ShinoInstall::Native::pump']),3)
        self.assertEqual(len(paths),4)

    def test_linked_but_unreachable_symbol_fails(self):
        tampered=DISASM.replace(
            '  40200100: 000000 call0 40200400 <ShinoInstall::Native::pump()>\n','')
        with self.assertRaisesRegex(AssertionError,'NOT reachable'):
            require_paths(tampered)

    def test_renamed_native_symbol_fails(self):
        tampered=DISASM.replace(
            '40200400 <ShinoInstall::Native::pump()>:',
            '40200400 <NotNativePump()>:')
        with self.assertRaisesRegex(AssertionError,'NOT reachable'):
            require_paths(tampered)

if __name__=='__main__':
    unittest.main()
