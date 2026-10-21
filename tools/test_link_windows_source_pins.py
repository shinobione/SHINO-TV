"""Windows additions require exact pins in BOTH historical gates; no SDK/network."""
import ast
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import test_m9_b5_offline_source_pins as baseline
import m9_signed_ota_runner as signed
import m9_stagea_source_gate as stagea

ROOT=Path(__file__).resolve().parents[1]
WINDOWS=(
    'companion/link_windows.py', 'companion/link_windows_smoke.py',
    'companion/requirements-windows-build.txt', 'companion/shino_link_windows.pyw',
    'companion/test_link_windows.py',
)


class WindowsSourcePins(unittest.TestCase):
    setUp=baseline.OfflineSourcePinsTests.setUp

    def test_both_gates_pin_all_five_new_files_to_exact_commit_blobs(self):
        for gate in (signed,stagea):
            tree=ast.parse(Path(gate.__file__).read_text(encoding='utf-8'))
            assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='new_offline_script_pins' for t in n.targets))
            pins=ast.literal_eval(assignment.value)
            for name in WINDOWS:
                with self.subTest(gate=gate.__name__,name=name):
                    expected=subprocess.check_output(['git','rev-parse','HEAD:'+name],cwd=ROOT,text=True).strip()
                    self.assertEqual(pins.get(name),expected)

    def test_each_new_windows_file_mutation_is_rejected_by_both_gates(self):
        original=subprocess.check_output
        for gate in (signed,stagea):
            for name in WINDOWS:
                def mutated(command,*args,**kwargs):
                    if command[:2]==['git','ls-files']:return '\n'.join(WINDOWS)+'\n'
                    if command==['git','hash-object','--',name]:return '0'*40+'\n'
                    return original(command,*args,**kwargs)
                with self.subTest(gate=gate.__name__,name=name), patch.object(subprocess,'check_output',side_effect=mutated):
                    with self.assertRaises(AssertionError):baseline.tracked_gate(gate)


if __name__=='__main__':unittest.main()
