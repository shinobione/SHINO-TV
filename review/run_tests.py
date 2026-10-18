"""Reproducible source-only review: standard Python + C/C++ compiler, loopback only."""
import sys,os,json,unittest,socket,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for p in (ROOT,ROOT/'tests',ROOT/'clients'):sys.path.insert(0,str(p))
from verify_source import verify
from build_host import build

def main():
 verify();exe,native,env=build();os.environ.update(env)
 os.environ['P0_B54_HOST_EXE']=str(exe);os.environ['B54_LAN_NATIVE_EXE']=str(native)
 # Fail closed if any Python test attempts external network access.
 original=socket.socket.connect
 def local_only(peer,address):
  if not isinstance(address,tuple) or address[0]!='127.0.0.1':raise AssertionError('HOST tests permit only numeric IPv4 loopback')
  return original(peer,address)
 socket.socket.connect=local_only
 run=subprocess.run([str(native)],capture_output=True,text=True,timeout=20,check=True);print(run.stdout.strip())
 suite=unittest.defaultTestLoader.loadTestsFromNames(['test_source','test_weather','test_application','weather_vm.test_protocol','weather_vm.test_publisher'])
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 summary=dict(scope='HOST_SIMULATED_NOT_DEVICE',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),passed=result.wasSuccessful(),network='127.0.0.1_ONLY',firmware_builds=0)
 (ROOT/'.build/results.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
 return 0 if result.wasSuccessful() and not result.skipped else 1
if __name__=='__main__':raise SystemExit(main())
