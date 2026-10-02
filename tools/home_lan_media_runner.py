"""Real signed native 32px receiver/scene regression at AP and DHCP authorities.

Reuse P0 lab in temporary files, with P1's trusted authority setter. Signing
keys are ephemeral host fixtures. No device contacts or persistent output keys.
"""
import json,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run():
    results=[]
    for authority in ('192.168.4.1','192.168.1.12'):
        with tempfile.TemporaryDirectory(prefix='p1-signed-scenes-') as td:
            directory=Path(td);(directory/'native').mkdir()
            # Exact same one-line trusted setter as the native P1 shadow.
            ingress=(ROOT/'experiments/v08_m8r/native/MediaIngress.h').read_text(encoding='utf-8')
            ingress=ingress.replace('  void cancel() {','  void setExpectedHost(const char* host) { expectedHost=host; }\n  void cancel() {')
            (directory/'native/MediaIngress.h').write_text(ingress,encoding='utf-8')
            scene=(ROOT/'tools/scene_engine_lab.cpp').read_text(encoding='utf-8')
            scene=scene.replace('    void packet(const Packet& p,bool partial=false) {',
                '    void packet(const Packet& p,bool partial=false) {\n        ingress.setExpectedHost("'+authority+'");')
            (directory/'scene.cpp').write_text(scene,encoding='utf-8')
            fixtures=(ROOT/'tools/artwork_pilot_fixtures.js').read_text(encoding='utf-8').replace('"tv.test"',json.dumps(authority)).replace('Host: tv.test','Host: '+authority)
            fixtures=fixtures.replace('require("./v08_m6b_security")','require('+json.dumps(str(ROOT/'tools/v08_m6b_security.js'))+')')
            runner=(ROOT/'tools/artwork_pilot_runner.py').read_text(encoding='utf-8')
            runner=runner[:runner.index("if __name__=='__main__':")]
            runner=runner.replace("['node',str(ROOT/'tools/artwork_pilot_fixtures.js')]","['node','-e',"+repr(fixtures)+"]")
            runner=runner.replace("str(ROOT/'tools/scene_engine_lab.cpp')",repr(str(directory/'scene.cpp')))
            runner=runner.replace("includes += [ROOT/'experiments/v08_m8r/native'", "includes += [Path("+repr(str(directory/'native'))+"),ROOT/'experiments/v08_m8r/native'")
            namespace={'__file__':str(ROOT/'tools/artwork_pilot_runner.py')}
            exec(compile(runner,str(ROOT/'tools/artwork_pilot_runner.py'),'exec'),namespace)
            result=namespace['run'](directory/'previews')
            result['authority']=authority
            result.pop('preview_hashes',None)
            results.append(result)
    return {'scope':'actual BearSSL + native receiver + scenes at trusted AP/DHCP authority; host only',
            'runs':results,'device_contacts':0,'device_writes':0}
if __name__=='__main__':print(json.dumps(run(),indent=2))
