"""Actual pinned eboot raw-copy function, public fixture and RAM SPI only."""
import hashlib,json,subprocess,tempfile
from pathlib import Path
from v07_pinned_core_probe import core_root
from v08_m8r_runner import compiler_environment
ROOT=Path(__file__).resolve().parents[1]

def run():
    core=core_root();source=core/'bootloaders/eboot/eboot.c';data=source.read_bytes().replace(b'\r\n',b'\n')
    pins=json.loads((ROOT/'tools/m9_signed_core_sources.json').read_text())
    assert hashlib.sha256(data).hexdigest()==pins['bootloaders/eboot/eboot.c']
    text=data.decode();first=text.index('uint8_t read_flash_byte(');end=text.index('unsigned char __attribute__',first)
    copy=text[text.index('int copy_raw('):text.index('\nint main()',text.index('int copy_raw('))]
    body=text[first:end]+copy
    assert 'SPIEraseSector(daddr/buffer_size)' in body and 'SPIWrite(daddr, buffer, buffer_size)' in body
    with tempfile.TemporaryDirectory(prefix='m9-t-eboot-') as td:
        directory=Path(td);(directory/'pinned_eboot_copy.inc').write_text(body,encoding='utf-8')
        compiler,env=compiler_environment(directory);exe=directory/'eboot.exe';msvc=Path(compiler).name.lower()=='cl.exe'
        command=([compiler,'/nologo','/std:c++20','/EHsc','/O2',f'/I{directory}',str(ROOT/'tools/m9_stagea_eboot_lab.cpp'),'/link',f'/OUT:{exe}'] if msvc else
            [compiler,'-std=c++20','-O2','-fsanitize=address,undefined',f'-I{directory}',str(ROOT/'tools/m9_stagea_eboot_lab.cpp'),'-o',str(exe)])
        compiled=subprocess.run(command,cwd=directory,env=env,capture_output=True,text=True,timeout=60)
        if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
        output=subprocess.run([str(exe),str(ROOT/'experiments/m9_signed_ota/fixtures/signed.inert')],cwd=directory,env=env,capture_output=True,text=True,timeout=60)
        if output.returncode:raise RuntimeError(output.stdout+output.stderr)
        result=json.loads(output.stdout);assert result['interrupted_sector_boundaries']==72 and result['cases']==74
        result['eboot_LF_sha256']=hashlib.sha256(data).hexdigest();result['extracted_function_sha256']=hashlib.sha256(body.encode()).hexdigest()
        return result

if __name__=='__main__':print(json.dumps(run(),indent=2))
