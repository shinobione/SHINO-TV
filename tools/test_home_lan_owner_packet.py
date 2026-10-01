"""Private-owner preparation safeguards; synthetic paths, no owner/device I/O."""
import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import home_lan_owner_packet as p

class OwnerPacketTests(unittest.TestCase):
    def test_CI_cannot_enable_active_owner_shadow_or_read_inputs(self):
        with patch.dict(os.environ,{'CI':'true'}),patch.object(p,'checked_inputs') as read:
            with self.assertRaisesRegex(ValueError,'forbidden in CI'):
                p.prepare_owner_shadow(p.ROOT,None,None,['-DSHINO_P1_OWNER_PRIVATE=1'])
            with self.assertRaisesRegex(ValueError,'forbidden in CI'):p.build_packet(None)
        read.assert_not_called()

    def test_owner_flag_and_explicit_inputs_fail_before_private_reads(self):
        with patch.dict(os.environ,{},clear=True),patch.object(p,'checked_inputs') as read:
            with self.assertRaisesRegex(ValueError,'flag required'):p.prepare_owner_shadow(p.ROOT,None,None,[])
            with self.assertRaisesRegex(ValueError,'inputs required'):p.prepare_owner_shadow(p.ROOT,None,None,['SHINO_P1_OWNER_PRIVATE=1'])
        read.assert_not_called()

    def test_private_output_cannot_be_repository_or_descendant(self):
        for location in (p.ROOT,p.ROOT/'research-local/private-kit'):
            with self.assertRaisesRegex(ValueError,'outside Git'):p.outside(location)
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(p.outside(folder),Path(folder).resolve())

    def test_retained_rollback_mismatch_stops_before_policy_or_fixture_read(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'synthetic';path.write_bytes(b'not an owner image')
            with patch.object(p,'macros') as policy:
                with self.assertRaisesRegex(ValueError,'OEM bytes/hash mismatch'):
                    p.checked_inputs({k:path for k in p.INPUTS})
            policy.assert_not_called()

    def test_source_mismatch_and_dirty_tree_cannot_build(self):
        from types import SimpleNamespace
        args=SimpleNamespace(expected_source_sha='a'*40)
        with patch.dict(os.environ,{},clear=True),patch.object(p.subprocess,'check_output',return_value='b'*40),patch.object(p,'checked_inputs') as read:
            with self.assertRaisesRegex(ValueError,'Source SHA mismatch'):p.build_packet(args)
        read.assert_not_called()
        with patch.dict(os.environ,{},clear=True),patch.object(p.subprocess,'check_output',side_effect=['a'*40,' M tracked-source']),patch.object(p,'checked_inputs') as read:
            with self.assertRaisesRegex(ValueError,'Commit focused source'):p.build_packet(args)
        read.assert_not_called()

if __name__=='__main__':unittest.main()
