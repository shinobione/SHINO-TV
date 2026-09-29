"""The dedicated CI step requires dependencies; broad discovery may skip them."""
import os
from pathlib import Path
import unittest
from v07_pinned_core_probe import core_root
from v08_m5_socket_runner import ROOT, run

class SocketDispatchLab(unittest.TestCase):
    def test_actual_composition_and_cleanup(self):
        json_src=Path(os.environ.get('SHINO_ARDUINOJSON_SRC',str(ROOT/'experiments/v08_full_bridge/.pio/libdeps/bridge_baseline/ArduinoJson/src')))
        if not (core_root()/'package.json').is_file() or not (json_src/'ArduinoJson.h').is_file():
            self.skipTest('pinned Core and real ArduinoJson required; dedicated Mission 5 CI step must run without skipping')
        result=run()
        self.assertEqual(len(result['runs']),3)
        for row in result['runs']:
            with self.subTest(variant=row['variant'],oem=row['conditional_oem']):
                evidence=row['result']
                self.assertEqual(evidence['failed'],0)
                self.assertEqual(evidence['contexts_created'],evidence['contexts_destroyed'])
                self.assertEqual(evidence['stock_ready_grace_ms'],30)
                if row['variant']=='overlay':
                    self.assertLessEqual(evidence['max_preparse_only_bytes'],64)
                    self.assertGreaterEqual(evidence['deadline_handoff_us'],2000000)

if __name__=='__main__':
    unittest.main()
