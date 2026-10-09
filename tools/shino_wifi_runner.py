"""Real Python sender -> adapted receiver -> pinned native Core, RAM only."""
import contextlib,hashlib,json,os,secrets,subprocess,tempfile,sys
from pathlib import Path
from shino_wifi_core import materialize,ROOT
from v07_pinned_core_probe import core_root
from v08_m8r_runner import compiler_environment
sys.path.insert(0,str(ROOT/'companion'))
from shino_install import send,proof,capability,InstallError
from m9_signed_fixture_image import inert_image
def build(directory,lab=None,prepare_host=None,defines=(),small_buffer=False):
    core=core_root();generated=materialize(directory/'core',core,small_buffer=small_buffer);bear=core/'tools/sdk/ssl/bearssl'
    host=directory/'host';host.mkdir()
    (host/'MD5Builder.h').write_text('''#pragma once
#include "Arduino.h"
#include <bearssl.h>
struct MD5Builder {br_md5_context ctx;uint8_t digest[16]{};void begin(){br_md5_init(&ctx);}void add(uint8_t* p,size_t n){br_md5_update(&ctx,p,n);}void calculate(){br_md5_out(&ctx,digest);}void getBytes(uint8_t* p){std::memcpy(p,digest,16);}String toString()const{char out[33];for(unsigned i=0;i<16;++i)std::sprintf(out+2*i,"%02x",digest[i]);return out;}};
''')
    if prepare_host:prepare_host(host)
    for name in ('c_types.h','spi_flash.h','user_interface.h'):(generated/name).write_text('#pragma once\n')
    header=(core/'bootloaders/eboot/eboot_command.h').read_text().replace('#define RTC_MEM ((volatile uint32_t*)0x60001200)','extern volatile uint32_t m9_host_rtc[32];\n#define RTC_MEM m9_host_rtc')
    (generated/'eboot_command.h').write_text('extern "C" {\n'+header+'\n}\n')
    # C compilation needs a header without C++ linkage wrapper.
    (generated/'eboot_plain.h').write_text(header)
    cbody=(core/'bootloaders/eboot/eboot_command.c').read_text().replace('"eboot_command.h"','"eboot_plain.h"')
    (generated/'eboot_command.c').write_text(cbody)
    includes=[generated,host,ROOT/'experiments/m9_signed_ota/host',ROOT/'experiments/shino_wifi_install/include',ROOT/'experiments/v08_m7/host_shims',bear/'inc',bear/'src']
    compiler,env=compiler_environment(directory);msvc=Path(compiler).name.lower()=='cl.exe'
    inc=[('/I' if msvc else '-I')+str(x) for x in includes]
    crypto=[bear/'src/hash/sha2small.c',bear/'src/hash/md5.c',bear/'src/mac/hmac.c',*sorted((bear/'src/codec').glob('*.c')),generated/'eboot_command.c']
    command=([compiler,'/nologo','/TC','/O2','/c',*inc,*map(str,crypto)] if msvc else ['gcc','-O2','-c',*inc,*map(str,crypto)])
    p=subprocess.run(command,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    objects=[directory/(x.stem+('.obj' if msvc else '.o')) for x in crypto];exe=directory/('receiver.exe' if msvc else 'receiver')
    sources=[lab or ROOT/'tools/shino_wifi_lab.cpp',generated/'Updater.cpp']
    flags=[('/D' if msvc else '-D')+d for d in (*defines, *((['SHINO_SMALL_OTA_BUFFER=1']) if small_buffer else []))]
    command=([compiler,'/nologo','/std:c++20','/EHsc','/O2','/DHOST_MOCK=1',*flags,*inc,*map(str,sources),*map(str,objects),'/link','/OUT:'+str(exe)] if msvc else
             [compiler,'-std=c++17','-O2','-DHOST_MOCK=1',*flags,*inc,*map(str,sources),*map(str,objects),'-o',str(exe)])
    p=subprocess.run(command,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return exe,env
class IO:
    def __init__(self,exe,env,password):
        self.p=subprocess.Popen([str(exe)],env=dict(env,SHINO_TEST_SECRET=password),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    def line(self,text):self.p.stdin.write(text+'\n');self.p.stdin.flush()
    def write(self,data):self.line('DATA '+data.hex())
    def read(self):
        line=self.p.stdout.readline()
        if not line:raise RuntimeError('Receiver terminated: '+self.p.stderr.read())
        return line.strip()
    def command(self,text):self.line(text);return self.read()
    def report(self):return json.loads(self.command('REPORT'))
    def close(self):self.p.stdin.close();self.p.wait(timeout=5);assert self.p.returncode==0,self.p.stderr.read()
def run(builder=build,native=False):
    with tempfile.TemporaryDirectory(prefix='shino-install-public-') as td:
        directory=Path(td);exe,env=builder(directory);password=secrets.token_hex(32);device='0123456789abcdef';raw=inert_image()
        m=dict(schema=1,family='SHINO-StageA',layout='4m2m',protocol='shino-install-1',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),build_id='b'*64)
        rows=[]
        @contextlib.contextmanager
        def trial(name):
            io=IO(exe,env,password)
            try:yield io;row=io.report();assert row['fs_preserved'];rows.append(dict(name=name,**row))
            finally:io.close()
        def auth(io,command=0,size=None,sha=None,nextBuild=None,private=password):
            key=hashlib.sha256(private.encode()).digest();cn='1'*32
            try:cap=capability(io,device,key,cn)
            except InstallError:
                if native:return 'ERR' # Native may reject floors before listener/CAP.
                raise
            size=len(raw) if size is None else size;sha=sha or m['sha256'];nextBuild=nextBuild or m['build_id']
            signed=f'AUTH {device} {cn} {cap[6]} {command} {size} {sha} {nextBuild}'
            return io.command(f'AUTH {command} {size} {sha} {nextBuild} {proof(key,signed)}')
        def upload(io,data=raw):
            for at in range(0,len(data),512):
                io.write(data[at:at+512]);assert io.read()==f'ACK {min(at+512,len(data))}'
        with trial('valid_real_sender') as io:
            assert send(io,device,password,m,raw)=='STAGED_PENDING_BOOT_CONFIRMATION';assert io.report()['commit']
        with trial('wrong_password') as io:
            try:send(io,device,'f'*64,m,raw);raise AssertionError('bad password accepted')
            except InstallError:
                if native:io.command('DISCONNECT')
            assert io.report()['writes']==0
        with trial('time_wrap') as io:
            io.command('TIME 4294967200');assert auth(io)=='READY';io.command('TIME 40');upload(io);assert io.command('COMMIT').startswith('STAGED ')
        for label,values in [('heap','20479 50000 3248 1'),('largest','60000 16383 3248 1'),('stack','60000 50000 2047 1'),('fragmentation','60000 50000 3248 26')]:
            with trial('admission_'+label) as io:
                io.command('BUDGET '+values);assert auth(io)=='ERR';assert io.report()['writes']==0
        with trial('wrong_interface') as io:
            io.command('POLICY 3232236546 0');assert io.command(f'CAP {device} '+ '1'*32)=='ERR';assert io.report()['writes']==0
        with trial('bad_crc_with_matching_hash') as io:
            data=bytearray(raw);data[0x1014]^=1
            assert auth(io,sha=hashlib.sha256(data).hexdigest())=='READY';upload(io,data);assert io.command('COMMIT')=='ERR'
        for cmd in (100,200,1,4294967295):
            with trial('command_'+str(cmd)) as io:assert auth(io,cmd)=='ERR';assert io.report()['writes']==io.report()['erase']==0
        for name in ('wrong_hmac','oversize','undersize','duplicate','truncated','timeout','disconnect','bad_integrity','bad_format','staging_corrupt','erase_fault','write_fault','read_fault','budget','full_abort'):
            with trial(name) as io:
                if name=='oversize':assert auth(io,size=0xFEFF1)=='ERR'
                elif name=='undersize':assert auth(io,size=1)=='ERR'
                elif name=='wrong_hmac':
                    key=hashlib.sha256(password.encode()).digest();capability(io,device,key,'1'*32)
                    assert io.command(f"AUTH 0 {len(raw)} {m['sha256']} {m['build_id']} {'0'*64}")=='ERR'
                else:
                    assert auth(io)=='READY'
                    if name=='duplicate':assert io.command(f"AUTH 0 {len(raw)} {m['sha256']} {m['build_id']} {'0'*64}")=='ERR'
                    elif name in ('truncated','disconnect','timeout','budget'):
                        io.write(raw[:512]);assert io.read()=='ACK 512'
                        if name=='timeout':io.command('TIME 3001');io.write(raw[512:1024]);assert io.read()=='ERR'
                        elif name=='budget':io.command('BUDGET 20479 50000 3248 1');io.write(raw[512:1024]);assert io.read()=='ERR'
                        elif name=='truncated':
                            if native:assert io.command('DISCONNECT')=='DISCONNECTED'
                            else:assert io.command('COMMIT')=='ERR'
                        else:io.command('ABORT')
                    elif name in ('erase_fault','write_fault'):
                        io.command('FAULT '+name.split('_')[0])
                        # Both Core's default 4096 B and opt-in 256 B buffers
                        # must stop at the FIRST failing physical flash flush.
                        answer=''
                        for at in range(0,4608,512):
                            io.write(raw[at:at+512]);answer=io.read()
                            if answer=='ERR':break
                        assert answer=='ERR'
                    elif name=='bad_format':io.write(b'\x1f'+raw[1:512]);assert io.read()=='ERR'
                    else:
                        data=bytearray(raw)
                        if name=='bad_integrity':data[-32]^=1
                        upload(io,data)
                        if name=='staging_corrupt':io.command('CORRUPT 5000')
                        if name=='read_fault':io.command('FAULT read')
                        if name=='full_abort':io.command('ABORT')
                        else:assert io.command('COMMIT')=='ERR'
                report=io.report();assert not report['commit'] and not report['running'],name
        # Every 512B interruption, including a fully staged image, frees Core
        # buffer without end() or RTC command. RAM sink preserves LittleFS.
        cuts=0
        for cut in range(0,len(raw)+512,512):
            with trial('cut_'+str(cut)) as io:
                assert auth(io)=='READY';upload(io,raw[:min(cut,len(raw))]);io.command('ABORT')
                assert not io.report()['commit'] and not io.report()['running'];cuts+=1
        if native:
            with trial('listener_allocation_failure') as io:
                assert io.command('LISTENFAIL')=='FAULT';assert io.command('CAP '+device+' '+'1'*32)=='ERR'
            with trial('idle_listener_timeout') as io:
                assert io.command('START')=='STARTED';io.command('TIME 15001');assert io.command('PUMP')=='ERR'
            with trial('overlong_control_line') as io:assert io.command('CAP '+device+' '+'1'*512)=='ERR'
            with trial('ap_lost_during_upload') as io:
                assert auth(io)=='READY';io.write(raw[:512]);assert io.read()=='ACK 512'
                io.command('POLICY 3232236546 0');assert io.command('PUMP')=='ERR'
            with trial('socket_disconnect_after_full_staging') as io:
                assert auth(io)=='READY';upload(io);assert io.command('DISCONNECT')=='DISCONNECTED'
        return dict(cases=len(rows),interruption_boundaries=cuts,rows=rows,actual_core=True,actual_python_sender=True,network_calls=0,
                    auth='HMAC-SHA256 private maintenance; not vendor signing',device_contacts=0,physical='NOT_RUN')
if __name__=='__main__':print(json.dumps(run(),indent=2))
