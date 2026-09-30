"""Dedicated runner commands cannot skip; discovery tolerates absent toolchains."""
from pathlib import Path
import os
import unittest

from v07_pinned_core_probe import core_root
from v08_m6a_socket_runner import ROOT, run
from v08_m6a_source_lab import run as source_run


class Remediation(unittest.TestCase):
    def test_source_decisions(self):
        if not (core_root()/'package.json').is_file():
            self.skipTest('pinned Core absent; dedicated CI source command is required')
        for variant, evidence in source_run().items():
            with self.subTest(variant=variant):
                self.assertEqual(evidence['result']['failed'],0)

    def test_socket_composition(self):
        json_src = Path(os.environ.get('SHINO_ARDUINOJSON_SRC',str(ROOT/'experiments/v08_full_bridge/.pio/libdeps/bridge_baseline/ArduinoJson/src')))
        if not (core_root()/'package.json').is_file() or not (json_src/'ArduinoJson.h').is_file():
            self.skipTest('pinned Core and real ArduinoJson absent; dedicated CI socket command is required')
        rows = run()['runs']
        self.assertEqual(len(rows),4)
        for row in rows:
            r = row['result']
            with self.subTest(variant=row['variant'],oem=row['conditional_oem']):
                self.assertEqual(r['failed'],0)
                self.assertEqual(r['contexts_created'],r['contexts_destroyed'])
                self.assertEqual(r['stock_ready_grace_ms'],30)
                self.assertEqual(r['overlay_ready_release_tick_ms'],2000 if row['variant']=='previous' else 31)
                if row['variant']!='stock':
                    self.assertLessEqual(r['max_preparse_only_bytes'],64)
                    self.assertGreaterEqual(r['deadline_handoff_us'],2000000)


if __name__=='__main__': unittest.main()
