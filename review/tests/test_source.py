import json,shutil,tempfile,unittest
from pathlib import Path
from verify_source import ROOT,verify
class Source(unittest.TestCase):
 def test_complete_public_inventory(self):self.assertGreater(len(verify()['files']),100)
 def test_content_mutation_and_missing_source_refused(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'native').mkdir();p=root/'native/a.h';p.write_text('expected');import hashlib
   (root/'SOURCES.json').write_text(json.dumps(dict(files={'native/a.h':dict(bytes=8,sha256=hashlib.sha256(b'expected').hexdigest())})))
   verify(root);p.write_text('modified')
   with self.assertRaises(ValueError):verify(root)
   p.unlink()
   with self.assertRaises(ValueError):verify(root)
 def test_fixture_identity_cannot_compile_on_esp8266(self):
  for name in ('ShinoRelease.h','shino_private_policy.h','B54LanPrivate.h'):
   for directory in ('host','native/include'):
    text=(ROOT/directory/name).read_text();self.assertIn('defined(ESP8266)',text);self.assertIn('#error',text)
 def test_native_host_application_bodies_match(self):
  for native,host in [('src/boot/M9NormalStageA.cpp','normal_host.inc'),('src/boot/B52Clock.cpp','B52Clock_host.inc'),('src/boot/B53Sntp.cpp','B53Sntp_host.inc'),('src/boot/B53Integrated.cpp','B53Integrated_host.inc'),('src/boot/B54LanNative.cpp','B54LanNative_host.inc')]:
   self.assertEqual((ROOT/'native'/native).read_text(),(ROOT/'host'/host).read_text())
 def test_updater_patch_is_the_only_flash_buffer_change(self):
  a=(ROOT/'native/core/Updater.upstream.cpp').read_text();b=(ROOT/'native/core/Updater.cpp').read_text()
  start=b.index('#if defined(SHINO_UPDATER_FLASH_BUFFER_512)');end=b.index('  if (ESP.getFreeHeap() > 2 * FLASH_SECTOR_SIZE)',start)
  restored=b[:start]+b[end:];self.assertEqual(a,restored)
  block=b[start:end];self.assertIn('command == U_FLASH',block);self.assertIn('_bufferSize = 512',block);self.assertIn('#error',block)
