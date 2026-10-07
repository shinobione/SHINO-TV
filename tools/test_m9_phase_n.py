"""Actual StageA algorithms/callbacks/routes; local fake hardware only."""
from pathlib import Path
import hashlib, json, runpy, types, tempfile, unittest
from unittest.mock import patch
from m9_phase_n_qualification import ROOT, ENV, source_gate
from test_m9_mount_probe import CompiledTests as Compiler

class SourceTests(unittest.TestCase):
    def test_current_stage_a_and_historical_projection(self):
        self.assertEqual(source_gate()['PHASE_N_SOURCE_GATE'],'PASS/OFFLINE')

    def test_target_guard_variants_environment_linker_and_exact_flags(self):
        script=ROOT/'firmware/scripts/m9_normal_qualification_gate.py'
        good={'build_flags':['-DSHINO_BOOT_PROFILE=1','-DSHINO_M9_NORMAL_QUALIFICATION=1'],
              'board_build.ldscript':'eagle.flash.4m2m.ld'}
        env=type('Env',(),{'subst':lambda self,_:ENV,'GetProjectOption':lambda self,key:good[key]})()
        module=types.ModuleType('SCons.Script');module.Import=lambda _:None
        for target in ('buildprog','upload','uploadfs','buildfs','erase','program','UPLOADFS','erase_flash','program-app','prebuildfs','upload-anything'):
            module.COMMAND_LINE_TARGETS=[target]
            with patch.dict('sys.modules',{'SCons.Script':module}):
                if target=='buildprog':runpy.run_path(str(script),init_globals={'env':env})
                else:
                    with self.assertRaises(RuntimeError):runpy.run_path(str(script),init_globals={'env':env})
        module.COMMAND_LINE_TARGETS=['buildprog']
        for bad in ([],['-DSHINO_BOOT_PROFILE=0','-DSHINO_M9_NORMAL_QUALIFICATION=1'],
                    ['-DSHINO_BOOT_PROFILE=1','-DSHINO_M9_NORMAL_QUALIFICATION=1','-DSHINO_M9_NORMAL_QUALIFICATION=0']):
            with patch.dict('sys.modules',{'SCons.Script':module}),patch.dict(good,{'build_flags':bad}),self.assertRaises(RuntimeError):
                runpy.run_path(str(script),init_globals={'env':env})
        with patch.dict('sys.modules',{'SCons.Script':module}),patch.dict(good,{'board_build.ldscript':'eagle.flash.4m3m.ld'}),self.assertRaises(RuntimeError):
            runpy.run_path(str(script),init_globals={'env':env})

    def test_installed_freeze_and_writer_are_unchanged_reject_normal_identity(self):
        import m9_single_attempt_app_write as writer
        self.assertEqual(writer.FROZEN_SHA256,'e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e')
        with self.assertRaises(writer.WriteError):writer.candidate(Path('not-opened.bin'),'0'*64)
        local=ROOT/'research-local/m9-mount-stack/frozen-successor-resource-probe.bin'
        if local.exists():
            self.assertEqual(local.stat().st_size,writer.FROZEN_BYTES)
            self.assertEqual(hashlib.sha256(local.read_bytes()).hexdigest(),writer.FROZEN_SHA256)
        pins=json.loads((ROOT/'tools/m9_mount_stack_sources.json').read_text())
        for name,digest in pins['unchanged_tool_sha256_lf'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),digest)

class NativeTests(Compiler):
    # Do not duplicate predecessor compiler tests inherited from its fixture.
    test_compile_profile_allowlist_and_explicit_opt_in=None
    test_actual_stream_algorithm_fault_matrix=None

    def test_profile_one_exact_optin_matrix(self):
        for profile,flag,ok in [(1,None,False),(1,0,False),(1,1,True),(1,2,False),(0,1,False),(2,1,False),(0,None,True)]:
            with self.subTest(profile=profile,flag=flag),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'shino_private_policy.h').write_text(f'#define SHINO_BOOT_PROFILE {profile}\n')
                source=(f'#define SHINO_M9_NORMAL_QUALIFICATION {flag}\n' if flag is not None else '')
                self.compile(source+'#include "boot/ShinoBootProfile.h"\nint main() {}\n',root,ok)

    def test_actual_config_reader_short_reads_mutations_and_eof(self):
        source=r'''
#include "boot/M9StageAConfig.h"
#include <cassert>
#include <algorithm>
#include <cstring>
#include <string>
const char seed[]="{\n  \"api_token\": \"\",\n  \"lcd_rotation\": 0,\n  \"wifi_password\": \"\",\n  \"wifi_ssid\": \"\"\n}\n";
struct Reader {
    std::string data=seed;size_t offset=0,quantum=32,advertised=85;int fault=0;size_t calls=0;
    size_t size(){return advertised;}
    size_t read(uint8_t* out,size_t wanted){assert(wanted<=32);++calls;
        if(fault==1)return 0;if(fault==2)return wanted+1;
        size_t n=std::min(wanted,std::min(quantum,data.size()-offset));
        std::memcpy(out,data.data()+offset,n);offset+=n;return n;}
    int read(){return offset==data.size()?-1:static_cast<uint8_t>(data[offset++]);}
};
int main(){
    auto expected=[](size_t i){return static_cast<uint8_t>(seed[i]);};
    for(size_t q:{size_t(1),size_t(7),size_t(32)}){Reader r;r.quantum=q;assert(M9StageAConfig::validate(r,expected));}
    for(size_t i=0;i<85;++i){Reader r;r.data[i]^=1;assert(!M9StageAConfig::validate(r,expected));}
    for(int f:{1,2}){Reader r;r.fault=f;assert(!M9StageAConfig::validate(r,expected));}
    Reader big;big.advertised=86;assert(!M9StageAConfig::validate(big,expected)&&big.calls==0);
    Reader extra;extra.data+='x';assert(!M9StageAConfig::validate(extra,expected));
    Reader shortread;shortread.data.resize(84);assert(!M9StageAConfig::validate(shortread,expected));
}
'''
        with tempfile.TemporaryDirectory() as tmp:self.compile(source,Path(tmp))

    def test_actual_resource_windows_minima_rejections_cadence_wrap_and_floors(self):
        source=r'''
#include "boot/M9NormalResources.h"
#include <cassert>
using namespace M9NormalResources;
struct Fake {
    uint32_t time=0,margin=4000;unsigned resets=0,reads=0;Heap value{32000,30000,1};
    void resetStack(){++resets;margin=4000;}
    uint32_t stack(){++reads;return margin;}
    uint32_t now(){return time;}
    void heap(Heap& out){out=value;}
};
int main(){
    Fake f;Observer<Fake> o(f);o.beforeSetup();o.beforeSetup();f.margin=2800;o.beforeFs();
    f.margin=2600;f.value={30000,24000,8};o.afterFs();f.margin=3000;o.afterSetup();
    assert(f.resets==4&&o.status().setup_min==2600&&o.status().fs_min==2600&&o.status().runtime_start==4000);
    f.time=999;o.poll();assert(o.status().samples==0&&!floors(o.status()));
    f.time=1000;f.margin=2400;f.value={28000,22000,12};o.poll();assert(o.status().samples==1&&floors(o.status()));
    f.time=2000;f.margin=2300;f.value={31000,25000,7};o.poll();
    assert(o.status().samples==2&&o.status().min_heap==28000&&o.status().min_block==22000&&o.status().max_frag==12);
    f.time=3000;f.margin=2400;o.poll();assert(o.status().samples==2&&o.status().rejected==1&&!o.status().valid);
    f.time=4000;f.margin=2200;o.poll();assert(o.status().samples==3&&!o.status().valid&&!floors(o.status()));
    f.time=5000;f.value={20000,20001,101};o.poll();assert(o.status().samples==3&&o.status().rejected==2);
    assert(f.resets==4);
    Fake wrap;wrap.time=UINT32_MAX-500;Observer<Fake> w(wrap);w.beforeSetup();w.beforeFs();w.afterFs();w.afterSetup();
    wrap.time=498;w.poll();assert(w.status().samples==0);wrap.time=499;w.poll();assert(w.status().samples==1);
    Fake low;Observer<Fake> l(low);l.beforeSetup();low.margin=0;l.beforeFs();l.afterFs();l.afterSetup();
    low.time=1000;l.poll();assert(l.status().valid&&l.status().setup_min==0&&!floors(l.status()));
}
'''
        with tempfile.TemporaryDirectory() as tmp:self.compile(source,Path(tmp))

    def test_actual_prebody_policy_route_and_length_matrix(self):
        source=r'''
#include "boot/M9NormalHttpPolicy.h"
#include <cassert>
#include <initializer_list>
using namespace M9NormalHttpPolicy;
int main(){
    const char* route="/api/v1/bridge/metrics";
    assert(classify(true,false,"/status","","","")==200);
    for(const char* path:{"/config.json","/web/../config.json","/%2e%2e/config.json","/api/reboot","/api/v1/media/image","/api/v1/ota"})
        assert(classify(true,false,path,"","","")==404&&classify(false,true,path,"32","application/json","")==404);
    assert(classify(false,true,route,"16","application/json","")==200);
    assert(classify(false,true,route,"384","application/json","")==200);
    for(const char* size:{"","0","15","385","-1","4294967296","12junk"})
        assert(classify(false,true,route,size,"application/json","")==413);
    assert(classify(false,true,route,"32","multipart/form-data","")==415);
    assert(classify(false,true,route,"32","application/json","chunked")==400);
}
'''
        with tempfile.TemporaryDirectory() as tmp:self.compile(source,Path(tmp))

    def test_actual_status_worst_case_capacity_json_and_privacy(self):
        source=r'''
#include "boot/M9NormalStatusJson.h"
#include <cassert>
#include <iostream>
#include <string>
struct Sink{size_t length=0;std::string body;void begin(size_t n){length=n;}void write(const char* p,size_t n){body.append(p,n);}};
int main(){
    M9NormalResources::Observation r;
    r.setup_start=r.setup_min=r.fs_start=r.fs_min=r.runtime_start=r.runtime_min=r.samples=r.rejected=r.min_heap=r.min_block=UINT32_MAX;
    r.after_fs=r.after_setup=r.latest={UINT32_MAX,UINT32_MAX,255};r.max_frag=255;
    M9LittleFsMountProbe::LittleFsMountProbeStatus f;f.checked_file_count=65535;f.checked_payload_bytes=f.blocked_write_attempts=UINT32_MAX;
    M9NormalStatusJson::Snapshot s{r,f,false,false};
    for(unsigned i=0;i<4;++i){char b[512];int n=M9NormalStatusJson::part(b,sizeof(b),i,s);assert(n>0&&n<512);
        for(size_t c=0;c<=size_t(n);++c)assert(M9NormalStatusJson::part(b,c,i,s)>=int(c));}
    Sink sink;assert(M9NormalStatusJson::emit(s,sink)&&sink.length==sink.body.size());std::cout<<sink.body;
}
'''
        # Compiler fixture runs the executable; capture once for semantic parsing.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.compile(source,root)
            import subprocess
            status=json.loads(subprocess.check_output([str(root/'test.exe')],text=True))
            self.assertEqual(status['boot_profile'],1)
            self.assertFalse(status['native_ota_writer_enabled'])
            text=json.dumps(status).lower()
            for bad in ('password','mac_address','saved_ssid','private_path','token_value'):self.assertNotIn(bad,text)

    def test_actual_readonly_adapter_all_mutation_callbacks(self):
        body=(ROOT/'firmware/src/boot/M9LittleFsMountProbe.cpp').read_text()
        adapter=body.split('class ReadOnlyImpl final')[1].split('static_assert(sizeof(ReadOnlyImpl)')[0]
        source=r'''
#include <cassert>
#include <cstdint>
#include <memory>
using lfs_block_t=uint32_t;using lfs_off_t=uint32_t;using lfs_size_t=uint32_t;
constexpr int LFS_ERR_IO=-5,FS_PHYS_ADDR=0,FS_PHYS_SIZE=0,FS_PHYS_PAGE=0,FS_PHYS_BLOCK=0;
enum OpenMode{OM_DEFAULT,OM_WRITE};enum AccessMode{AM_READ,AM_WRITE};
struct FileImpl{};using FileImplPtr=std::shared_ptr<FileImpl>;
struct lfs_config {int(*prog)(const lfs_config*,lfs_block_t,lfs_off_t,const void*,lfs_size_t)=nullptr;int(*erase)(const lfs_config*,lfs_block_t)=nullptr;};
struct {unsigned blocked_write_attempts=0;} result;
namespace littlefs_impl {
class LittleFSImpl {public:lfs_config _lfs_cfg;unsigned reads=0;
    LittleFSImpl(int,int,int,int,int){} virtual ~LittleFSImpl()=default;
    virtual FileImplPtr open(const char*,OpenMode,AccessMode){++reads;return std::make_shared<FileImpl>();}
    virtual bool format(){return true;}virtual bool remove(const char*){return true;}virtual bool rename(const char*,const char*){return true;}
    virtual bool mkdir(const char*){return true;}virtual bool rmdir(const char*){return true;}
};}
class ReadOnlyImpl final'''+adapter+r'''
int main(){ReadOnlyImpl fs;assert(fs.open("/config.json",OM_DEFAULT,AM_READ));
    assert(!fs.open("/config.json",OM_WRITE,AM_READ));assert(!fs.open("/config.json",OM_DEFAULT,AM_WRITE));
    assert(!fs.format()&&!fs.remove("x")&&!fs.rename("x","y")&&!fs.mkdir("x")&&!fs.rmdir("x"));
    assert(fs._lfs_cfg.prog(nullptr,0,0,nullptr,1)==LFS_ERR_IO&&fs._lfs_cfg.erase(nullptr,0)==LFS_ERR_IO);
    assert(fs.reads==1&&result.blocked_write_attempts==9);}
'''
        with tempfile.TemporaryDirectory() as tmp:self.compile(source,Path(tmp))

if __name__=='__main__':unittest.main()
