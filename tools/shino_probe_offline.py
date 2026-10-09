"""Authenticated full Wi-Fi transport DRY-RUN with the real native parser.
Only RAM sockets, fake flash/RTC and host ESP. Deliberately never invokes
Updater.begin/write/end in probe mode. Existing upload protocol remains tested
separately against the live-dormant writer in 230 test cases.
"""
import hashlib,json,secrets,tempfile
from pathlib import Path
from shino_wifi_runner import IO,build,ROOT,capability,proof
from shino_maintenance_native import host_shims
from m9_signed_fixture_image import inert_image

def run():
    rows=[]
    with tempfile.TemporaryDirectory(prefix='shino-probe-public-') as work:
        exe,env=build(Path(work),ROOT/'tools/shino_maintenance_native_lab.cpp',
            host_shims,defines=('SHINO_PROBE_TEST=1','SHINO_PUBLIC_INERT_REVIEW=1'),small_buffer=True)
        password=secrets.token_hex(32)
        device='0123456789abcdef'
        raw=inert_image()
        hash_value=hashlib.sha256(raw).hexdigest()
        build_id='b'*64
        def trial(name,variant,command=0,cut=None):
            io=IO(exe,env,password)
            try:
                key=hashlib.sha256(password.encode()).digest()
                client_nonce=secrets.token_hex(16)
                cap=capability(io,device,key,client_nonce)
                signed=f'AUTH {device} {client_nonce} {cap[6]} {command} {len(raw)} {hash_value} {build_id}'
                p=proof(key,signed)
                if variant=='wrong_hmac':p='0'*64
                result=io.command(f'AUTH {command} {len(raw)} {hash_value} {build_id} {p}')
                if variant=='valid':
                    assert result=='READY'
                    data=raw if cut is None else raw[:cut]
                    for at in range(0,len(data),512):
                        io.write(data[at:at+512])
                        assert io.read()==f'ACK {min(at+512,len(data))}'
                    assert io.command('COMMIT')==f'PROBED {build_id}'
                elif variant=='bad_hash':
                    assert result=='READY'
                    bad=raw[:-1]+bytes([raw[-1]^1])
                    for at in range(0,len(bad),512):
                        io.write(bad[at:at+512])
                        assert io.read()==f'ACK {min(at+512,len(bad))}'
                    assert io.command('COMMIT')=='ERR'
                else:
                    assert result=='ERR', (name,result)
                row=io.report()
                assert row['writes']==row['erase']==row['host_restart_calls']==0,(name,row)
                assert not row['commit'] and row['fs_preserved'],(name,row)
                assert row['probed']==(variant=='valid'),(name,row)
                rows.append({'case':name,'probed':row['probed'],'flash_calls':0,'rtc_calls':0,'reboots':0})
            finally:io.close()
        trial('valid_full_ram_only','valid')
        trial('bad_hmac_pre_admission','wrong_hmac')
        trial('filesystem_command_rejected', 'unsupported',command=100)
        trial('bad_image_sha_denied','bad_hash')
    return dict(cases=len(rows),actual_native=True,actual_core=True,
                physical='NOT_RUN',io='RAM_ONLY',no_flash_no_rtc_no_reboot=True,
                dry_run_reply='PROBED',rows=rows)

if __name__=='__main__':print(json.dumps(run(),indent=2))
