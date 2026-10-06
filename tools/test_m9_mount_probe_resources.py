"""Phase J deterministic observer/serializer/profile and read-only regression proof."""
from pathlib import Path
import ast
import json
import runpy
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
from m9_mount_probe_resources import ROOT, source_gate, future_packet


class SourceTests(unittest.TestCase):
    def test_paired_budgets_and_individual_frame_fail_closed(self):
        from m9_mount_probe_resources import paired_build
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/'a.txt';b=root/'b.txt';old=root/'old';new=root/'new'
            old.mkdir();new.mkdir()
            def sections(ram,flash):return f'.data 0 0\n.rodata 0 0\n.bss {ram} 0\n.noinit 56 0\n.text 0 0\n.text1 0 0\n.irom0.text {flash} 0\n'
            a.write_text(sections(40652,403283));b.write_text(sections(40736,406995))
            (old/'main.cpp.su').write_text('main.cpp:1:1:void setup()\t32\tstatic\n')
            frame=new/'M9MountProbeResources.cpp.su'
            frame.write_text('resource.cpp:1:1:bool sendStatus()\t944\tstatic\n')
            report=paired_build(a,b,old,new)
            self.assertEqual(report['delta']['static_ram_bytes'],84)
            for ram,flash,size in [(40652+513,406995,944),(40736,403283+8193,944),(40736,406995,1025)]:
                b.write_text(sections(ram,flash));frame.write_text(f'resource.cpp:1:1:bool sendStatus()\t{size}\tstatic\n')
                with self.subTest(ram=ram,flash=flash,size=size),self.assertRaises(AssertionError):paired_build(a,b,old,new)

    def test_resource_api_source_pins_reject_mutation(self):
        from m9_mount_probe_resources import core_gate
        allpins={**json.loads((ROOT/'tools/m9_mount_probe_sources.json').read_text()),
                 **json.loads((ROOT/'tools/m9_resource_core_sources.json').read_text())}
        # A changed resource API must fail before any device use; no SDK heuristic fallback.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'package.json').write_text('{"version":"3.30102.0"}',encoding='utf-8')
            for path in allpins:
                target=root/path;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text('MUTATED PINNED SOURCE',encoding='utf-8')
            with patch('m9_mount_probe.core_gate',return_value={}),self.assertRaises(AssertionError):
                core_gate(root) # Isolate the additional resource pins from the independent FS audit.

    def test_original_behavior_pins_and_explicit_observation_placement(self):
        report=source_gate()
        self.assertEqual(report['PHYSICAL_RESOURCE_THRESHOLD'],'REVIEW_REQUIRED')
        self.assertEqual(report['MOUNT_PROBE_PHYSICAL_GATE'],'PARTIAL / HOLD')

    def test_boundary_cadence_and_writer_mutations_fail_gate(self):
        pins=json.loads((ROOT/'tools/m9_resource_baseline_sources.json').read_text())
        paths=set(pins['sha256_lf'])|{
            'firmware/platformio.ini','firmware/include/boot/ShinoBootProfile.h',
            'firmware/include/boot/HomeLan.h','firmware/src/config/ConfigManager.cpp',
            'firmware/src/config/SecureStorage.cpp','firmware/src/display/DisplayManager.cpp',
            'firmware/src/recovery/FactoryRollback.cpp','firmware/scripts/m9_mount_probe_gate.py',
            'firmware/include/boot/M9ResourceObserver.h','firmware/include/boot/M9ResourceJson.h',
            'firmware/src/boot/M9MountProbeResources.cpp'}
        mutations=[('firmware/include/boot/M9ResourceObserver.h','< 1000','< 100'),
                   ('firmware/src/main.cpp','M9MountProbeResources::afterMount();','M9MountProbeResources::beforeMount();'),
                   ('firmware/src/boot/M9LittleFsMountProbe.cpp','LittleFSConfig(false)','LittleFSConfig(true)'),
                   ('firmware/src/boot/M9MountProbeResources.cpp','observer.status()','observer.poll()'),
                   ('firmware/src/boot/M9MountProbeResources.cpp','void poll() { observer.poll(); }',
                    'void poll() { ESP.flashWrite(0, nullptr, 0); observer.poll(); }'),
                   ('firmware/include/boot/M9ResourceObserver.h','lastAttemptMs_ = now;','lastAttemptMs_ += 1000;')]
        for path,old,new in mutations:
            with self.subTest(old=old),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                for name in paths:
                    target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_text((ROOT/name).read_text(encoding='utf-8'),encoding='utf-8')
                target=root/path;target.write_text(target.read_text(encoding='utf-8').replace(old,new),encoding='utf-8')
                with self.assertRaises(AssertionError):source_gate(root)

    def test_original_read_only_begin_inventory_and_telemetry_pinned(self):
        from m9_mount_probe_resources import uninstrumented_source
        pins=json.loads((ROOT/'tools/m9_resource_baseline_sources.json').read_text())
        import hashlib
        for path,expected in pins['sha256_lf'].items():
            restored=uninstrumented_source(path,(ROOT/path).read_text(encoding='utf-8'))
            self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(),expected,path)

    def test_target_gate_both_environment_flags_and_no_device_targets(self):
        script=ROOT/'firmware/scripts/m9_mount_probe_gate.py'
        for name,flag in [('esp12e_m9_4m2m_mount_probe',False),('esp12e_m9_4m2m_mount_probe_resources',True)]:
            env=type('Env',(),{'subst':lambda self,_,name=name:name,
                'GetProjectOption':lambda self,_,flag=flag:['-DSHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS=1'] if flag else []})()
            for target in ('buildprog','upload','uploadfs','buildfs','erase','program','upload-anything'):
                module=types.ModuleType('SCons.Script');module.COMMAND_LINE_TARGETS=[target];module.Import=lambda _:None
                with patch.dict('sys.modules',{'SCons.Script':module}):
                    if target=='buildprog':runpy.run_path(str(script),init_globals={'env':env})
                    else:
                        with self.assertRaises(RuntimeError):runpy.run_path(str(script),init_globals={'env':env})
            wrong=type('Env',(),{'subst':lambda self,_,name=name:name,
                'GetProjectOption':lambda self,_,flag=flag:[] if flag else ['-DSHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS=1']})()
            module.COMMAND_LINE_TARGETS=['buildprog']
            with patch.dict('sys.modules',{'SCons.Script':module}),self.assertRaises(RuntimeError):
                runpy.run_path(str(script),init_globals={'env':wrong})

    def test_future_packet_print_only_and_no_executor(self):
        p=future_packet();self.assertFalse(p['physical_authorization']);self.assertFalse(p['automatic_rollback'])
        text=json.dumps(p)
        for required in ('NOT AUTHORIZED BY PHASE J','<EXACT_RESOURCE_PROBE_BIN>','rounded_candidate_end','REVIEW_REQUIRED','GPIO0 LOW','180-second'):
            self.assertIn(required,text)
        tree=ast.parse((ROOT/'tools/m9_mount_probe_resources.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                self.assertFalse({'subprocess','serial','esptool','socket','requests'} & {x.name for x in node.names})


class CompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler=shutil.which('g++') or shutil.which('cl')
        if not cls.compiler:raise RuntimeError('Host C++ compiler required; no skipped resource qualification')

    def compile(self,source,root,expect=True):
        cpp=root/'test.cpp';exe=root/'test.exe';cpp.write_text(source,encoding='utf-8')
        includes=[root,ROOT/'firmware/include']
        if Path(self.compiler).name.lower()=='cl.exe':
            args=[self.compiler,'/nologo','/std:c++17','/EHsc','/W4','/WX',*[f'/I{p}' for p in includes],str(cpp),f'/Fe:{exe}',f'/Fo:{root}/']
        else:
            args=[self.compiler,'-std=c++17','-Wall','-Wextra','-Werror',*[f'-I{p}' for p in includes],str(cpp),'-o',str(exe)]
        result=subprocess.run(args,cwd=root,capture_output=True,text=True)
        self.assertEqual(result.returncode==0,expect,result.stdout+result.stderr)
        if expect:return subprocess.check_output([str(exe)],cwd=root,text=True)
        return ''

    def test_profile_allowlist_including_resource_flag_fail_closed(self):
        for profile,probe,resource,ok in [(0,0,0,True),(1,0,0,False),(2,1,0,True),
                (2,1,1,True),(2,0,1,False),(0,0,1,False),(2,1,2,False),(3,1,1,False)]:
            with self.subTest(profile=profile,resource=resource),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'shino_private_policy.h').write_text(f'#define SHINO_BOOT_PROFILE {profile}\n')
                source=f'#define SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS {resource}\n'
                if probe:source+='#define SHINO_M9_MOUNT_PROBE 1\n'
                self.compile(source+'#include "boot/ShinoBootProfile.h"\nint main(){return 0;}\n',root,ok)

    def test_actual_observer_two_windows_cadence_wrap_and_invalid_values(self):
        source=r'''
#include "boot/M9ResourceObserver.h"
#include <cassert>
#include <vector>
#include <string>
using namespace M9MountProbeResources;
struct Fake {
    uint32_t time=0, margin=3800; Heap value{36000,35000,2};
    unsigned resets=0, reads=0; std::vector<std::string> calls;
    void resetStack(){++resets;calls.push_back("reset");margin=3800;}
    uint32_t stack(){calls.push_back("stack");return margin;}
    void heap(Heap& out){++reads;calls.push_back("heap");out=value;}
    uint32_t now(){calls.push_back("now");return time;}
};
int main(){
    Fake f;Observer<Fake> o(f);o.poll();o.afterMount();assert(f.calls.empty());
    o.beforeMount();o.beforeMount();assert(f.resets==1 && f.calls==std::vector<std::string>({"reset","stack"}));
    f.margin=1800;o.afterMount();o.afterMount();
    assert(f.calls==std::vector<std::string>({"reset","stack","stack","heap","reset","stack","now"}));
    assert(f.resets==2 && o.status().mount_phase_cont_stack_start==3800 && o.status().mount_phase_cont_stack_min_free==1800);
    assert(o.status().runtime_cont_stack_start==3800 && o.status().resource_measurements_valid);
    f.time=999;o.poll();assert(f.reads==1 && o.status().resource_sample_count==0);
    f.time=1000;f.margin=1700;o.poll();assert(f.reads==2 && o.status().resource_sample_count==1);
    for(int i=0;i<100;++i){o.poll();}assert(f.reads==2);
    f.time=10000;f.margin=0;f.value={32000,20000,30};o.poll();o.poll();
    assert(f.resets==2 && o.status().resource_sample_count==2 && o.status().runtime_min_cont_stack_free==0);
    assert(o.status().lowest_observed_free_heap==32000 && o.status().lowest_observed_largest_free_block==20000 && o.status().highest_observed_fragmentation_percent==30);
    const Heap invalids[]={{0,0,0},{81921,100,0},{20000,0,0},{20000,20001,0},{20000,1000,101}};
    for(const auto& v:invalids){f.value=v;f.time+=1000;o.poll();}
    assert(o.status().resource_sample_count==2 && o.status().resource_rejected_sample_count==5);
    assert(o.status().latest.free==32000 && !o.status().resource_measurements_valid);
    f.value={30000,18000,32};f.time+=1000;o.poll();assert(o.status().resource_sample_count==3 && !o.status().resource_measurements_valid);
    assert(f.resets==2);
    Fake wrap;wrap.time=UINT32_MAX-500;Observer<Fake> w(wrap);w.beforeMount();w.afterMount();
    wrap.time=498;w.poll();assert(w.status().resource_sample_count==0);
    wrap.time=499;w.poll();assert(w.status().resource_sample_count==1);
    Fake bad;Observer<Fake> b(bad);b.beforeMount();bad.margin=4097;bad.value={10000,20000,0};b.afterMount();
    assert(!b.status().resource_measurements_valid && b.status().resource_rejected_sample_count==2 && b.status().heap_after_probe.free==0);
    bad.time=1000;bad.margin=3;b.poll();assert(b.status().resource_sample_count==0);
}
'''
        with tempfile.TemporaryDirectory() as tmp:self.compile(source,Path(tmp))

    def test_actual_json_worst_case_bounds_overflow_and_cached_only(self):
        source=r'''
#include "boot/M9ResourceJson.h"
#include <cassert>
#include <iostream>
#include <string>
using namespace M9MountProbeResources;
struct Sink {
    size_t declared=0;unsigned calls=0;std::string body;
    void begin(size_t n){declared=n;++calls;}
    void write(const char* p,size_t n){body.append(p,n);++calls;}
};
int main(){
    Observation s{};
    s.mount_phase_cont_stack_start=s.mount_phase_cont_stack_min_free=UINT32_MAX;
    s.heap_after_probe={UINT32_MAX,UINT32_MAX,255};
    s.runtime_cont_stack_start=s.runtime_min_cont_stack_free=s.resource_sample_count=UINT32_MAX;
    s.latest=s.heap_after_probe;s.lowest_observed_free_heap=s.lowest_observed_largest_free_block=UINT32_MAX;
    s.highest_observed_fragmentation_percent=255;s.resource_rejected_sample_count=UINT32_MAX;
    char full[JSON_CHUNK_BYTES];size_t n=0;assert(suffix(s,full,sizeof(full),n));assert(n==SUFFIX_MAX_BYTES);
    for(size_t capacity=0;capacity<=n;++capacity){char b[JSON_CHUNK_BYTES];size_t rejected=99;
        assert(!suffix(s,b,capacity,rejected));assert(rejected==0);}
    size_t same=0;char exact[JSON_CHUNK_BYTES];assert(suffix(s,exact,n+1,same) && same==n);
    Sink sink;assert(emit(s,"{\"mounted\":true}",16,sink));assert(sink.calls==3 && sink.declared==sink.body.size());
    const std::string before=sink.body;assert(emit(s,"{\"mounted\":true}",16,sink));
    Sink fail;assert(!emit(s,"broken",6,fail) && fail.calls==0);
    std::cout<<before<<"\n"<<SUFFIX_MAX_BYTES<<"\n";
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            lines=self.compile(source,Path(tmp)).splitlines()
            values=json.loads(lines[0]);bound=int(lines[1])
            self.assertTrue(values['mounted']);self.assertTrue(values['resource_diagnostics_enabled'])
            self.assertFalse(values['resource_measurements_valid'])
            self.assertEqual(values['resource_sample_count'],0xFFFFFFFF)
            worst={key:(255 if 'fragmentation' in key else
                        False if isinstance(value,bool) and key=='resource_measurements_valid' else
                        True if isinstance(value,bool) else 0xFFFFFFFF) for key,value in values.items() if key!='mounted'}
            self.assertEqual(len(json.dumps(worst,separators=(',',':'))),bound)

if __name__=='__main__':unittest.main()
