"""Offline Phase H source, compiled stream-fault and future-model regressions."""
import ast
import hashlib
import json
import runpy
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
from m9_mount_probe import ROOT, manifest_header, source_gate, future_packet, build_gate
from m9_first_migration import application_extent


class SourceTests(unittest.TestCase):
    def test_source_geometry_default_and_read_only_contract(self):
        self.assertEqual(source_gate()["profile"],2)

    def test_manifest_matches_all_reviewed_payloads_and_blank_seed(self):
        from m9_stage2_fs_candidate import reviewed_source
        files=reviewed_source(ROOT/"firmware/data")
        self.assertEqual(len(files),24)
        self.assertEqual(sum(map(len,files.values())),181402)
        text=manifest_header()
        self.assertEqual((ROOT/"firmware/include/boot/M9ProbeManifest.h").read_text(),text)
        self.assertEqual(json.loads(files["config.json"]),
                         {"api_token":"","wifi_ssid":"","wifi_password":"","lcd_rotation":0})
        for path,payload in files.items():
            self.assertIn(f'"/{path}", {len(payload)}',text)
            self.assertIn(', '.join(f'0x{b:02x}' for b in hashlib.sha256(payload).digest()),text)

    def test_mutations_close_source_gate(self):
        from m9_fsless_gate import inspect_source
        extra=["firmware/platformio.ini","firmware/src/boot/M9LittleFsMountProbe.cpp",
               "firmware/include/boot/M9ProbeManifest.h","firmware/scripts/m9_mount_probe_gate.py"]
        paths=set(inspect_source()["source_sha256"])|set(extra)
        changes=[('LittleFSConfig(false)','LittleFSConfig(true)'),
                 ('LittleFS.open(pin.path, "r")','LittleFS.open(pin.path, "w")'),
                 ('_lfs_cfg.prog = denyProg','_lfs_cfg.prog = lfs_flash_prog'),
                 ('_lfs_cfg.erase = denyErase','_lfs_cfg.erase = lfs_flash_erase'),
                 ('file.isFile()','true'),('file.size() != pin.bytes','false'),
                 ('result.attempted) return','false) return'),
                 ('LittleFS.begin()','LittleFS.begin(); LittleFS.begin()')]
        for old,new in changes:
            with self.subTest(old=old),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                for path in paths:
                    out=root/path;out.parent.mkdir(parents=True,exist_ok=True)
                    out.write_text((ROOT/path).read_text(),encoding="utf-8")
                path=root/'firmware/src/boot/M9LittleFsMountProbe.cpp'
                path.write_text(path.read_text().replace(old,new),encoding="utf-8")
                with self.assertRaises(AssertionError):source_gate(root)

    def test_mount_failure_no_retry_no_repair(self):
        text=(ROOT/'firmware/src/boot/M9LittleFsMountProbe.cpp').read_text()
        self.assertIn('if (!result.mounted) { fail(F("MOUNT")); return; }',text)
        self.assertIn('if (result.attempted) return;',text)
        for bad in ('LittleFS.format(', 'LittleFS.mkdir(', 'LittleFS.remove(', 'ESP.restart('):
            self.assertNotIn(bad,text)
        self.assertIn('bool format() override { return denied(); }',text)
        self.assertIn('return LFS_ERR_IO;',text)

    def test_stream_and_status_have_fixed_bounds(self):
        text=(ROOT/'firmware/include/boot/M9ProbeStream.h').read_text()
        self.assertIn('uint8_t buffer[256]',text)
        self.assertNotIn('new ',text)
        self.assertNotIn('String',text)
        header=(ROOT/'firmware/include/boot/M9LittleFsMountProbe.h').read_text()
        self.assertIn('STATUS_JSON_BYTES = 768',header)
        self.assertIn('sizeof(LittleFsMountProbeStatus) <= 52',header)

    def test_frozen_fs_and_previous_profile_are_not_rebuilt_by_probe(self):
        gate=(ROOT/'firmware/scripts/m9_mount_probe_gate.py').read_text()
        for target in ('upload','uploadfs','buildfs','erase'): self.assertIn(f'"{target}"',gate)
        self.assertNotIn('-DSHINO_BOOT_PROFILE=1',(ROOT/'firmware/platformio.ini').read_text())
        self.assertIn('#if SHINO_BOOT_PROFILE != 2\nConfigManager configManager;',
                      (ROOT/'firmware/src/main.cpp').read_text())

    def test_future_packet_print_only_no_runner(self):
        packet=future_packet();text=json.dumps(packet)
        self.assertFalse(packet['physical_authorization'])
        self.assertFalse(packet['automatic_rollback'])
        self.assertIn('NOT AUTHORIZED BY PHASE H',text)
        self.assertIn('<PORT>',text);self.assertNotIn('erase-all',text)
        self.assertIn('--stub-version 2',text)
        self.assertIn('POST[0x200000:0x3FA000]',text)
        tree=ast.parse((ROOT/'tools/m9_mount_probe.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):
                self.assertFalse({'subprocess','serial','esptool','socket','requests'} &
                                 {x.name for x in node.names})

    def test_probe_build_target_gate_executes_before_any_fs_or_device_target(self):
        script=ROOT/'firmware/scripts/m9_mount_probe_gate.py'
        env=type('Env',(),{'subst':lambda self,_:'esp12e_m9_4m2m_mount_probe',
                          'GetProjectOption':lambda self,_:[]})()
        for target in ('upload','uploadfs','buildfs','erase','program','upload-custom','buildprog'):
            module=types.ModuleType('SCons.Script')
            module.COMMAND_LINE_TARGETS=[target];module.Import=lambda _:None
            with self.subTest(target=target),patch.dict('sys.modules',{'SCons':types.ModuleType('SCons'),'SCons.Script':module}):
                if target=='buildprog':runpy.run_path(str(script),init_globals={'env':env})
                else:
                    with self.assertRaises(RuntimeError):runpy.run_path(str(script),init_globals={'env':env})

    def test_application_extents_cannot_overlap_fs(self):
        self.assertEqual(application_extent(1044464),0xFF000)
        for size in (0,0xFF001,0x100000,0x200000):
            with self.assertRaises(ValueError):application_extent(size)

    def test_future_post_preserves_arena_fs_and_tail_before_boot(self):
        from test_m9_first_migration import candidate_fixture
        from m9_stage1_readback_verify import verify_stage1
        candidate=candidate_fixture();rounded=application_extent(len(candidate))
        before=b'\x31'*0x400000
        after=candidate+b'\xff'*(rounded-len(candidate))+before[rounded:]
        with tempfile.TemporaryDirectory() as tmp:
            app,pre,post=(Path(tmp)/p for p in ('app.bin','pre.bin','post.bin'))
            app.write_bytes(candidate);pre.write_bytes(before);post.write_bytes(after)
            digest=hashlib.sha256(candidate).hexdigest()
            self.assertTrue(verify_stage1(app,pre,post,digest)['protected_byte_exact'])
            for offset in (rounded,0x1FFFFF,0x200000,0x3F9FFF,0x3FA000,0x3FFFFF):
                damaged=bytearray(after);damaged[offset]^=1;post.write_bytes(damaged)
                with self.subTest(offset=offset),self.assertRaises(ValueError):
                    verify_stage1(app,pre,post,digest)


class CompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler=shutil.which('g++') or shutil.which('cl')
        if not cls.compiler:raise RuntimeError('Host C++ compiler required for mount-probe qualification')

    def compile(self,source,root,expect=True):
        cpp=root/'test.cpp';exe=root/'test.exe'
        cpp.write_text(source,encoding='utf-8')
        includes=[root,ROOT/'firmware/include']
        if Path(self.compiler).name.lower()=='cl.exe':
            args=[self.compiler,'/nologo','/std:c++17','/EHsc','/W4','/WX',
                  *[f'/I{p}' for p in includes],str(cpp),f'/Fe:{exe}',f'/Fo:{root}/']
        else:
            args=[self.compiler,'-std=c++17','-Wall','-Wextra','-Werror',
                  *[f'-I{p}' for p in includes],str(cpp),'-o',str(exe)]
        result=subprocess.run(args,cwd=root,capture_output=True,text=True)
        self.assertEqual(result.returncode==0,expect,result.stdout+result.stderr)
        if expect: subprocess.run([str(exe)],check=True,cwd=root)

    def test_compile_profile_allowlist_and_explicit_opt_in(self):
        for profile,optin,ok in [(0,False,True),(1,False,False),(2,False,False),
                                  (2,True,True),(3,True,False),(0,True,False)]:
            with self.subTest(profile=profile,optin=optin),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                (root/'shino_private_policy.h').write_text(f'#define SHINO_BOOT_PROFILE {profile}\n')
                source=('#define SHINO_M9_MOUNT_PROBE 1\n' if optin else '')
                source+='#include "boot/ShinoBootProfile.h"\nint main(){return 0;}\n'
                self.compile(source,root,ok)

    def test_actual_stream_algorithm_fault_matrix(self):
        source=r'''
#include "boot/M9ProbeStream.h"
#include <cassert>
#include <vector>
#include <algorithm>
struct Reader {
    std::vector<uint8_t> bytes; size_t offset=0, quantum=256; int fault=0;
    int read(uint8_t* out,size_t n) {
        if(fault==1)return -1;
        if(fault==2)return 0;
        if(fault==3)return static_cast<int>(n+1);
        n=std::min(n,std::min(quantum,bytes.size()-offset));
        for(size_t i=0;i<n;++i)out[i]=bytes[offset++];
        return static_cast<int>(n);
    }
    int read(){return offset==bytes.size()?-1:bytes[offset++];}
};
// Deterministic fake hash isolates streaming/error handling. Target SHA256
// adapter is real pinned BearSSL and compiled by the ESP8266 build.
struct Hash {
    uint8_t h[32]; size_t offset;
    void begin(){std::memset(h,0,32);offset=0;}
    void update(const void* p,size_t n){auto b=static_cast<const uint8_t*>(p);
        for(size_t i=0;i<n;++i)h[(offset++)%32]^=b[i];}
    void end(uint8_t* out){std::memcpy(out,h,32);}
};
int main(){
    std::vector<uint8_t> payload(8193);for(size_t i=0;i<payload.size();++i)payload[i]=static_cast<uint8_t>(i*17);
    Hash reference;reference.begin();reference.update(payload.data(),payload.size());uint8_t expected[32];reference.end(expected);
    auto seed=[](uint32_t,const uint8_t*,size_t){return true;};
    for(size_t quantum : {size_t(1),size_t(7),size_t(256)}) {
        Reader reader{payload,0,quantum,0};M9ProbeStream::Workspace<Hash> hash;uint32_t checked=0;size_t samples=0;
        assert(M9ProbeStream::validate(reader,8193,expected,hash,seed,[&](){++samples;},checked));
        assert(checked==8193 && samples>0);
    }
    for(int fault=0;fault<7;++fault){
        Reader reader{payload,0,256,0};M9ProbeStream::Workspace<Hash> hash;uint32_t checked=0;
        if(fault<3)reader.fault=fault+1;
        if(fault==3)reader.bytes.pop_back();
        if(fault==4)reader.bytes.push_back(0);
        if(fault==5)reader.bytes[0]^=1;
        auto seedCheck=[fault](uint32_t,const uint8_t*,size_t){return fault!=6;};
        assert(!M9ProbeStream::validate(reader,8193,expected,hash,seedCheck,[](){},checked));assert(checked==0 && !hash.active);
    }
    const uint8_t canonical[]={0,1,2,3};Hash h;h.begin();h.update(canonical,4);h.end(expected);
    for(bool corrupt : {false,true}){
        Reader reader{{0,1,2,3},0,1,0};if(corrupt)reader.bytes[2]=9;
        auto exactSeed=[&](uint32_t off,const uint8_t* p,size_t n){return std::memcmp(p,canonical+off,n)==0;};
        uint32_t checked=0;M9ProbeStream::Workspace<Hash> hash;
        assert(M9ProbeStream::validate(reader,4,expected,hash,exactSeed,[](){},checked)==!corrupt);
    }
}
'''
        with tempfile.TemporaryDirectory() as tmp:self.compile(source,Path(tmp))

if __name__=='__main__':unittest.main()
