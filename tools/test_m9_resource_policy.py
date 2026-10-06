"""Fail-closed local evidence qualification; all observations are synthetic."""
import copy
import unittest
from m9_resource_policy import evaluate, validate_status, policy, PolicyError


def status(samples=1):
    s = {k: True for k in ('resource_diagnostics_enabled', 'resource_measurements_valid', 'attempted',
         'autoformat_disabled', 'mounted', 'inventory_checked', 'inventory_exact', 'config_seed_exact')}
    s.update(write_paths_compiled=False, blocked_write_attempts=0, resource_rejected_sample_count=0,
             checked_file_count=24, checked_payload_bytes=181402, filesystem_start=0x200000,
             filesystem_end_exclusive=0x3FA000, filesystem_bytes=2072576, resource_sample_count=samples,
             mount_phase_cont_stack_start=3500, mount_phase_cont_stack_min_free=2400,
             runtime_cont_stack_start=3500, runtime_min_cont_stack_free=2300,
             heap_after_probe_free=36000, heap_after_probe_largest_block=30000, heap_after_probe_fragmentation=10,
             latest_free_heap=30000, latest_largest_free_block=24000, latest_fragmentation_percent=12,
             lowest_observed_free_heap=28000, lowest_observed_largest_free_block=22000,
             highest_observed_fragmentation_percent=15, available_heap_after_mount=36000,
             available_heap_after_inventory=36000, minimum_observed_free_heap=26000)
    return s


def observations():
    return dict(same_boot=True, digest_status_observed=True, stable_link_pass=True,
                telemetry_stale_recovery_pass=True, reboot_observed=False,
                display_corruption_observed=False, link_seconds=180)


class ResourcePolicyTests(unittest.TestCase):
    def test_scoped_pass_and_no_authority(self):
        report = evaluate(status(), status(181), observations())
        self.assertFalse(report['physical_authorization'])
        self.assertFalse(report['physical_authenticity_verified'])
        self.assertEqual(policy()['RESOURCE_POLICY_SCOPE'], 'M9_PROFILE2_INSTRUMENTED_MOUNT_PROBE_ONLY')

    def test_every_missing_status_field_fails_closed(self):
        for k in status():
            bad = status(); del bad[k]
            with self.subTest(key=k), self.assertRaises(PolicyError): validate_status(bad)

    def test_required_booleans_and_counts_fail_closed(self):
        for key, value in [('resource_diagnostics_enabled', False), ('resource_measurements_valid', False),
                           ('resource_rejected_sample_count', 1), ('blocked_write_attempts', 1),
                           ('mounted', False), ('inventory_exact', False), ('checked_file_count', 23),
                           ('checked_payload_bytes', 181401), ('config_seed_exact', False),
                           ('write_paths_compiled', True), ('resource_sample_count', 0),
                           ('filesystem_start', 0x100000)]:
            bad=status(); bad[key]=value
            with self.subTest(key=key), self.assertRaises(PolicyError): validate_status(bad)

    def test_strict_scalar_types_and_impossible_values(self):
        for key, value in [('resource_sample_count', True), ('resource_sample_count', -1),
                           ('resource_sample_count', 2**32), ('heap_after_probe_free', 81921),
                           ('heap_after_probe_largest_block', 36001), ('latest_fragmentation_percent', 101),
                           ('mount_phase_cont_stack_start', 4097), ('mount_phase_cont_stack_start', 3501),
                           ('runtime_min_cont_stack_free', 3504), ('mount_phase_cont_stack_min_free', 3504),
                           ('latest_free_heap', 20000), ('latest_fragmentation_percent', 26),
                           ('latest_largest_free_block', 16383), ('runtime_min_cont_stack_free', 2044)]:
            bad=status(); bad[key]=value
            with self.subTest(key=key, value=value), self.assertRaises(PolicyError): validate_status(bad)

    def test_all_numeric_boundaries_inclusive_and_one_step_fail(self):
        s=status()
        for k in ('heap_after_probe_free','latest_free_heap','lowest_observed_free_heap',
                  'available_heap_after_mount','available_heap_after_inventory','minimum_observed_free_heap'):s[k]=20480
        for k in ('heap_after_probe_largest_block','latest_largest_free_block','lowest_observed_largest_free_block'):s[k]=16384
        for k in ('heap_after_probe_fragmentation','latest_fragmentation_percent','highest_observed_fragmentation_percent'):s[k]=25
        for k in ('mount_phase_cont_stack_start','mount_phase_cont_stack_min_free','runtime_cont_stack_start','runtime_min_cont_stack_free'):s[k]=2048
        validate_status(s)
        for k in s:
            if k in ('resource_sample_count','checked_file_count','checked_payload_bytes','filesystem_start',
                     'filesystem_end_exclusive','filesystem_bytes','blocked_write_attempts','resource_rejected_sample_count') or type(s[k]) is not int:continue
            bad=copy.deepcopy(s);bad[k]=s[k]+1 if 'fragmentation' in k else s[k]-1
            with self.subTest(key=k),self.assertRaises(PolicyError):validate_status(bad)

    def test_observer_invalidity_and_absent_owner_facts(self):
        obs=observations()
        for k in obs:
            for v in (None, 179 if k=='link_seconds' else not obs[k]):
                bad=obs.copy();bad[k]=v
                with self.subTest(key=k, value=v),self.assertRaises(PolicyError):evaluate(status(),status(181),bad)

    def test_nonadvancing_saturated_counts_and_changed_windows(self):
        for old,new in [(1,1),(2,1),(0xFFFFFFFF,0xFFFFFFFF)]:
            with self.subTest(old=old,new=new),self.assertRaises(PolicyError):evaluate(status(old),status(new),observations())
        for k in ('mount_phase_cont_stack_start','mount_phase_cont_stack_min_free','heap_after_probe_free',
                  'heap_after_probe_largest_block','heap_after_probe_fragmentation','runtime_cont_stack_start',
                  'runtime_min_cont_stack_free','lowest_observed_free_heap','lowest_observed_largest_free_block',
                  'minimum_observed_free_heap','highest_observed_fragmentation_percent'):
            s=status(181);s[k] += -1 if k=='highest_observed_fragmentation_percent' else 4
            with self.subTest(key=k),self.assertRaises(PolicyError):evaluate(status(),s,observations())

    def test_cached_min_max_inconsistency(self):
        for k,v in [('lowest_observed_free_heap',30001), ('lowest_observed_largest_free_block',24001),
                    ('highest_observed_fragmentation_percent',11), ('minimum_observed_free_heap',36001)]:
            s=status();s[k]=v
            with self.subTest(key=k),self.assertRaises(PolicyError):validate_status(s)


if __name__=='__main__':unittest.main()
