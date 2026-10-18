"""Build only the HOST RAM simulator; no firmware, serial, upload or SDK writes."""
import json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.build'
def compiler_environment():
 if os.name!='nt':return shutil.which('g++') or 'g++',dict(os.environ)
 compiler=shutil.which('cl.exe')
 if compiler:return compiler,dict(os.environ)
 vswhere=Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
 install=subprocess.check_output([str(vswhere),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
 if not install:raise RuntimeError('MSVC x64 or GCC required; no compiler installed by this script')
 batch=OUT/'compiler-env.cmd';batch.write_text('@echo off\ncall "'+str(Path(install)/'Common7/Tools/VsDevCmd.bat')+'" -arch=x64 >nul\nset\n')
 run=subprocess.run(['cmd.exe','/d','/c',str(batch)],capture_output=True,text=True,timeout=30,check=True)
 env={k:v for k,v in os.environ.items() if k.upper()!='PATH'}
 for line in run.stdout.splitlines():
  key,sep,val=line.partition('=')
  if sep and key:env['PATH' if key.upper()=='PATH' else key]=val
 compiler=shutil.which('cl.exe',path=env.get('PATH'))
 if not compiler:raise RuntimeError('MSVC x64 required')
 return compiler,env
def build():
 OUT.mkdir(parents=True,exist_ok=True);compiler,env=compiler_environment();msvc=Path(compiler).name.lower()=='cl.exe'
 inc=[ROOT/'core',ROOT/'host',ROOT/'seams/core',ROOT/'seams/wifi',ROOT/'seams/base',ROOT/'vendor/bearssl/inc',ROOT/'vendor/bearssl/src']
 flags=[('/I' if msvc else '-I')+str(x) for x in inc]
 sources=[ROOT/'vendor/bearssl/src/hash/sha2small.c',ROOT/'vendor/bearssl/src/hash/md5.c',ROOT/'vendor/bearssl/src/mac/hmac.c',*sorted((ROOT/'vendor/bearssl/src/codec').glob('*.c')),ROOT/'core/eboot_command.c']
 def run(args):
  result=subprocess.run(args,cwd=OUT,env=env,capture_output=True,text=True,timeout=120)
  if result.returncode:raise RuntimeError(result.stdout+result.stderr)
 run([compiler,'/nologo','/TC','/O2','/c',*flags,*map(str,sources)] if msvc else ['gcc','-O2','-c',*flags,*map(str,sources)])
 objects=[OUT/(p.stem+('.obj' if msvc else '.o')) for p in sources]
 defines=['HOST_MOCK=1','ARDUINOJSON_POOL_CAPACITY=8','SHINO_B53_AUTONOMY_EXPERIMENTAL=1','SHINO_B53_DIAGNOSTIC_OFF=1','SHINO_B54_LAN_WEATHER=1','SHINO_UPDATER_FLASH_BUFFER_512=1']
 exe=OUT/('receiver.exe' if msvc else 'receiver');cxx=[ROOT/'tests/lab.cpp',ROOT/'core/Updater.cpp']
 run([compiler,'/nologo','/std:c++20','/EHsc','/O2',*['/D'+x for x in defines],*flags,*map(str,cxx),*map(str,objects),'/link','/OUT:'+str(exe)] if msvc else [compiler,'-std=c++20','-O2','-pthread',*['-D'+x for x in defines],*flags,*map(str,cxx),*map(str,objects),'-o',str(exe)])
 from weather_vm.protocol import sample
 (OUT/'vectors.inc').write_text('static const char* FrozenSample="'+sample(bytes(range(32)),bytes.fromhex('0102030405060708'),bytes.fromhex('1020304050607080'),1,1791955392,2700,182,3).hex()+'";\n')
 native=OUT/('native_receiver.exe' if msvc else 'native_receiver')
 native_flags=[('/I' if msvc else '-I')+str(p) for p in (ROOT/'host',OUT,ROOT/'vendor/bearssl/inc')]
 sha_objects=[OUT/(name+('.obj' if msvc else '.o')) for name in ('sha2small','dec32be','enc32be')]
 run([compiler,'/nologo','/std:c++20','/EHsc','/O2',*native_flags,str(ROOT/'tests/native_receiver.cpp'),*map(str,sha_objects),'/link','/OUT:'+str(native)] if msvc else [compiler,'-std=c++20','-O2',*native_flags,str(ROOT/'tests/native_receiver.cpp'),*map(str,sha_objects),'-o',str(native)])
 return exe,native,env
