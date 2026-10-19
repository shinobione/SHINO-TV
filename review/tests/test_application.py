"""P0 regression paths against the same complete C++ HTTP application as weather."""
import json,hashlib,unittest,time
import clock_sync
import test_weather as wx
from ota_fixture import fixture,signature
DEVICE='0123456789abcdef';BUILD='b'*64
OTA_PASSWORD='PUBLIC-INERT-HTTP-OTA-TEST-PASSWORD'
class Application(unittest.TestCase):
 setUp=wx.IntegratedWeather.setUp;tearDown=wx.IntegratedWeather.tearDown
 command=wx.IntegratedWeather.command;wire=wx.IntegratedWeather.wire;auth=wx.IntegratedWeather.auth
 def test_digest_and_exact_journal_pages(self):
  prefix='/api/v1/m9/normal/journal/'
  for i in range(3):
   path=prefix+str(i);self.assertEqual(self.wire(path)[0],401)
   code,data=self.auth(path);self.assertEqual(code,200);self.assertEqual(data['page'],i);self.assertEqual(len(data['hex']),512)
  for tail in ('3','00','-1','0/','%30','0?x=1'):
   self.assertNotEqual(self.wire(prefix+tail)[0],200)
 def test_link_four_values_clock_and_six_second_ttl(self):
  raw=json.dumps(dict(ok=True,gpu_available=True,cpu_usage=22.5,gpu_usage=34.5,memory_used_gb=8,memory_total_gb=16,gpu_vram_mb=2048,gpu_temp_c=56,gpu_power=120)).encode()
  self.assertEqual(self.auth('/api/v1/bridge/metrics',raw)[0],200)
  stats=self.command('stats');self.assertEqual([stats[k] for k in ('cpu','gpu','ram','temperature')],[22.5,34.5,8,56])
  self.assertTrue(self.auth('/api/v1/update/status')[1]['metrics_fresh'])
  status=self.auth('/api/v1/clock/status')[1]
  frame=clock_sync.seal(dict(schema=1,utc_s=int(time.time()),offset_min=0,lease_s=120),status,clock_sync.derive_key('PUBLIC-INERT-LAB-HTTP-FIXTURE'))
  self.assertEqual(self.auth('/api/v1/clock/sync',frame,'application/octet-stream')[0],200)
  status=self.auth('/api/v1/clock/status')[1];self.assertTrue(status['valid'] and status['synced'])
  self.command('advance 6001');self.assertFalse(self.auth('/api/v1/update/status')[1]['metrics_fresh'])
 def headers(self,raw,wrong=False):
  status=self.auth('/api/v1/update/status')[1]
  manifest=dict(device=DEVICE,build_id=BUILD,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  return {'Content-Type':'application/octet-stream','X-Shino-SHA256':manifest['sha256'],'X-Shino-Build':BUILD,'X-Shino-Nonce':status['nonce'],'X-Shino-Proof':'0'*64 if wrong else signature(dict(device=DEVICE,maintenance_password=OTA_PASSWORD),status['nonce'],manifest)}
 def test_hmac_core_staging_and_rtc_are_ram_only(self):
  raw=fixture();code,body=self.wire('/api/v1/update','POST',raw,self.headers(raw));self.assertEqual(code,200,body)
  self.assertEqual(json.loads(body)['status'],'STAGED_PENDING_BOOT');stats=self.command('stats')
  self.assertGreater(stats['flash_writes'],0);self.assertEqual(stats['sdk_writes'],0);self.assertEqual(stats['restarts'],1)
  self.assertTrue(stats['rtc_pending']);self.assertTrue(stats['fs_preserved'])
 def faulted_transfer(self,fault):
  # Synthetic RAM flash; no real UART/RTC/flash or real firmware file.
  raw=fixture()
  headers=self.headers(raw)
  self.assertTrue(self.command('fault '+fault)['ok'])
  code,body=self.wire('/api/v1/update','POST',raw,headers)
  self.assertEqual(code,422,(fault,body))
  stats=self.command('stats')
  self.assertFalse(stats['rtc_pending'],fault) # no eboot switch command
  self.assertTrue(stats['fs_preserved'],fault) # all protected sectors remain untouched
  self.assertEqual(stats['restarts'],0,fault)
  self.assertEqual(stats['sdk_writes'],0,fault)
 def test_core_erase_failure_no_eboot_commit_or_fs_write(self):
  self.faulted_transfer('erase')
 def test_core_write_failure_no_eboot_commit_or_fs_write(self):
  self.faulted_transfer('write')
 def test_core_readback_failure_no_eboot_commit_or_fs_write(self):
  self.faulted_transfer('read')
 def test_wrong_hmac_refused_before_ram_flash_write(self):
  raw=fixture();self.assertEqual(self.wire('/api/v1/update','POST',raw,self.headers(raw,True))[0],503)
  stats=self.command('stats');self.assertEqual(stats['flash_writes'],0);self.assertEqual(stats['sdk_writes'],0);self.assertEqual(stats['restarts'],0)
 def test_crc_corruption_never_commits(self):
  raw=bytearray(fixture());raw[0x1014]^=1;raw=bytes(raw)
  code,body=self.wire('/api/v1/update','POST',raw,self.headers(raw));self.assertEqual(code,422,body)
  stats=self.command('stats');self.assertEqual(stats['sdk_writes'],0);self.assertEqual(stats['restarts'],0)
