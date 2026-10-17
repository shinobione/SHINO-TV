"""Phase T public source closure, retaining all previous frozen source gates."""
import hashlib,json,subprocess
from pathlib import Path
from m9_signed_ota_runner import source_gate as signed_gate
from v07_pinned_core_probe import core_root
ROOT=Path(__file__).resolve().parents[1]

def run():
    from b52_source_compat import NEW_FILE_BLOBS, SCENE, predecessor
    from link_m2_source_identity import LINK_M2_FILE_BLOBS, LINK_PATH, reviewed_link_predecessor
    previous=signed_gate();core=core_root()
    pins=json.loads((ROOT/'tools/m9_stagea_core_sources.json').read_text())
    for name,digest in pins.items():
        assert hashlib.sha256((core/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==digest,name
    # New local-only wrappers retain an explicit exact-content blob pin.
    # All historical source identities below remain unchanged.
    new_offline_script_pins = {
        'companion/SHINO-OWNER-TRANSITION.cmd': '5d5bacb18ac43b1217a05171e1e26bcd25bd1daa',
        'companion/SHINO-TRANSITION-CHECK.cmd': 'f6785c16885c0cfcd83ac58f5c857c1a6f122ed4',
        # New HTTP OTA product files are separate from the frozen StageA graph.
        'companion/SHINO-UPDATE.cmd': '43902cd1e0bdab70495beedfbd76205ddc8b93c8',
        'companion/shino_update.py': '0e266c515b34b652d81b1eb5121c3ac01fd66fb0',
        'companion/shino_qualify.py': '69992a082d06b93c4a2b94ab1be14fb4c07c890a',
        'companion/test_shino_update.py': 'd1afe393073c1baaad60c36093f20a33375a46a9',
        'companion/SHINO-ONE-SHOT-B.ps1': '197ab9b8f71133fb27d8931a849eb6f5aff10d3a',
        # Deliberate PC-only LINK update, exact Git blob; no wildcard exemption.
        'companion/shino_link.py': '3d09d7593d13a7ab52d4efc51e24e00e909810a9',
        # Explicit 11 October owner mandate: Windows coordination only.
        # Exact blobs; historical qualifier/capture/firmware pins stay frozen.
        'companion/shino_digest_coord.py': '494a7ed15c6150ed43adc292d9a7c79386917123',
        'companion/shino_coordinated_qualify.py': 'fd148d081813cb1a66447e18f362a888f2b3aedb',
        'companion/test_shino_http_coordination.py': '046261f647b901d36ad97b57baea692f8bb78c22',
        # Exact Git blob pins for B3 owner-only read-only evidence files.
        'companion/shino_b3_capture.py': '98a7e39f19d7917b2029f2b8ab393615f1478cf1',
        'companion/test_shino_b3_capture.py': 'de17954a836e566e51c5ee18c1b1bf7fc185facd',
        'companion/SHINO_B3_READONLY_CAPTURE.md': 'f0a17dcad31872ab0f90286871aa1b04df35fdb6',
        # 13 October owner documentary/code freeze: new offline B5 tools only.
        # Exact reviewed Git blobs; all historical deployed-source pins remain.
        'companion/shino_b5_get_diagnostic.py': '16a036896fac1b676328888313c516e2c3507f8d',
        'companion/test_shino_b5_get_diagnostic.py': '07bc1cfc28904206674389c896d1504cd90281d2',
        'companion/shino_b5_partial_preflight.py': 'c4b950a08a6d498a01fa49d86e75f48e3e3c0cc6',
        'companion/test_shino_b5_partial_preflight.py': '84adec2c7ce3ad49c9b0424afaa94af082019cb2',
    }
    new_offline_script_pins.update(NEW_FILE_BLOBS)
    # M1/M2 are new PC-only sources; exact Git blobs, never wildcard bypasses.
    # M2 LINK is also reconstructed against its immutable B5.2 predecessor.
    new_offline_script_pins.update(LINK_M2_FILE_BLOBS)
    # The verifier is new tooling outside the legacy firmware/companion set.
    # Anchor its exact bytes too; otherwise editing it could weaken the gate.
    verifier_blob = subprocess.check_output(
        ["git", "hash-object", "--", "tools/link_m2_source_identity.py"],
        cwd=ROOT, text=True,
    ).strip()
    assert verifier_blob == "959ee3c0de07a145f9a4654677c1c5cdf20be8f3", "M2 source verifier changed"
    for name in subprocess.check_output(['git','ls-files','firmware','companion','tools/m9_single_attempt*'],cwd=ROOT,text=True).splitlines():
        if name in new_offline_script_pins:
            digest=subprocess.check_output(['git','hash-object','--',name],cwd=ROOT,text=True).strip()
            assert digest==new_offline_script_pins[name],name
            if name == LINK_PATH:
                reviewed_link_predecessor((ROOT/name).read_bytes().replace(b'\r\n', b'\n'))
            continue
        # Explicit new issue43 installer files; old transport identities stay pinned.
        # The B2 diagnostic scripts were introduced *after* this pinned
        # signed/StageA baseline. They are PC read-only observability and
        # have no deployed firmware, rescue, serial or OTA writer authority.
        # Only these two exact paths are exempt; all historical source
        # identities below are still compared byte-for-byte.
        if name in ('companion/shino_http_observe.py',
                    'companion/test_shino_http_observe.py'):
            continue
        # New Windows-side Digest coordination and alternative qualifier
        # added after the historic signed/StageA freeze. Do not exempt any
        # historical firmware or physical updater path.
        if name in ('companion/shino_digest_coord.py',
                    'companion/test_shino_digest_coord.py',
                    'companion/shino_coordinated_qualify.py',
                    'companion/test_shino_coordinated_qualify.py'):
            continue
        if name in ('companion/shino_install.py','companion/test_shino_install.py','companion/SHINO-INSTALL.cmd','companion/SHINO_INSTALL.md','companion/SHINO-OFFLINE-CHECK.cmd','companion/shino_maintenance_control.py','companion/test_shino_maintenance_control.py'):
            continue
        original=subprocess.check_output(['git','show','b59964af43b555b75d415e6d063580945e6d99f7:'+name],cwd=ROOT)
        actual=(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
        if name == SCENE:
            actual=predecessor(name,actual.decode('utf-8')).encode('utf-8')
        assert actual==original.replace(b'\r\n',b'\n'),name
    stage=(ROOT/'firmware/src/boot/M9NormalStageA.cpp').read_text()
    assert 'M9StageAHttp' not in stage and 'setStageARawHook' not in stage
    graph=(ROOT/'experiments/m9_stagea_ota/include/M9StageALink.inc').read_text()
    assert 'retainedStageAProof' in graph and 'retainedStageAPump' in graph
    for bad in ('end(true)','ESP.restart','ESP.reset(','Update.','installSignature(nullptr','private.key','PUBLIC-INERT','BEGIN PRIVATE'):
        assert bad not in graph,bad
    files=[*sorted((ROOT/'experiments/m9_stagea_ota').rglob('*')),*sorted((ROOT/'tools').glob('m9_stagea*'))]
    return dict(PHASE_T_SOURCE='PASS_OFFLINE',previous=previous,additional_core_LF_pins=len(pins),
        deployed_source_identity='b59964af43b555b75d415e6d063580945e6d99f7',default_stagea_ota=False,
        source_identity_scope='PINNED_PREDECESSOR_PROJECTION_NOT_RAW_CURRENT_EQUALITY',
        composition_LF_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in files if p.is_file()},
        device_contacts=0,serial_io=0,flash_writes=0,rtc_writes=0,reboots=0,device_filesystem_writes=0)

if __name__=='__main__':print(json.dumps(run(),indent=2))
