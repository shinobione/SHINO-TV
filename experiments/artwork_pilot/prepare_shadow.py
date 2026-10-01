"""Equivalent offline full graphs. No private policy, device contact or upload."""
from pathlib import Path
import base64, json, os, shutil, subprocess
Import('env')
project = Path(env['PROJECT_DIR']).resolve()
repo = project.parents[1]
pilot = env['PIOENV'] != 'baseline_compile'
previous = env['PIOENV'] == 'previous_pilot_compile'
# Reuse the pinned M8 owner/crypto generator, with only public test material.
# Deliberately refuse inherited live-install environment variables.
if os.environ.get('SHINO_M8_PRIVATE_POLICY'):
    raise RuntimeError('Artwork pilot offline build refuses private install policy')
old = repo / 'experiments/v08_m8r/prepare_shadow.py'
text = old.read_text(encoding='utf-8')
text = text.replace("is_qualification=env['PIOENV']=='qualification_compile'", 'is_qualification=True')
text = text.replace("is_media=env['PIOENV'] in ('media_compile','stack_sensitivity_compile','qualification_compile')", 'is_media=True')
text = text.replace("str(project/'native')", "str(repo/'experiments/v08_m8r/native')")
start = text.index("    fixture=Path(os.environ.get(")
stop = text.index("    assert len(point)==65", start)
text = text[:start] + '''    pem=json.loads((repo/'tools/v08_crypto_vectors.json').read_text())['public_key_pem']
    der=base64.b64decode(''.join(pem.splitlines()[1:-1]))
    point=der[-65:]
''' + text[stop:]
exec(compile(text, str(old), 'exec'))
env.Prepend(CPPPATH=[str(project / 'native')])
if previous:
    # Rebuild the exact previous PR40 source with identical public policy,
    # compiler, key, partition and volatile startup guard. No private binary.
    previous_dir = project / '.pio/previous-native'
    shutil.copytree(repo/'experiments/v08_m8r/native', previous_dir, dirs_exist_ok=True)
    (previous_dir/'display').mkdir(exist_ok=True)
    for source, destination in (
        ('firmware/include/display/ArtworkPilot.h', previous_dir/'display/ArtworkPilot.h'),
        ('experiments/v08_m8r/native/MediaReceiver.h', previous_dir/'MediaReceiver.h'),
        ('experiments/artwork_pilot/native/ArtworkAdapter.inc', previous_dir/'ArtworkAdapter.inc'),
    ):
        content = subprocess.check_output(['git', 'show',
            'ec20f32f5960d7181671655751ded137a84c2963:'+source], cwd=repo)
        destination.write_bytes(content)
    # PlatformIO's project include_dir precedes CPPPATH. Replace the shadow
    # include too; otherwise old Receiver would accidentally see today's API.
    (shadow/'include/display/ArtworkPilot.h').write_bytes(
        (previous_dir/'display/ArtworkPilot.h').read_bytes())
    env.Prepend(CPPPATH=[str(previous_dir)])
# Both full graphs remain unstarted; volatile guard retains linked reachability.
main.write_text('''#include <Arduino.h>
#include "original_main.inc"
volatile unsigned char shinoArtworkOfflineGuard=0;
void setup(){if(shinoArtworkOfflineGuard)shinoResearchSetup();}
void loop(){if(shinoArtworkOfflineGuard)shinoResearchLoop();else delay(1000);}
''', encoding='utf-8')
if pilot:
    # This shadow is shared by sequential PIO environments. Always replace
    # the local include, including when switching back from the old graph.
    adapter = previous_dir/'ArtworkAdapter.inc' if previous else project/'native/ArtworkAdapter.inc'
    (shadow/'src/boot/ArtworkAdapter.inc').write_bytes(adapter.read_bytes())
    value = bridge.read_text(encoding='utf-8')
    value = 'void artworkPilotAfterHttp();\n' + value
    value = value.replace('    paintNativeDashboard();', '    // Artwork pilot initializes cooperatively on the loop side.')
    begin = value.index('    if (networkReady &&\n', value.index('void loop()'))
    end = value.index('    m8QualAfterLoop();', begin)
    value = value[:begin] + '    if (networkReady) artworkPilotAfterHttp();\n' + value[end:]
    value += '\n#include "ArtworkAdapter.inc"\n'
    bridge.write_text(value, encoding='utf-8')
    (shadow/'include/project_version.h').write_text('#pragma once\n#define PROJECT_VER_STR "ARTWORK-32-OFFLINE-PILOT"\n', encoding='utf-8')
