"""Binding, fail-before-transport and POST model tests. Hardware never invoked."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
import m9_phase_o_qualification as qualification
import m9_single_attempt_app_write as app
import m9_single_attempt_physical_runner as runner
from m9_stage1_readback_verify import verify_stage1, ReadbackError

ROOT = qualification.ROOT
NORMAL_SHA = '78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c'
OLD_HASHES = ('e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e',
              '2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835')


class PhaseOTests(unittest.TestCase):
    def test_exact_active_binding_source_and_firmware_identity(self):
        report = qualification.source_gate()
        self.assertEqual(report['PHASE_O_BINDING_SOURCE_GATE'], 'PASS/OFFLINE')
        self.assertEqual(report['firmware_files_checked'], 113)
        self.assertEqual((app.FROZEN_BYTES, app.FROZEN_SHA256, app.ROUNDED_END, app.BLOCK_COUNT),
                         (399264, NORMAL_SHA, 0x062000, 98))
        names = subprocess.check_output(['git', 'ls-files', 'firmware'], cwd=ROOT, text=True).splitlines()
        pins = json.loads(qualification.PINS.read_text(encoding='utf-8'))
        self.assertEqual(set(names), set(pins['firmware_sha256_lf']))
        self.assertTrue(report['transaction_classes_source_equivalent'])
        self.assertTrue(report['runner_source_equivalent_except_numeric_receipt'])
        self.assertEqual(report['PHASE_O_RETAINED_CANDIDATE_IDENTITY_GATE'], 'NOT_READ_BY_THIS_RUN')
        self.assertFalse(report['physical_authorization'])

    def test_reviewed_runner_receipt_projection_rejects_acquisition_drift(self):
        pins = json.loads(qualification.PINS.read_text(encoding='utf-8'))
        text = (ROOT/'tools/m9_single_attempt_physical_runner.py').read_text(encoding='utf-8')
        qualification.runner_equivalent(text, pins['runner_predecessor_sha256_lf'])
        for mutation in (text.replace('MAX_SYNC_ATTEMPTS = 5', 'MAX_SYNC_ATTEMPTS = 6'),
                         text.replace('16384', '32768'), text.replace('0x061FFF', '0x064FFF')):
            with self.subTest(mutation=mutation[:20]), self.assertRaises(ValueError):
                qualification.runner_equivalent(mutation, pins['runner_predecessor_sha256_lf'])

    def test_transaction_projection_rejects_retry_capacity_md5_changes(self):
        pins = json.loads(qualification.PINS.read_text(encoding='utf-8'))
        text = (ROOT/'tools/m9_single_attempt_app_write.py').read_text(encoding='utf-8')
        qualification.transaction_equivalent(text, pins['transaction_class_sha256_lf'])
        for mutation in (text.replace('self.consumed = True', 'self.consumed = False'),
                         text.replace('== 0x16', '== 0x15'), text.replace('flash_md5sum(0, FROZEN_BYTES)', 'flash_md5sum(0, ROUNDED_END)')):
            with self.subTest(), self.assertRaises(ValueError):
                qualification.transaction_equivalent(mutation, pins['transaction_class_sha256_lf'])

    def test_old_successor_and_j_hash_go_refused_before_any_factory(self):
        for old in OLD_HASHES:
            for expected, go in ((old, app.GO_TEXT), (NORMAL_SHA, 'GO SINGLE ATTEMPT '+old),
                                 (old, 'GO SINGLE ATTEMPT '+old)):
                factory = Mock()
                with patch.object(app, 'candidate_bytes') as read, self.assertRaises(app.WriteError):
                    app.SingleAttempt().write(Path('never-read'), expected, factory, go)
                read.assert_not_called(); factory.assert_not_called()

    def test_old_successor_and_j_hash_go_refused_before_runner_acquisition(self):
        for old in OLD_HASHES:
            for expected, go in ((old, app.GO_TEXT), (NORMAL_SHA, 'GO SINGLE ATTEMPT '+old)):
                args = types.SimpleNamespace(candidate=Path('never-read'), expected_sha256=expected,
                                             owner_go=go, execute=True, port='COM8', stub_audit_root=Path('unused'))
                with (patch.object(runner, 'interpreter_gate'), patch.object(runner.Session, 'acquire') as acquire,
                      patch.object(app, 'candidate_bytes') as read):
                    code, report = runner.Session().run(args)
                self.assertEqual((code, report), (1, {'status':'STOP_PREFLIGHT_NO_PORT_OPEN'}))
                read.assert_not_called(); acquire.assert_not_called()

    def test_altered_or_truncated_normal_bytes_before_factory_and_acquisition(self):
        retained = ROOT/'research-local/m9-phase-n/frozen-normal-stage-a.bin'
        # CI uses synthetic wrong bytes. Local run also mutates the retained
        # image COPY; the freeze itself is never opened for writing.
        data = retained.read_bytes() if retained.exists() else bytes(app.FROZEN_BYTES)
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp)/'altered.bin'
            changed = bytearray(data); changed[0x20000] ^= 1
            for raw in (bytes(changed), data[:-1]):
                image.write_bytes(raw)
                factory = Mock()
                with self.assertRaises(ValueError):
                    app.SingleAttempt().write(image, NORMAL_SHA, factory, app.GO_TEXT)
                factory.assert_not_called()
                args = types.SimpleNamespace(candidate=image, expected_sha256=NORMAL_SHA, owner_go=app.GO_TEXT,
                                             execute=True, port='COM8', stub_audit_root=Path('unused'))
                with patch.object(runner, 'interpreter_gate'), patch.object(runner.Session, 'acquire') as acquire:
                    code, report = runner.Session().run(args)
                self.assertEqual((code, report), (1, {'status':'STOP_PREFLIGHT_NO_PORT_OPEN'}))
                acquire.assert_not_called()

    def test_frozen_candidate_ignored_not_tracked_and_source_only_ci(self):
        path = 'research-local/m9-phase-n/frozen-normal-stage-a.bin'
        subprocess.run(['git', 'check-ignore', '--quiet', path], cwd=ROOT, check=True)
        self.assertEqual(subprocess.check_output(['git', 'ls-files', '--', path], cwd=ROOT, text=True), '')
        for workflow in (ROOT/'.github/workflows').glob('*.yml'):
            self.assertNotIn('frozen-normal-stage-a.bin', workflow.read_text(encoding='utf-8'))

    def test_wrong_rounded_extent_rejected_independently_before_factory(self):
        factory = Mock()
        with (patch.object(app, 'candidate_bytes', return_value=(bytes(399264),
              {'sha256':NORMAL_SHA, 'sector_rounded_write_extent':0x065000})), self.assertRaises(app.WriteError)):
            app.SingleAttempt().write(Path('modeled-image'), NORMAL_SHA, factory, app.GO_TEXT)
        factory.assert_not_called()

    def test_print_only_packet_and_normal_gates_no_boot_authority(self):
        report = qualification.qualify()
        self.assertEqual(report['NORMAL_PROFILE_LITTLEFS_MOUNT_GATE'], 'NOT_RUN')
        self.assertEqual(report['NORMAL_PROFILE_RUNTIME_GATE'], 'NOT_RUN')
        packet = report['future_packet']
        self.assertEqual(packet['scope'], 'PRINT ONLY / NOT AUTHORIZED BY PHASE O')
        self.assertEqual(packet['protected_interval'], '0x062000..0x3FFFFF')
        self.assertFalse(packet['physical_authorization'])
        steps = '\n'.join(packet['steps'])
        self.assertIn('POST before first normal boot', steps)
        self.assertIn('RTC neutralization', steps)
        self.assertIn('separate later physical gates', steps)
        self.assertIn('POST[0x062000:0x400000]', steps)

    def test_full_post_candidate_and_continuous_protected_interval_model(self):
        # Full independent files, synthetic flash model ONLY. Real shared
        # comparator proves byte equality; candidate parser is modeled here.
        payload = bytes((i % 251 for i in range(app.FROZEN_BYTES)))
        inspected = dict(sha256=hashlib.sha256(payload).hexdigest(), sector_rounded_write_extent=0x62000)
        pre = bytes([0x5a])*0x400000
        after = bytearray(pre); after[:len(payload)] = payload
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); candidate = root/'candidate.bin'; before = root/'pre.bin'; post = root/'post.bin'
            candidate.write_bytes(payload); before.write_bytes(pre); post.write_bytes(after)
            with patch('m9_stage1_readback_verify.candidate_bytes', return_value=(payload, inspected)):
                result = verify_stage1(candidate, before, post, inspected['sha256'])
                self.assertEqual(result['protected_range_inclusive'], '0x062000..0x3FFFFF')
                self.assertEqual(result['protected_bytes_compared'], 3792896)
                self.assertFalse(result['physical_authorization'])
                for offset in (0, 0x62000, 0x1fffff, 0x200000, 0x3f9fff, 0x3fa000, 0x3fffff):
                    changed = bytearray(after); changed[offset] ^= 1; post.write_bytes(changed)
                    with self.subTest(offset=offset), self.assertRaises(ReadbackError):
                        verify_stage1(candidate, before, post, inspected['sha256'])
                post.write_bytes(after[:-1])
                with self.assertRaises(ReadbackError): verify_stage1(candidate, before, post, inspected['sha256'])


if __name__ == '__main__':
    unittest.main()
