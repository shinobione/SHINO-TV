import json,os,sys,unittest
from pathlib import Path
R=Path(os.environ['SHINO_M3R_LAB_OUT']).resolve();sys.path[:0]=[str(R/'patched/tests'),str(R/'patched/clients'),str(R/'patched')]
os.environ['P0_B54_HOST_EXE']=str(R/'patched/.build'/('receiver.exe' if os.name=='nt' else 'receiver'))
names=['test_application.Application.'+x for x in ['test_digest_and_exact_journal_pages','test_link_four_values_clock_and_six_second_ttl','test_hmac_core_staging_and_rtc_are_ram_only','test_wrong_hmac_refused_before_ram_flash_write','test_crc_corruption_never_commits']]
names+=['test_weather.IntegratedWeather.'+x for x in ['test_status_sample_ack_and_replay','test_bad_hmac_identity_boot_location_sequence_and_expiry','test_link_clock_and_digest_remain_after_weather','test_concurrent_requests_and_nested_loop']]
names+=['test_source.Source.'+x for x in ['test_content_mutation_and_missing_source_refused','test_fixture_identity_cannot_compile_on_esp8266','test_native_host_application_bodies_match','test_updater_patch_is_the_only_flash_buffer_change']]
import test_application
original_command=test_application.Application.command
def checked_command(self,s,reply=True):
 result=original_command(self,s,reply)
 if s=='stats':self.assertEqual(result['protected_regions_unchanged'],1)
 return result
test_application.Application.command=checked_command
if '--remaining' in sys.argv:names=names[:5]
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names));(R/('regression-remaining-summary.json' if '--remaining' in sys.argv else 'regression-summary.json')).write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped)),indent=2));sys.exit(not result.wasSuccessful())
